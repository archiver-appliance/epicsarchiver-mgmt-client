"""Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options. For a full
list see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

from importlib.metadata import version as get_version

# -- Project information -----------------------------------------------------

project = "epicsarchiver-mgmt-client"
copyright = "2026, European Spallation Source ERIC"  # noqa: A001
authors = ["Sky Brewer"]
release = get_version("epicsarchiver-mgmt-client")
version = ".".join(release.split(".")[0:2])


# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx_click",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "autoapi.extension",
    "sphinx_copybutton",
    "sphinx.ext.napoleon",
    "myst_parser",
]

templates_path = ["_templates"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autoapi_dirs = ["../../src/epicsarchiver_mgmt"]

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"

html_static_path: list[str] = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "arch-retrieval": ("https://epicsarchiver-retrieval-client.readthedocs.io/en/latest/", None),
    "epicsarchiverap": ("https://epicsarchiver.readthedocs.io/en/latest/", None),
    "epics-controls": ("https://docs.epics-controls.org/en/latest/", None),
}

# Enable special syntax for admonitions (:::{directive})
myst_admonition_enable = True

# Enable definition lists (Term\n: Definition)
myst_deflist_enable = True

# Allow colon fencing of directives
myst_enable_extensions = [
    "colon_fence",
]

suppress_warnings = ["ref.python"]
