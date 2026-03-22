"""
    python-creole
    ~~~~~~~~~~~~~


    :copyleft: 2008-2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


from xml.sax.saxutils import escape


def _mask_content(emitter, node, mask_tag):
    attrs = node.get_attrs_as_string()
    if attrs:
        attrs = " " + attrs

    tag_data = {
        "tag": node.kind,
        "attrs": attrs,
        "mask_tag": mask_tag,
    }

    content = emitter.emit_children(node)
    if not content:
        # single tag
        return f"<<{tag_data['mask_tag']}>><{tag_data['tag']}{tag_data['attrs']} /><</{tag_data['mask_tag']}>>"

    start_tag = f"<<{tag_data['mask_tag']}>><{tag_data['tag']}{tag_data['attrs']}><</{tag_data['mask_tag']}>>"
    end_tag = f"<<{tag_data['mask_tag']}>></{tag_data['tag']}><</{tag_data['mask_tag']}>>"

    return start_tag + content + end_tag


def raise_unknown_node(emitter, node):
    """
    unknown_emit callable for Html2CreoleEmitter

    Raise NotImplementedError on unknown tags.
    """
    content = emitter.emit_children(node)
    raise NotImplementedError(
        f"Node from type '{node.kind}' is not implemented! (child content: {content!r})"
    )


def use_html_macro(emitter, node):
    """
    unknown_emit callable for Html2CreoleEmitter

    Use the <<html>> macro to mask unknown tags.
    """
    return _mask_content(emitter, node, mask_tag="html")


def preformat_unknown_nodes(emitter, node):
    """
    Put unknown tags in a <pre> area.

    Usefull for html2textile.emitter.TextileEmitter()
    """
    return _mask_content(emitter, node, mask_tag="pre")


def escape_unknown_nodes(emitter, node):
    """
    unknown_emit callable for Html2CreoleEmitter

    All unknown tags should be escaped.
    """
    attrs = node.get_attrs_as_string()
    if attrs:
        attrs = " " + attrs

    tag_data = {
        "tag": node.kind,
        "attrs": attrs,
    }

    content = emitter.emit_children(node)
    if not content:
        # single tag
        return escape(f"<{tag_data['tag']}{tag_data['attrs']} />")

    start_tag = escape(f"<{tag_data['tag']}{tag_data['attrs']}>")
    end_tag = escape(f"</{tag_data['tag']}>")

    return start_tag + content + end_tag


def transparent_unknown_nodes(emitter, node):
    """
    unknown_emit callable for Html2CreoleEmitter

    Remove all unknown html tags and show only
    their child nodes' content.
    """
    return emitter._emit_content(node)
