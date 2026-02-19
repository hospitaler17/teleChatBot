# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from __future__ import annotations

import os
import sys

# -- Path setup -------------------------------------------------------
# Make the project root importable so autodoc can find source modules.
sys.path.insert(0, os.path.abspath(".."))

# -- Project information ----------------------------------------------
project = "teleChatBot"
copyright = "2025, teleChatBot contributors"
author = "teleChatBot contributors"
release = "0.1.0"

# -- General configuration --------------------------------------------
extensions = [
    "sphinx.ext.autodoc",          # Core autodoc – pulls docstrings from source
    "sphinx.ext.napoleon",          # Google / NumPy style docstring support
    "sphinx_autodoc_typehints",    # Render type hints in API docs
    "sphinx.ext.viewcode",          # [source] links in API docs
    "sphinx.ext.intersphinx",       # Cross-references to Python stdlib etc.
    "myst_parser",                  # Markdown source files
    "sphinxcontrib.plantuml",       # Render *.puml diagrams
]

# -- MyST (Markdown) --------------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "attrs_inline",
]

# -- autodoc ----------------------------------------------------------
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_typehints_format = "short"
always_document_param_types = True

# -- napoleon ---------------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_attr_annotations = True

# -- intersphinx ------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
}

# -- Nitpick ignore ---------------------------------------------------
# Suppress unresolvable cross-references for third-party libraries that
# don't publish a Sphinx inventory, and for modules documented with
# :no-index: to avoid duplicate-object warnings.
nitpick_ignore = [
    # yaml – no public Sphinx inventory
    ("py:class", "yaml.error.YAMLError"),
    ("py:class", "yaml.loader.SafeLoader"),
    ("py:exc", "yaml.YAMLError"),
    # typing generics – not exposed as py:data in stdlib docs
    ("py:data", "typing.Any"),
    ("py:data", "typing.Optional"),
    ("py:data", "typing.Union"),
    ("py:data", "Ellipsis"),
    # src.config.settings uses :no-index: to prevent duplicate descriptions
    ("py:class", "AppSettings"),
    ("py:exc", "DuplicateKeyError"),
]
nitpick_ignore_regex = [
    # python-telegram-bot – no Sphinx inventory
    (r"py:class", r"telegram\..*"),
    # All src.config.settings.* references (module documented with :no-index:)
    (r"py:class", r"src\.config\.settings\..*"),
]

# -- PlantUML ---------------------------------------------------------
# Try to use the system `plantuml` command; fall back to the jar if set.
_plantuml_jar = os.environ.get("PLANTUML_JAR")
if _plantuml_jar:
    plantuml = f"java -jar {_plantuml_jar}"
else:
    plantuml = "plantuml"
plantuml_output_format = "svg"

# -- Templates & static files -----------------------------------------
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML output -------------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_title = "teleChatBot documentation"
html_show_sourcelink = True

html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "titles_only": False,
}
