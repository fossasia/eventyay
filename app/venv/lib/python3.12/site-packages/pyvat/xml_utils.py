class NodeNotFoundError(Exception):
    """XML node was not found.
    """

    pass


def get_first_child_element(node, tag_name):
    """Get the first child element node with a given tag name.

    :param node: Parent node.
    :type node: xml.dom.Node
    :returns: the first child element node with the given tag name.
    :rtype: xml.dom.Node
    :raises NodeNotFoundError:
        if no child node with the given tag name was found.
    """

    for child in node.childNodes:
        if child.nodeType == node.ELEMENT_NODE and \
           child.tagName == tag_name:
            return child

    raise NodeNotFoundError('no child element node with tag %s was found' %
                            (tag_name))


def get_text(node):
    """Get text from a node.

    :param node: Node.
    :type node: xml.dom.Node
    :returns: the node's text
    """

    return ''.join(child.data for child in node.childNodes
                   if child.nodeType == node.TEXT_NODE)
