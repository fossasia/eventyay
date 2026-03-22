class StylesheetCache:
    def __init__(self, size: int = 8) -> None: ...

class CSSInliner:
    def __init__(
        self,
        inline_style_tags: bool = True,
        keep_style_tags: bool = False,
        keep_link_tags: bool = False,
        keep_at_rules: bool = False,
        minify_css: bool = False,
        base_url: str | None = None,
        load_remote_stylesheets: bool = True,
        cache: StylesheetCache | None = None,
        extra_css: str | None = None,
        preallocate_node_capacity: int | None = 32,
        remove_inlined_selectors: bool = False,
    ) -> None: ...
    def inline(self, html: str) -> str: ...
    def inline_fragment(self, html: str, css: str) -> str: ...
    def inline_many(self, html: list[str]) -> list[str]: ...
    def inline_many_fragments(self, html: list[str], css: list[str]) -> list[str]: ...

def inline(
    html: str,
    inline_style_tags: bool = True,
    keep_style_tags: bool = False,
    keep_link_tags: bool = False,
    keep_at_rules: bool = False,
    minify_css: bool = False,
    base_url: str | None = None,
    load_remote_stylesheets: bool = True,
    cache: StylesheetCache | None = None,
    extra_css: str | None = None,
    preallocate_node_capacity: int | None = 32,
    remove_inlined_selectors: bool = False,
) -> str: ...
def inline_fragment(
    html: str,
    css: str,
    inline_style_tags: bool = True,
    keep_style_tags: bool = False,
    keep_link_tags: bool = False,
    keep_at_rules: bool = False,
    minify_css: bool = False,
    base_url: str | None = None,
    load_remote_stylesheets: bool = True,
    cache: StylesheetCache | None = None,
    extra_css: str | None = None,
    preallocate_node_capacity: int | None = 32,
    remove_inlined_selectors: bool = False,
) -> str: ...
def inline_many(
    html: list[str],
    inline_style_tags: bool = True,
    keep_style_tags: bool = False,
    keep_link_tags: bool = False,
    keep_at_rules: bool = False,
    minify_css: bool = False,
    base_url: str | None = None,
    load_remote_stylesheets: bool = True,
    cache: StylesheetCache | None = None,
    extra_css: str | None = None,
    preallocate_node_capacity: int | None = 32,
    remove_inlined_selectors: bool = False,
) -> list[str]: ...
def inline_many_fragments(
    html: list[str],
    css: list[str],
    inline_style_tags: bool = True,
    keep_style_tags: bool = False,
    keep_link_tags: bool = False,
    keep_at_rules: bool = False,
    minify_css: bool = False,
    base_url: str | None = None,
    load_remote_stylesheets: bool = True,
    cache: StylesheetCache | None = None,
    extra_css: str | None = None,
    preallocate_node_capacity: int | None = 32,
    remove_inlined_selectors: bool = False,
) -> list[str]: ...

class InlineError(ValueError): ...
