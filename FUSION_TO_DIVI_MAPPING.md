# Fusion Shortcode → Divi 5 Module Mapping

> **Status: verified against `divi_migrator/converters/avada.py` and
> `divi5_blocks.py` as of v0.1.2.** This is the authoritative capability map.

## How conversion works on this host

Avada (Fusion Builder) shortcodes are converted to **Divi 5 block markup**
(`<!-- wp:divi/... -->`). Two emission strategies are used:

- **Native Divi 5 module** — emitted as the real `divi/<module>` block. Renders
  directly from `post_content` in Divi 5.
- **Semantic HTML inside a `divi/text` block** — used for modules whose native
  Divi 5 equivalent **does not render from raw `post_content` markup on this
  shared host** (verified 2026-08). These are emitted as clean, styled HTML
  inside a Divi text block so they display reliably. They are fully readable and
  editable in the Divi Visual Builder, just not as the dedicated module type.

## Structure & content

| Fusion Shortcode | Divi 5 Target | Status | Notes |
|------------------|---------------|--------|-------|
| `fusion_builder_container` | `divi/section` | ✅ Native | Section with background |
| `fusion_builder_row` | `divi/row` | ✅ Native | Flex/standard row |
| `fusion_builder_column` | `divi/column` | ✅ Native | Column layouts |
| `fusion_builder_row_inner` | `divi/row` (inner) | ✅ Native | Nested rows |
| `fusion_builder_column_inner` | `divi/column` (inner) | ✅ Native | Nested columns |
| `fusion_text` | `divi/text` | ✅ Native | Rich text |
| `fusion_title` | `divi/heading` | ✅ Native | H1–H6 headings |
| `fusion_separator` | `divi/divider` | ✅ Native | Horizontal rule |
| `fusion_button` | `divi/button` | ✅ Native | Button with link |
| `fusion_imageframe` | `divi/image` | ✅ Native | Single image |
| `fusion_image` | `divi/image` | ✅ Native | Single image (also imageframe) |
| `fusion_images` | `divi/gallery` | ✅ Native | Multiple images |
| `fusion_gallery` | `divi/gallery` | ✅ Native | Gallery grid |
| `fusion_gallery_image` | `divi/image` | ✅ Native | Gallery child item |
| `fusion_youtube` | `divi/video` | ✅ Native | YouTube embed |
| `fusion_vimeo` | `divi/video` | ✅ Native | Vimeo embed |
| `fusion_video` | `divi/video` | ✅ Native | Self-hosted video |
| `fusion_social_links` | `divi/social-media-follow` | ✅ Native | Social icons |
| `fusion_fontawesome` | HTML icon in `divi/text` | ✅ Converted | Emitted as styled HTML (native `divi/icon` does not render headless here) |
| `fusion_testimonial` | `divi/testimonial` | ✅ Native | Single testimonial |
| `fusion_testimonials` | `divi/testimonial` (multiple) | ✅ Native | Wrapper → multiple testimonials |
| `fusion_map` | `divi/map` | ✅ Native | Google Map |
| `fusion_person` | HTML profile card in `divi/text` | ✅ Converted | Name/title/bio/socials as semantic HTML (native `divi/team-member` does not render headless here) |
| `fusion_content_box` | `divi/blurb` | ✅ Native | Content box → blurb |
| `fusion_content_boxes` | `divi/blurb` (multiple) | ✅ Native | Wrapper → multiple blurbs |
| `fusion_tabs` / `fusion_tab` | HTML `<details>` accordion in `divi/text` | ✅ Converted | Native `divi/tabs` does not render headless here; emitted as stacked panels |
| `fusion_faq` / `fusion_toggles` | HTML `<details>` accordion in `divi/text` | ✅ Converted | Native `divi/accordion` does not render headless here |
| `fusion_checklist` | `divi/icon-list` | ✅ Native | Checklist with icons |
| `fusion_countdown` | `divi/countdown-timer` | ✅ Native | Countdown timer |
| `fusion_blog` | `divi/blog` | ✅ Native | Blog feed |
| `fusion_code` | HTML `<pre>`/`code` in `divi/text` | ✅ Converted | Code block content preserved as styled HTML |
| `fusion_raw` | `divi/text` (raw HTML) | ✅ Converted | Raw HTML passed through |
| `fusion_li_item` | List item (within text/checklist) | ✅ Converted | Child of list containers |

## Not converted (excluded by design)

| Fusion Shortcode | Reason |
|------------------|-------|
| `fusion_events` | Emitted best-effort as HTML; full Events Calendar mapping is out of scope (no direct Divi equivalent). |
| `fusion_woo_shortcodes` | WooCommerce modules excluded — different plugin/ecosystem. |
| `fusion_global` | Global/library elements are not page content; skipped. |

## Notes for maintainers

- Every `_convert_*` method in `avada.py` maps to a generator in `divi5_blocks.py`.
- When adding a new mapping: add the shortcode pattern + `_convert_<x>_to_block`
  method in `avada.py`, add/use the generator in `divi5_blocks.py`, and update
  this table.
- "Does not render headless" refers to the Divi 5 headless/REST render path on
  the target shared host; the Visual Builder may still render native modules.
  The HTML-fallback strategy guarantees the content is visible after migration
  regardless.
