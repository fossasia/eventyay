"""
    html2textile unittest
    ~~~~~~~~~~~~~~~~~~~~~

    Unittests for special cases which only works in the html2textile way.

    Note: This only works fine if there is no problematic whitespace handling.

    :copyleft: 2011 by python-creole team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import unittest

from creole.shared.unknown_tags import preformat_unknown_nodes
from creole.tests.utils.base_unittest import BaseCreoleTest


class TextileTests(BaseCreoleTest):
    def test_entities(self):
        """
        can't be cross tested, because textile would convert < to &#60; and > to &#62;
        """
        self.assert_html2textile(
            textile_string="""
                less-than sign: <
                greater-than sign: >
            """,
            html_string="""
                <p>less-than sign: &lt;<br />
                greater-than sign: &gt;</p>
            """,
            # debug=True
        )

    def test_preformat_unknown_nodes(self):
        """
        Put unknown tags in a <pre> area.
        """
        self.assert_html2textile(
            textile_string="""
                111 <<pre>><x><</pre>>foo<<pre>></x><</pre>> 222
                333<<pre>><x foo1="bar1"><</pre>>foobar<<pre>></x><</pre>>444

                555<<pre>><x /><</pre>>666
            """,
            html_string="""
                <p>111 <x>foo</x> 222<br />
                333<x foo1="bar1">foobar</x>444</p>

                <p>555<x />666</p>
            """,
            emitter_kwargs={"unknown_emit": preformat_unknown_nodes}
        )

    def test_transparent_unknown_nodes(self):
        """
        transparent_unknown_nodes is the default unknown_emit:

        Remove all unknown html tags and show only
        their child nodes' content.
        """
        self.assert_html2textile(
            textile_string="""
                111 foo 222
                333foobar444

                555666
            """,
            html_string="""
                <p>111 <x>foo</x> 222<br />
                333<x foo1="bar1">foobar</x>444</p>

                <p>555<x />666</p>
            """,
        )


if __name__ == '__main__':
    unittest.main()
