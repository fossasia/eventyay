from csp.tests.utils import ScriptExtensionTestBase


class TestJinjaExtension(ScriptExtensionTestBase):
    def test_script_tag_injects_nonce(self) -> None:
        tpl = """
            {% script %}
                var hello='world';
            {% endscript %}
        """

        expected = """<script nonce="{}">var hello='world';</script>"""
        self.assert_template_eq(*self.process_templates(tpl, expected))

    def test_script_with_src_ignores_body(self) -> None:
        tpl = """
            {% script src="foo" %}
                var hello='world';
            {% endscript %}
        """

        expected = """<script nonce="{}" src="foo"></script>"""

        self.assert_template_eq(*self.process_templates(tpl, expected))

    def test_script_tag_sets_attrs_correctly(self) -> None:
        tpl = """
            {% script id='jeff' defer=True %}
                var hello='world';
            {% endscript %}
            """
        expected = """
            <script nonce="{}" id="jeff" defer>
                var hello='world';
            </script>"""

        self.assert_template_eq(*self.process_templates(tpl, expected))

    def test_async_attribute_with_falsey(self) -> None:
        tpl = """
            {% script id="jeff" async=False %}
                var hello='world';
            {% endscript %}"""

        expected = '<script nonce="{}" id="jeff" async=false>var hello=\'world\';</script>'

        self.assert_template_eq(*self.process_templates(tpl, expected))

    def test_async_attribute_with_truthy(self) -> None:
        tpl = """
            {% script id="jeff" async=True %}
                var hello='world';
            {% endscript %}"""

        expected = '<script nonce="{}" id="jeff" async>var hello=\'world\';</script>'

        self.assert_template_eq(*self.process_templates(tpl, expected))

    def test_nested_script_tags_are_removed(self) -> None:
        """Let users wrap their code in script tags for the sake of their
        development environment"""
        tpl = """
            {% script type="application/javascript" id="jeff" defer=True%}
                <script type="text/javascript">
                var hello='world';
                </script>
            {% endscript %}"""

        expected = '<script nonce="{}" id="jeff" type="application/javascript" defer>var hello=\'world\';</script>'

        self.assert_template_eq(*self.process_templates(tpl, expected))

    def test_regex_captures_script_content_including_brackets(self) -> None:
        """
        Ensure that script content get captured properly.
        Especially when using angle brackets."""
        tpl = """
            {% script %}
            <script type="text/javascript">
                let capture_text = "<script></script>"
            </script>
            {% endscript %}
            """

        expected = '<script nonce="{}">let capture_text = "<script></script>"</script>'

        self.assert_template_eq(*self.process_templates(tpl, expected))
