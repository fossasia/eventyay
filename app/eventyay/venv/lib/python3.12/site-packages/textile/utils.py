try:
    import regex as re
except ImportError:
    import re

from urllib.parse import urlparse
import html

from collections import OrderedDict

from xml.etree import ElementTree

from textile.regex_strings import valign_re_s, halign_re_s

# Regular expressions for stripping chunks of HTML,
# leaving only content not wrapped in a tag or a comment
RAW_TEXT_REVEALERS = (
    # The php version has orders the below list of tags differently.  The
    # important thing to note here is that the pre must occur before the p or
    # else the regex module doesn't properly match pre-s. It only matches the
    # p in pre.
    re.compile(r'<(pre|p|blockquote|div|form|table|ul|ol|dl|h[1-6])[^>]*?>.*</\1>',
               re.S),
    re.compile(r'<(hr|br)[^>]*?/>'),
    re.compile(r'<!--.*?-->'),
)


def decode_high(text):
    """Decode encoded HTML entities."""
    text = '&#{0};'.format(text)
    return html.unescape(text)


def encode_high(text):
    """Encode the text so that it is an appropriate HTML entity."""
    return ord(text)


def encode_html(text, quotes=True):
    """Return text that's safe for an HTML attribute."""
    a = (
        ('&', '&amp;'),
        ('<', '&lt;'),
        ('>', '&gt;'))

    if quotes:
        a = a + (("'", '&#39;'),
                 ('"', '&quot;'))

    for k, v in a:
        text = text.replace(k, v)
    return text


def generate_tag(tag, content, attributes=None):
    """Generate a complete html tag using the ElementTree module.  tag and
    content are strings, the attributes argument is a dictionary.  As
    a convenience, if the content is ' /', a self-closing tag is generated."""
    enc = 'unicode'
    if not tag:
        return content
    element = ElementTree.Element(tag, attrib=attributes)
    # Sort attributes for Python 3.8+, as suggested in
    # https://docs.python.org/3/library/xml.etree.elementtree.html
    if len(element.attrib) > 1:
        # adjust attribute order, e.g. by sorting
        attribs = sorted(element.attrib.items())
        element.attrib.clear()
        element.attrib.update(attribs)
    # FIXME: Kind of an ugly hack.  There *must* be a cleaner way.  I tried
    # adding text by assigning it to element_tag.text.  That results in
    # non-ascii text being html-entity encoded.  Not bad, but not entirely
    # matching php-textile either.
    element_tag = ElementTree.tostringlist(element, encoding=enc,
                                           method='html')
    element_tag.insert(len(element_tag) - 1, content)
    element_text = ''.join(element_tag)
    return element_text


def getimagesize(url):
    """
    Attempts to determine an image's width and height, and returns a tuple,
    (width, height), in pixels or an empty string in case of failure.
    Requires that PIL is installed.

    """

    try:
        from PIL import ImageFile
    except ImportError:
        return ''

    from urllib.request import urlopen

    try:
        p = ImageFile.Parser()
        f = urlopen(url)
        while True:
            s = f.read(1024)
            if not s:
                break
            p.feed(s)
            if p.image:
                return p.image.size
    except (IOError, ValueError):
        return ''


def has_raw_text(text):
    """checks whether the text has text not already enclosed by a block tag"""
    r = text.strip()
    for pattern in RAW_TEXT_REVEALERS:
        r = pattern.sub('', r).strip()
    return r != ''


def human_readable_url(url):
    if "://" in url:
        url = url.split("://")[1]
    elif ":" in url:
        url = url.split(":")[1]
    return url


def is_rel_url(url):
    """Identify relative urls."""
    (scheme, netloc) = urlparse(url)[0:2]
    return not scheme and not netloc


def is_valid_url(url):
    parsed = urlparse(url)
    if parsed.scheme == '':
        return True
    return False


def list_type(list_string):
    listtypes = {
        list_string.endswith('*'): 'u',
        list_string.endswith('#'): 'o',
        (not list_string.endswith('*') and not list_string.endswith('#')):
        'd'
    }
    return listtypes.get(True, False)


def normalize_newlines(string):
    out = re.sub(r'\r\n?', '\n', string)
    out = re.compile(r'^[ \t]*\n', flags=re.M).sub('\n', out)
    out = out.strip('\n')
    return out


def parse_attributes(block_attributes, element=None, include_id=True, restricted=False):
    vAlign = {'^': 'top', '-': 'middle', '~': 'bottom'}
    hAlign = {'<': 'left', '=': 'center', '>': 'right', '<>': 'justify'}
    style = []
    aclass = ''
    lang = ''
    colspan = ''
    rowspan = ''
    block_id = ''
    span = ''
    width = ''
    result = OrderedDict()

    if not block_attributes:
        return result

    matched = block_attributes
    if element == 'td':
        m = re.search(r'\\(\d+)', matched)
        if m:
            colspan = m.group(1)

        m = re.search(r'/(\d+)', matched)
        if m:
            rowspan = m.group(1)

    if element == 'td' or element == 'tr':
        m = re.search(r'(^{0})'.format(valign_re_s), matched)
        if m:
            style.append("vertical-align:{0}".format(vAlign[m.group(1)]))

    if not restricted:
        m = re.search(r'\{([^}]*)\}', matched)
        if m:
            style.extend(m.group(1).rstrip(';').split(';'))
            matched = matched.replace(m.group(0), '')

    m = re.search(r'\[([^\]]+)\]', matched, re.U)
    if m:
        lang = m.group(1)
        matched = matched.replace(m.group(0), '')

    m = re.search(r'\(([^()]+)\)', matched, re.U)
    if m:
        matched = matched.replace(m.group(0), '')
        # Only allow a restricted subset of the CSS standard characters for classes/ids.
        # No encoding markers allowed.
        id_class_match = re.compile(r"^([-a-zA-Z 0-9_\/\[\]\.\:\#]+)$", re.U).match(m.group(1))
        if id_class_match:
            class_regex = re.compile(r"^([-a-zA-Z 0-9_\.\/\[\]]*)$")
            id_class = id_class_match.group(1)
            # If a textile class block attribute was found with a '#' in it
            # split it into the css class and css id...
            hashpos = id_class.find('#')
            if hashpos >= 0:
                id_match = re.match(r"^#([-a-zA-Z0-9_\.\:]*)$", id_class[hashpos:])
                if id_match:
                    block_id = id_match.group(1)

                cls_match = class_regex.match(id_class[:hashpos])
            else:
                cls_match = class_regex.match(id_class)

            if cls_match:
                aclass = cls_match.group(1)

    m = re.search(r'([(]+)', matched)
    if m:
        style.append("padding-left:{0}em".format(len(m.group(1))))
        matched = matched.replace(m.group(0), '')

    m = re.search(r'([)]+)', matched)
    if m:
        style.append("padding-right:{0}em".format(len(m.group(1))))
        matched = matched.replace(m.group(0), '')

    m = re.search(r'({0})'.format(halign_re_s), matched)
    if m:
        style.append("text-align:{0}".format(hAlign[m.group(1)]))

    if element == 'col':
        pattern = r'(?:\\(\d+)\.?)?\s*(\d+)?'
        csp = re.match(pattern, matched)
        span, width = csp.groups()

    if colspan:
        result['colspan'] = colspan

    if style:
        # Previous splits that created style may have introduced extra
        # whitespace into the list elements.  Clean it up.
        style = [x.strip() for x in style]
        result['style'] = '{0};'.format("; ".join(style))
    if aclass:
        result['class'] = aclass
    if block_id and include_id:
        result['id'] = block_id
    if lang:
        result['lang'] = lang
    if rowspan:
        result['rowspan'] = rowspan
    if span:
        result['span'] = span
    if width:
        result['width'] = width
    return result


def pba(block_attributes, element=None, include_id=True, restricted=False):
    """Parse block attributes."""
    attrs = parse_attributes(block_attributes, element, include_id, restricted)
    if not attrs:
        return ''
    result = ' '.join(['{0}="{1}"'.format(k, v) for k, v in attrs.items()])
    return ' {0}'.format(result)
