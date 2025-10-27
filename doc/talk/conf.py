import os
import sys
from datetime import date

# Add the app source to the path (pointing to app directory, not old talk directory)
sys.path.insert(0, os.path.abspath("../../app"))
sys.path.insert(0, os.path.abspath("./_extensions"))

# Try to import eventyay for talk component
try:
    os.environ.setdefault("EVENTYAY_CONFIG_FILE", os.path.join(os.path.dirname(__file__), '../eventyay-docs.cfg'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventyay.config.settings")
    os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
    os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
    import django
    django.setup()
    version = "1.0"
    release = "1.0.0"
except (ImportError, Exception):
    version = "1.0"
    release = "1.0.0"

project = "Talk Component"
copyright = "2025 Apache 2.0 License by contributors"
author = "FOSSASIA"

try:
    import enchant

    HAS_PYENCHANT = True
except:
    HAS_PYENCHANT = False

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinxcontrib.httpdomain",
    "sphinxcontrib_django",
    "changelog",
    "sphinx_rtd_theme",
]
if HAS_PYENCHANT:
    extensions.append("sphinxcontrib.spelling")

templates_path = ["_templates"]
source_suffix = {".rst": "restructuredtext"}
master_doc = "contents"

language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

pygments_style = "sphinx"
html_static_path = ["_static"]
html_additional_pages = {}
html_extra_path = ["api/schema.yml"]
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    'logo_only': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}
html_css_files = [
    'eventyay_custom.css',
]
html_context = {
    "display_github": True,  # Integrate GitHub
    "github_user": "fossasia",  # Username
    "github_repo": "eventyay",  # Repo name
    "github_version": "enext",  # Version
    "conf_py_path": "/doc/talk/",  # Path in the checkout to the docs root
}

linkcheck_ignore = [
    "https://eventyay.yourdomain.com",
    "http://localhost",
    "http://127.0.0.1",
    "/schema.yml",
    r"https://github.com/fossasia/eventyay/issues/\d+",
    r"https://github.com/fossasia/eventyay/issues/new",
    r"https://github.com/fossasia/eventyay/discussions/new",
]

htmlhelp_basename = "eventyay-talk-doc"
autodoc_member_order = "groupwise"

if HAS_PYENCHANT:
    spelling_lang = "en_GB"
    spelling_word_list_filename = "spelling_wordlist.txt"
    spelling_show_suggestions = False

copybutton_prompt_text = (
    r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: |# |\(env\)\$ "
)
copybutton_prompt_is_regexp = True
copybutton_line_continuation_character = "\\"


def include_redoc_for_docs(app, page_name, template_name, context, doctree):
    if page_name == "api/resources":
        app.add_js_file("redoc.standalone.js")
        app.add_js_file("rest.js")


def setup(app):
    app.connect("html-page-context", include_redoc_for_docs)
