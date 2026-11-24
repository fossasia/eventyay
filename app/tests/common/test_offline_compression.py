from compressor.offline.django import DjangoParser
from django.conf import settings
from django.template import Context
from django.test import override_settings


@override_settings(COMPRESS_ENABLED=True, COMPRESS_OFFLINE=True)
def test_submission_content_edit_compress_blocks():
    """Ensure submission_video.js is in a dedicated CompressNode.

    This ensures offline compression generates separate manifest keys for base scripts
    and optional video dependencies.
    """
    parser = DjangoParser(charset='utf-8')
    template = parser.parse('orga/submission/content_edit.html')
    context = Context(parser.get_init_context(getattr(settings, 'COMPRESS_OFFLINE_CONTEXT', {})))
    nodes = list(parser.walk_nodes(template, context=context))
    compress_nodes = [n for n in nodes if n.__class__.__name__ == 'CompressorNode']
    rendered_blocks = [parser.render_nodelist(template, context, n) for n in compress_nodes]
    assert any('submission_video.js' in b for b in rendered_blocks)
    assert any('submission_form.js' in b for b in rendered_blocks)
