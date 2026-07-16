# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "Casualty Actuarial Society"
copyright = "2026, Casualty Actuarial Society"
author = "Casualty Actuarial Society"

extensions = [
    "myst_parser",
    "sphinx_design",
]

myst_enable_extensions = [
    "colon_fence",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The page title lives inside the raw-HTML hero banner on index.md, so the
# tracked heading structure starts at H2 - that's expected, not an error.
suppress_warnings = ["myst.header"]

# -- HTML output -------------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_title = "Casualty Actuarial Society"
html_favicon = "_static/images/favicon.png"
html_logo = "_static/images/cas-logo-horiz-reverse.png"
html_show_sourcelink = False

html_theme_options = {
    "logo": {
        "alt_text": "Casualty Actuarial Society",
        "text": "",
    },
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-nav"],
    "navbar_end": ["navbar-icon-links"],
    "navbar_align": "left",
    "navbar_persistent": ["search-button"],
    "header_links_before_dropdown": 6,
    "show_toc_level": 2,
    "show_prev_next": False,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/casact",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "LinkedIn",
            "url": "https://www.linkedin.com/company/casualty-actuarial-society",
            "icon": "fa-brands fa-linkedin",
        },
        {
            "name": "Facebook",
            "url": "https://www.facebook.com/CasualtyActuarialSociety",
            "icon": "fa-brands fa-facebook",
        },
        {
            "name": "Instagram",
            "url": "https://www.instagram.com/cas.act",
            "icon": "fa-brands fa-instagram",
        },
        {
            "name": "YouTube",
            "url": "https://www.youtube.com/user/CASwebmaster",
            "icon": "fa-brands fa-youtube",
        },
    ],
    "secondary_sidebar_items": {
        "**": [],
        "projects": ["page-toc"],
        "activities": ["page-toc"],
    },
    "footer_start": ["copyright"],
    "footer_end": [],
}

html_context = {
    "default_mode": "light",
}

html_sidebars = {
    "**": [],
}
