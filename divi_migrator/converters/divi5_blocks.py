#!/usr/bin/env python
"""
Divi 5 Block Generators

Generates proper Divi 5 block markup with schema-compliant structure.
All blocks use `<!-- wp:divi/... -->` format with proper `module` wrapper,
`builderVersion: "5.9.0"`, and `innerContent` structured as `[{"desktop": {"value": "..."}}]`.
"""

import json
import re
from typing import Any


# =============================================================================
# CORE UTILITIES
# =============================================================================


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def make_block(block_type: str, attrs: dict[str, Any], inner: str = "", is_self_closing: bool = False) -> str:  # noqa: E501
    """Create a Divi 5 block comment with attributes.

    In real Divi 5 the block comment carries top-level keys such as
    ``builderVersion`` plus module-specific content keys (e.g. ``content``,
    ``button``, ``image``) as siblings of ``module``. Container blocks
    (section/row/column) keep ``builderVersion`` at the top level too.
    """
    if "module" not in attrs and not is_self_closing:
        raise ValueError(f"Block attributes must contain 'module' key for {block_type}")  # noqa: TRY003

    # builderVersion is a top-level attribute in real Divi 5 blocks.
    attrs = dict(attrs)
    if "builderVersion" not in attrs:
        attrs["builderVersion"] = "5.9.0"

    attrs_json = json.dumps(attrs, ensure_ascii=False, separators=(",", ":"))

    if is_self_closing:
        return f"<!-- wp:{block_type} {attrs_json} /-->"
    # For non-self-closing, always use open/close format even with empty inner
    return f"<!-- wp:{block_type} {attrs_json} -->{inner}<!-- /wp:{block_type} -->"


def placeholder(inner: str) -> str:
    """Wrap content in divi/placeholder wrapper (required for Divi 5).

    Real Divi 5 placeholders are empty self-closing comments with no attrs.
    """
    return "<!-- wp:divi/placeholder -->" + inner + "<!-- /wp:divi/placeholder -->"


# =============================================================================
# SECTION BLOCKS
# =============================================================================


def _section_module(bg: dict[str, Any] | None = None, spacing: dict[str, Any] | None = None) -> dict[str, Any]:  # noqa: E501
    """Build section module attributes."""
    m: dict[str, Any] = {
        "decoration": {
            "layout": {"desktop": {"value": {"display": "block"}}},
            "spacing": {"desktop": {"value": {}}},
        }
    }
    # Real Divi 5 omits the `background` key entirely when there is none. When
    # present, the value is a canonical object whose `color`/`image` keys are
    # themselves responsive breakpoint objects (see build_background). An
    # over-nested or partial background makes Divi 5's background renderer
    # fatal on save/preview (verified: array_keys() crash on malformed bg).
    if bg:
        m["decoration"]["background"] = bg
    if spacing:
        m["decoration"]["spacing"]["desktop"]["value"] = spacing
    return m


def build_background(
    color: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any] | None:
    """Build a canonical Divi 5 background object.

    Divi 5 expects `color`/`image` as direct children of `background`, each a
    responsive breakpoint object:
        {"color": {"desktop": {"value": "#770000"}}}
        {"image": {"desktop": {"value": {"src": URL, "url": URL}}}}
    Returns None when neither is supplied (callers then omit the key).
    """
    if not color and not image_url:
        return None
    bg: dict[str, Any] = {}
    if color:
        bg["color"] = {"desktop": {"value": color}}
    if image_url:
        bg["image"] = {"desktop": {"value": {"src": image_url, "url": image_url}}}
    return bg


def section(
    inner: str,
    bg_color: str | None = None,
    bg_image: dict[str, Any] | None = None,
    spacing: dict[str, Any] | None = None,
    **attrs: Any,
) -> str:
    """Create a divi/section block."""
    img = bg_image.get("src") if isinstance(bg_image, dict) else bg_image
    bg = build_background(color=bg_color, image_url=img)
    m = {"module": _section_module(bg, spacing)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/section", m, inner=inner, is_self_closing=False)


def section_bg_color(color: str, inner: str = "", **attrs: Any) -> str:
    """Create a section with background color."""
    return section(inner, bg_color=color, **attrs)


def section_bg_image(image: dict[str, Any], inner: str = "", **attrs: Any) -> str:
    """Create a section with background image."""
    return section(inner, bg_image=image, **attrs)


# =============================================================================
# ROW BLOCKS
# =============================================================================


def _row_module(
    column_structure: str = "4_4",
    flex: dict[str, Any] | None = None,
    spacing: dict[str, Any] | None = None,
    background: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build row module attributes."""
    m: dict[str, Any] = {
        "advanced": {
            "columnStructure": {"desktop": {"value": column_structure}},
            "flexColumnStructure": {"desktop": {"value": "equal-columns_2"}},
        },
        "decoration": {
            "layout": {
                "desktop": {"value": {"display": "flex", "flexWrap": "nowrap", "alignItems": "center"}},  # noqa: E501
                "phone": {"value": {"flexWrap": "wrap"}},
                "phoneWide": {"value": {"flexWrap": "wrap"}},
            },
        },
    }
    if flex:
        m["decoration"]["layout"] = flex
    if spacing:
        m["decoration"]["spacing"] = spacing
    if background:
        m["decoration"]["background"] = background
    return m


def row(inner: str, columns: str = "4_4", **attrs: Any) -> str:
    """Create a divi/row block."""
    m = {"module": _row_module(columns)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/row", m, inner=inner, is_self_closing=False)


def row_flex(
    inner: str,
    column_structure: str = "4_4",
    flex: dict[str, Any] | None = None,
    background_color: str | None = None,
    background_image: dict[str, Any] | None = None,
    **attrs: Any,
) -> str:
    """Create a flex row with optional background."""
    img = background_image.get("src") if isinstance(background_image, dict) else background_image
    bg = build_background(color=background_color, image_url=img)
    m = {"module": _row_module(column_structure, flex, background=bg)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/row", m, inner=inner, is_self_closing=False)


# =============================================================================
# COLUMN BLOCKS
# =============================================================================


def _column_module(layout: str = "4_4", module_attrs: dict[str, Any] | None = None) -> dict[str, Any]:  # noqa: E501
    """Build column module attributes."""
    m: dict[str, Any] = {
        "advanced": {
            "type": {"desktop": {"value": layout}},
        },
        "decoration": {
            "sizing": {
                "desktop": {"value": {"flexType": "24_24"}},
                "phone": {"value": {"flexType": "24_24"}},
                "phoneWide": {"value": {"flexType": "24_24"}},
            }
        },
    }
    if module_attrs:
        m = _deep_merge(m, module_attrs)
    return m


def column(inner: str, layout: str = "4_4", module: dict[str, Any] | None = None, **attrs: Any) -> str:  # noqa: E501
    """Create a divi/column block."""
    m = {"module": _column_module(layout, module)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/column", m, inner=inner, is_self_closing=False)


# =============================================================================
# TEXT BLOCKS
# =============================================================================


def linkify_bare_urls(html: str) -> str:
    """Turn bare URLs in text into clickable <a> links.

    Only links a URL when it is NOT already inside an existing attribute
    (href/src) or inside an <a> tag (preceded by >). Existing links and image
    src URLs are left untouched.
    """
    # Negative lookbehind: not preceded by a quote/=/angle that would mean the
    # URL is already part of an attribute or an existing anchor's text.
    pattern = r'(?<!["\'=>])(https?://[^\s<>"\']+)'
    return re.sub(pattern, r'<a href="\1">\1</a>', html)


def _text_module(html: str) -> dict[str, Any]:
    """Build text block attributes (top-level ``content`` + ``module``)."""
    return {
        "content": {
            "innerContent": {
                "desktop": {"value": html}
            }
        },
        "module": {
            "decoration": {
                "layout": {"desktop": {"value": {"justifyContent": "start"}}},
                "spacing": {
                    "desktop": {
                        "value": {
                            "padding": {
                                "bottom": "1em",
                                "syncVertical": "off",
                                "syncHorizontal": "off",
                            }
                        }
                    }
                },
            }
        },
    }


def text(html: str, **attrs: Any) -> str:
    """Create a divi/text block."""
    m = _text_module(linkify_bare_urls(html))
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/text", m, is_self_closing=True)


# =============================================================================
# HEADING BLOCKS
# =============================================================================


def _heading_module(text_content: str, level: str = "h2", color: str | None = None, alignment: str = "left") -> dict[str, Any]:  # noqa: E501
    """Build heading block attributes (top-level ``title`` + ``module``)."""
    m: dict[str, Any] = {
        "title": {
            "innerContent": {
                "desktop": {"value": text_content}
            },
            "decoration": {
                "font": {
                    "font": {
                        "desktop": {"value": {"headingLevel": level}}
                    }
                }
            },
        },
        "module": {
            "decoration": {
                "layout": {"desktop": {"value": {"justifyContent": alignment}}}
            }
        },
    }
    if color:
        m["title"]["decoration"]["font"]["font"]["desktop"]["value"]["color"] = color
    return m


def heading(text_content: str, level: str = "h2", color: str | None = None, alignment: str = "left", **attrs: Any) -> str:  # noqa: E501
    """Create a divi/heading block."""
    m = _heading_module(text_content, level, color, alignment)
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/heading", m, is_self_closing=True)


# =============================================================================
# BUTTON BLOCKS
# =============================================================================


def _button_module(text_content: str, url: str, color: str = "#e8cb90", alignment: str = "center") -> dict[str, Any]:  # noqa: E501
    """Build button block attributes (top-level ``button`` + ``module``)."""
    return {
        "button": {
            "innerContent": {
                "desktop": {"value": text_content}
            },
            "url": {"desktop": {"value": url}},
            "color": {"desktop": {"value": color}},
            "alignment": {"desktop": {"value": alignment}},
            "sizing": {
                "desktop": {"value": {"width": "auto", "minWidth": "0"}},
                "phone": {"value": {"width": "100%", "minWidth": "0"}},
                "phoneWide": {"value": {"width": "100%", "minWidth": "0"}},
            },
        },
        "module": {
            "decoration": {
                "layout": {"desktop": {"value": {"display": "flex"}}}
            }
        },
    }


def button(text_content: str, url: str, color: str = "#e8cb90", alignment: str = "center", **attrs: Any) -> str:  # noqa: E501
    """Create a divi/button block."""
    m = _button_module(text_content, url, color, alignment)
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/button", m, is_self_closing=True)


# =============================================================================
# IMAGE BLOCKS
# =============================================================================


def _image_module(src: str, alt: str = "", link: str | None = None) -> dict[str, Any]:
    """Build image block attributes (top-level ``image`` + ``module``)."""
    m: dict[str, Any] = {
        "image": {
            "innerContent": {
                "desktop": {"value": {"src": src, "alt": alt}}
            }
        },
        "module": {
            "decoration": {
                "attributes": {
                    "attributes": [],
                    "desktop": {"value": {"attributes": []}},
                }
            }
        },
    }
    if link:
        m["image"]["innerContent"]["desktop"]["value"]["link"] = link
    return m


def image(src: str, alt: str = "", link: str | None = None, **attrs: Any) -> str:
    """Create a divi/image block."""
    m = _image_module(src, alt, link)
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/image", m, is_self_closing=True)


# =============================================================================
# DIVIDER BLOCKS
# =============================================================================


def _divider_module(style: str = "solid", alignment: str = "center", color: str | None = None) -> dict[str, Any]:  # noqa: E501
    """Build divider block attributes (top-level ``divider`` + ``module``)."""
    m: dict[str, Any] = {
        "divider": {
            "decoration": {
                "divider": {
                    "desktop": {"value": {"style": style, "alignment": alignment}}
                }
            }
        },
        "module": {
            "decoration": {
                "spacing": {
                    "desktop": {"value": {"margin": {"top": "1em", "bottom": "1em"}}}
                }
            }
        },
    }
    if color:
        m["divider"]["decoration"]["divider"]["desktop"]["value"]["color"] = color
    return m


def divider(style: str = "solid", alignment: str = "center", color: str | None = None, **attrs: Any) -> str:  # noqa: E501
    """Create a divi/divider block."""
    m = _divider_module(style, alignment, color)
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/divider", m, is_self_closing=True)


# =============================================================================
# BLURB BLOCKS
# =============================================================================


def _blurb_module(title: str, content: str, icon: str | None = None, image: str | None = None, url: str | None = None) -> dict[str, Any]:  # noqa: E501
    """Build blurb block attributes (top-level title/content/imageIcon + module)."""
    m: dict[str, Any] = {
        "title": {
            "innerContent": {"desktop": {"value": title}},
            "decoration": {"font": {"font": {"desktop": {"value": {"headingLevel": "h4"}}}}},
        },
        "content": {
            "innerContent": {"desktop": {"value": content}}
        },
        "module": {
            "decoration": {
                "layout": {"desktop": {"value": {"justifyContent": "center"}}}
            }
        },
    }
    if icon:
        m["imageIcon"] = {
            "innerContent": {
                "desktop": {
                    "value": {
                        "useIcon": "on",
                        "icon": {"unicode": icon, "type": "fa", "weight": "900"},
                    }
                }
            }
        }
    if image:
        m["imageIcon"] = {
            "innerContent": {
                "desktop": {"value": {"src": image, "useIcon": "off"}}
            }
        }
    if url:
        m.setdefault("module", {})["link"] = {"desktop": {"value": url}}
    return m


def blurb(title: str, content: str, icon: str | None = None, image: str | None = None, url: str | None = None, **attrs: Any) -> str:  # noqa: E501
    """Create a divi/blurb block."""
    m = _blurb_module(title, content, icon, image, url)
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/blurb", m, is_self_closing=True)


# =============================================================================
# VIDEO BLOCKS
# =============================================================================


def _video_module(src: str, type_: str = "youtube") -> dict[str, Any]:
    """Build video module attributes."""
    return {
        "video": {
            "innerContent": {
                "desktop": {"value": {"src": src, "type": type_}}
            }
        }
    }


def video(src: str, type_: str = "youtube", **attrs: Any) -> str:
    """Create a divi/video block."""
    m = {"module": _video_module(src, type_)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/video", m, is_self_closing=True)


# =============================================================================
# MAP BLOCKS
# =============================================================================


def _map_module(center: dict[str, Any] | None = None, zoom: int = 10) -> dict[str, Any]:
    """Build map module attributes."""
    m: dict[str, Any] = {
        "map": {
            "center": center or {"lat": 0, "lng": 0},
            "zoom": zoom,
        }
    }
    return m


def map_module(center: dict[str, Any] | None = None, zoom: int = 10, **attrs: Any) -> str:
    """Create a divi/map block."""
    m = {"module": _map_module(center, zoom)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/map", m, is_self_closing=True)


# =============================================================================
# TESTIMONIALS MODULE - Uses divi/slider with divi/slide items
# =============================================================================


def _testimonials_module(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build testimonials module attributes using slider with slide items."""
    slide_items = []
    for item in items:
        content = item.get("content", "")
        author = item.get("name", "")
        # Create testimonial HTML for each slide
        testimonial_html = f"""
        <div class="et_pb_testimonial">
            <div class="et_pb_testimonial_description">{content}</div>
            <div class="et_pb_testimonial_author">{author}</div>
        </div>
        """.strip()
        slide_items.append({
            "content": testimonial_html
        })

    return {
        "slider": {
            "advanced": {
                "auto": "on",
                "autoSpeed": "5000",
                "autoIgnoreHover": "off"
            },
            "decoration": {
                "animation": {
                    "desktop": {"value": {"style": "fade", "delay": "0ms"}}
                }
            }
        }
    }


def testimonials(items: list[dict[str, Any]], **attrs: Any) -> str:
    """Create a divi/slider block with testimonial slides."""
    # Build the slider module
    m = {"module": _testimonials_module(items)}
    if attrs:
        m = _deep_merge(m, attrs)

    # Create slide blocks as siblings
    slide_blocks = []
    for item in items:
        content = item.get("content", "")
        author = item.get("name", "")
        testimonial_html = f"""
        <div class="et_pb_testimonial">
            <div class="et_pb_testimonial_description">{content}</div>
            <div class="et_pb_testimonial_author">{author}</div>
        </div>
        """.strip()
        escaped_html = testimonial_html.replace('"', '\\"')
        slide_blocks.append(f'<!-- wp:divi/slide {{"module":{{"slide":{{"innerContent":{{"desktop":{{"value":"{escaped_html}"}}}}}}}},"builderVersion":"5.9.0"}} /-->')  # noqa: E501

    # Build slider opening tag manually (not self-closing)
    m_json = json.dumps(m, ensure_ascii=False, separators=(",", ":"))
    slider_open = f"<!-- wp:divi/slider {m_json} -->"
    slides_content = "".join(slide_blocks)
    slider_close = "<!-- /wp:divi/slider -->"

    return slider_open + slides_content + slider_close


# =============================================================================
# SOCIAL FOLLOW BLOCKS
# =============================================================================# =============================================================================  # noqa: E501
# SOCIAL FOLLOW BLOCKS
# =============================================================================


def _social_follow_module(networks: list[dict[str, Any]]) -> dict[str, Any]:
    """Build social follow module attributes."""
    items = []
    for net in networks:
        network = net.get("network", "")
        url = net.get("url", "")
        if network and url:
            items.append({
                "network": network,
                "url": url,
                "label": network.title(),
                "icon": {"enable": "on"}
            })
    return {
        "socialFollow": {
            "items": items
        }
    }


def social_follow(networks: list[dict[str, Any]], **attrs: Any) -> str:
    """Create a divi/social_follow block."""
    m = {"module": _social_follow_module(networks)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/social_follow", m, is_self_closing=True)


# =============================================================================
# TEAM MEMBER BLOCKS (for fusion_person)
# =============================================================================


def _team_member_module(name: str = "", position: str = "", content: str = "", image: str = "", social: dict[str, Any] | None = None) -> dict[str, Any]:  # noqa: E501
    """Build team member module attributes."""
    m: dict[str, Any] = {
        "teamMember": {
            "innerContent": {
                "desktop": {"value": content}
            }
        }
    }
    if name:
        m["teamMember"]["name"] = {"desktop": {"value": name}}
    if position:
        m["teamMember"]["position"] = {"desktop": {"value": position}}
    if image:
        m["teamMember"]["image"] = {"desktop": {"value": {"src": image}}}
    if social:
        # social contains facebookUrl, twitterUrl, linkedinUrl, instagramUrl, etc.
        social_items: dict[str, dict[str, dict[str, Any]]] = {}
        for key, url in social.items():
            if url:
                social_items[key] = {"desktop": {"value": url}}
        if social_items:
            m["teamMember"]["social"] = social_items
    return m


def team_member(name: str = "", position: str = "", content: str = "", image: str = "", social: dict[str, Any] | None = None, **attrs: Any) -> str:  # noqa: E501
    """Create a divi/team-member block."""
    m = {"module": _team_member_module(name, position, content, image, social)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/team-member", m, is_self_closing=True)


# =============================================================================
# ACCORDION BLOCKS (for fusion_faq)
# =============================================================================


def _accordion_module() -> dict[str, Any]:
    """Build accordion module attributes."""
    return {
        "accordion": {
            "decoration": {
                "animation": {
                    "desktop": {"value": {"style": "fade", "delay": "0ms"}}
                }
            }
        }
    }


def accordion(inner: str = "", **attrs: Any) -> str:
    """Create a divi/accordion block."""
    m = {"module": _accordion_module()}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/accordion", m, inner=inner, is_self_closing=False)


def _accordion_item_module(title: str = "", content: str = "") -> dict[str, Any]:
    """Build accordion item module attributes."""
    return {
        "accordionItem": {
            "innerContent": {
                "desktop": {"value": content}
            },
            "title": {"desktop": {"value": title}}
        }
    }


def accordion_item(title: str = "", content: str = "", **attrs: Any) -> str:
    """Create a divi/accordion-item block (child of accordion)."""
    m = {"module": _accordion_item_module(title, content)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/accordion-item", m, is_self_closing=True)


# =============================================================================
# TABS BLOCKS (for fusion_tabs / fusion_tab)
# =============================================================================


def _tabs_module() -> dict[str, Any]:
    """Build tabs module attributes."""
    return {
        "tabs": {
            "decoration": {
                "animation": {
                    "desktop": {"value": {"style": "fade", "delay": "0ms"}}
                }
            }
        }
    }


def tabs(inner: str = "", **attrs: Any) -> str:
    """Create a divi/tabs block."""
    m = {"module": _tabs_module()}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/tabs", m, inner=inner, is_self_closing=False)


def _tab_module(title: str = "", content: str = "") -> dict[str, Any]:
    """Build tab module attributes."""
    return {
        "tab": {
            "innerContent": {
                "desktop": {"value": content}
            },
            "title": {"desktop": {"value": title}}
        }
    }


def tab(title: str = "", content: str = "", **attrs: Any) -> str:
    """Create a divi/tab block (child of tabs)."""
    m = {"module": _tab_module(title, content)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/tab", m, is_self_closing=True)


# =============================================================================
# COUNTDOWN TIMER BLOCK (for fusion_countdown)
# =============================================================================


def _countdown_module(number: str = "", title: str = "", label: str = "", separator: str = "") -> dict[str, Any]:  # noqa: E501
    """Build countdown timer module attributes."""
    return {
        "countdownTimer": {
            "number": {"desktop": {"value": number}},
            "title": {"desktop": {"value": title}},
            "label": {"desktop": {"value": label}},
            "separator": {"desktop": {"value": separator}}
        }
    }


def countdown_timer(number: str = "", title: str = "", label: str = "", separator: str = "", **attrs: Any) -> str:  # noqa: E501
    """Create a divi/countdown-timer block."""
    m = {"module": _countdown_module(number, title, label, separator)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/countdown-timer", m, is_self_closing=True)


# =============================================================================
# GALLERY BLOCK (for fusion_gallery)
# =============================================================================


def _gallery_module(images: list[str] | None = None) -> dict[str, Any]:
    """Build gallery module attributes."""
    return {
        "gallery": {
            "images": images or []
        }
    }


def gallery(images: list[str] | None = None, **attrs: Any) -> str:
    """Create a divi/gallery block."""
    m = {"module": _gallery_module(images)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/gallery", m, is_self_closing=True)


# =============================================================================
# BLOG BLOCK (for fusion_blog)
# =============================================================================


def _blog_module() -> dict[str, Any]:
    """Build blog module attributes."""
    return {
        "blog": {
            "postsNumber": {"desktop": {"value": 10}},
            "includeCategories": {"desktop": {"value": []}},
            "offsetNumber": {"desktop": {"value": 0}}
        }
    }


def blog(**attrs: Any) -> str:
    """Create a divi/blog block."""
    m = {"module": _blog_module()}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/blog", m, is_self_closing=True)


# =============================================================================
# ICON LIST BLOCK (for fusion_checklist)
# =============================================================================


def _icon_list_module(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build icon list module attributes."""
    return {
        "iconList": {
            "items": items or []
        }
    }


def icon_list(items: list[dict[str, Any]] | None = None, **attrs: Any) -> str:
    """Create a divi/icon-list block."""
    m = {"module": _icon_list_module(items)}
    if attrs:
        m = _deep_merge(m, attrs)
    return make_block("divi/icon-list", m, is_self_closing=True)


# =============================================================================
# CLEAN HTML UTILITY
# =============================================================================


def _clean_html(content: str) -> str:
    """Clean HTML content (fix smart quotes, etc.)."""
    if not content:
        return ""
    content = content.replace("\u201c", '"').replace("\u201d", '"')
    content = content.replace("\u2018", "'").replace("\u2019", "'")
    content = content.replace("\u00d7", "x")
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    return content.strip()

