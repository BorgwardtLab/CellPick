# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys

sys.path.insert(0, os.path.abspath("../../cellpick"))


def setup(app):
    app.add_css_file("_static/hide_links.css")
    app.add_js_file("force_light_mode.js")


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "cellpick"
copyright = "2025, Lucas Miranda, Paolo Pellizzoni"
author = "Lucas Miranda, Paolo Pellizzoni"
release = "2025.7.22"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinxarg.ext",
    "sphinx_rtd_theme",
    "sphinx_design",
    "sphinx_copybutton",
]
exclude_patterns = []

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

# autodoc_mock_imports = []
autodoc_mock_imports = []  # type: ignore

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"

html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
    "logo": {
        "image_light": "../../cellpick/assets/logo.svg",
    },
}

html_title = "CellPick"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

autodoc_default_options = {
    "member-order": "bysource",
}

html_favicon = "../../cellpick/assets/logo-small.svg"
html_logo = "../../cellpick/assets/logo-small.svg"
