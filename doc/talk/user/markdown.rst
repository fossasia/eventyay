.. _talk-markdown-guide:

Markdown Guide
==============

What is Markdown?
-----------------

Eventyay often allows you to write `Markdown`_ instead of plain text, like in
talk descriptions, the Call for Papers, and email texts. Markdown is helpful if
you want to write text including links, bold text, and other formatted content.
Markdown is a common option since it’s way easier to learn than languages like
HTML but allows all basic formatting options required for text in those places.

Formatting rules
----------------

The following table shows the markdown syntax on the left, and the results are
on the right:

+--------------------------------------------+----------------------------------------+
| Markdown                                   | Result                                 |
+============================================+========================================+
| .. code-block:: md                         |                                        |
|                                            |                                        |
|     Please keep the deadline.              | Please keep the deadline.              |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         |                                        |
|                                            |                                        |
|     This is **important**.                 | This is **important**.                 |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         |                                        |
|                                            |                                        |
|     Print `this`.                          | Print ``this``.                        |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         |                                        |
|                                            | Look at https://eventyay.com.          |
|     Look at https://eventyay.com.          |                                        |
|     Look at [this](https://eventyay.com)   | Look at `this <https://eventyay.com>`_ |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         |                                        |
|                                            |                                        |
|    * First item                            |  * First item                          |
|    * Second item (long)                    |  * Second item (long)                  |
|    * Third item                            |  * Third item                          |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         |                                        |
|                                            |                                        |
|    1. First item                           |  1. First item                         |
|    2. Second item                          |  2. Second item                        |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         |  Headings (H1-H6)                      |
|                                            |                                        |
|    # Headline 1                            |                                        |
+--------------------------------------------+----------------------------------------+
| .. code-block:: md                         | Horizontal rule                        |
|                                            |                                        |
|     -----                                  |                                        |
+--------------------------------------------+----------------------------------------+


Using HTML
----------

You can also directly embed HTML code, if you want, although we recommend using
Markdown, as it enables e.g. people using text-based email clients to get a
better plain text representation of your text. Note that for security reasons
you can use the following HTML elements, and no others::

    a, abbr, acronym, b, br, code, div, em, h1, h2,
    h3, h4, h5, h6, hr, i, li, ol, p, pre, span, strong,
    table, tbody, td, thead, tr, ul

You can use the following attributes::

    <a href="..." title="...">
    <abbr title="...">
    <acronym title="...">
    <table width="...">
    <td width="..." align="...">
    <div class="...">
    <p class="...">
    <span class="..."...

Eventyay will strip all other elements and attributes during parsing.


.. _Markdown: https://en.wikipedia.org/wiki/Markdown
