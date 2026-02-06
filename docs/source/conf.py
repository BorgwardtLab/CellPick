# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.abspath("../../cellpick"))


def setup(app):
    app.add_css_file("_static/hide_links.css")
    app.add_js_file("force_light_mode.js")


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "cellpick"
copyright = "2025, Lucas Miranda, Paolo Pellizzoni"
author = "Lucas Miranda, Paolo Pellizzoni"
release = "0.2.2"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinx_copybutton",
    "sphinx_design",
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
autodoc_mock_imports = [
    "numpy",
    "pandas",
    "matplotlib",
    "matplotlib.image",
    "matplotlib.pyplot",
    "PIL",
    "PIL.Image",
    "untangle",
    "lxml",
    "lxml.etree",
    "scipy",
    "scipy.interpolate",
    "scipy.ndimage",
    "tqdm",
    "skimage",
    "skimage.measure",
    "shapely",
    "shapely.geometry",
    "czifile",
    "tifffile",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "qt_material",
    "imagecodecs",
    "spatialdata",
    "spatialdata.models",
    "spatialdata.transformations",
    "xarray",
    "geopandas",
    "anndata",
]  # type: ignore

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
    "use_issues_button": False,
    "use_repository_button": False,
}

html_title = "CellPick"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

autodoc_default_options = {
    "member-order": "bysource",
    "undoc-members": True,
    "show-inheritance": True,
}

# Additional autodoc settings for better RTD compatibility
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True

html_favicon = "../../cellpick/assets/logo-small.svg"
html_logo = "../../cellpick/assets/logo-small.svg"
