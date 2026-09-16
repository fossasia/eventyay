from django.db import migrations
import markdown
import nh3
import re


# Migration-local sanitizer snapshot. Do not import the live
# ``sanitize_page_rich_text`` helper — later allowlist changes must not change
# historical conversion results for installs that apply this migration later.
_PAGE_TAGS = frozenset({
    'p', 'br', 'strong', 'b', 'em', 'i', 'u',
    'ul', 'ol', 'li', 'a', 'blockquote', 'img',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
})
_PAGE_ATTRIBUTES = {
    'a': {'href', 'rel'},
    'img': {'src', 'alt', 'width', 'height', 'title'},
}
_URL_SCHEMES = frozenset({'http', 'https', 'mailto', 'tel', 'data'})


def _attribute_filter(tag, attr, value):
    if attr not in _PAGE_ATTRIBUTES.get(tag, ()):
        return None

    normalized = value.lstrip().lower()
    if normalized.startswith('data:'):
        if not (tag == 'img' and attr == 'src' and normalized.startswith('data:image/')):
            return None

    if tag == 'img' and attr == 'src':
        if not normalized.startswith(('data:image/', 'http://', 'https://', '/')):
            return None
    return value


def sanitize_page_rich_text_historical(html):
    if not html:
        return html
    return nh3.clean(
        html,
        tags=_PAGE_TAGS,
        attributes=_PAGE_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        url_schemes=_URL_SCHEMES,
        link_rel='noopener noreferrer',
    )


def is_tiptap_html(text):
    if not text:
        return False
    text_str = str(text).strip()
    return bool(re.match(r'^\s*<(p|ul|ol|blockquote|h[1-6])(\s|>)', text_str, re.IGNORECASE))


def convert_markdown_to_html(apps, schema_editor):
    Page = apps.get_model('base', 'Page')

    md = markdown.Markdown(
        extensions=[
            'markdown.extensions.nl2br',
            'markdown.extensions.sane_lists',
            'markdown.extensions.tables',
            'markdown.extensions.fenced_code',
        ]
    )

    for page in Page.objects.all().iterator():
        if page.text:
            text_data = page.text.data
            if isinstance(text_data, dict):
                new_data = {}
                changed = False
                for lang, text in text_data.items():
                    if text and not is_tiptap_html(text):
                        md.reset()
                        raw_html = md.convert(str(text))
                        new_data[lang] = sanitize_page_rich_text_historical(raw_html)
                        changed = True
                    else:
                        new_data[lang] = text
                if changed:
                    page.text.data = new_data
                    page.save(update_fields=['text'])
            elif isinstance(text_data, str) and text_data and not is_tiptap_html(text_data):
                md.reset()
                raw_html = md.convert(text_data)
                page.text.data = sanitize_page_rich_text_historical(raw_html)
                page.save(update_fields=['text'])


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0065_queuedmail_is_draft'),
    ]

    operations = [
        migrations.RunPython(
            convert_markdown_to_html,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
