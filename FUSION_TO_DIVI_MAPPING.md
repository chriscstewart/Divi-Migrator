# Fusion Shortcode → Divi 5 Module Mapping

## Complete Inventory of Fusion Shortcodes Found on HelenZee.com/2026

| Fusion Shortcode | Divi 5 Module | Status | Notes |
|------------------|---------------|--------|-------|
| **Structure** |
| `fusion_builder_container` | `divi/section` | ✅ Done | Maps to section with background |
| `fusion_builder_row` | `divi/row` | ✅ Done | Flex/standard row |
| `fusion_builder_column` | `divi/column` | ✅ Done | Column layouts |
| `fusion_builder_row_inner` | `divi/row` (inner) | ✅ Done | Nested rows |
| `fusion_builder_column_inner` | `divi/column` (inner) | ✅ Done | Nested columns |
| **Content** |
| `fusion_text` | `divi/text` | ✅ Done | Rich text |
| `fusion_title` | `divi/heading` | ✅ Done | H1-H6 headings |
| `fusion_separator` | `divi/divider` | ✅ Done | Horizontal rules |
| `fusion_button` | `divi/button` | ✅ Done | Buttons with links |
| **Media** |
| `fusion_imageframe` | `divi/image` | ✅ Done | Single images |
| `fusion_image` | `divi/image` | ⚠️ Partial | Similar to imageframe |
| `fusion_images` | `divi/gallery` | ⚠️ Partial | Multiple images |
| `fusion_gallery` | `divi/gallery` | ⚠️ Placeholder | Gallery grid |
| `fusion_gallery_image` | `divi/image` | ⚠️ Child | Gallery items |
| `fusion_youtube` | `divi/video` | ✅ Done | YouTube videos |
| `fusion_vimeo` | `divi/video` | ✅ Done | Vimeo videos |
| `fusion_video` | `divi/video` | ✅ Done | Self-hosted video |
| `fusion_countdown` | `divi/countdown-timer` | ⚠️ New | Countdown timer |
| **Social** |
| `fusion_social_links` | `divi/social-media-follow` | ✅ Done | Social icons |
| `fusion_fontawesome` | `divi/icon` | ⚠️ Partial | Font Awesome icons |
| **Testimonials/Team** |
| `fusion_testimonial` | `divi/testimonial` | ✅ Done | Single testimonial |
| `fusion_testimonials` | `divi/testimonial` (multiple) | ✅ Done | Wrapper → multiple testimonials |
| `fusion_person` | `divi/team-member` | ⚠️ New | Person/team member |
| **Advanced Layout** |
| `fusion_content_box` | `divi/blurb` | ⚠️ Partial | Content box = blurb |
| `fusion_content_boxes` | `divi/blurb` (multiple) | ⚠️ New | Wrapper → multiple blurbs |
| `fusion_tabs` / `fusion_tab` | `divi/tabs` / `divi/tab` | ⚠️ New | Tabbed content |
| `fusion_faq` | `divi/accordion` | ⚠️ New | FAQ = accordion |
| `fusion_checklist` | `divi/icon-list` | ⚠️ New | Checklist with icons |
| `fusion_events` | `divi/blog` / custom | ❌ Complex | Events calendar |
| `fusion_blog` | `divi/blog` | ⚠️ New | Blog feed |
| `fusion_code` | `divi/code` | ⚠️ New | Code block |
| `fusion_global` | Library/Global | ❌ N/A | Global elements |
| `fusion_woo_shortcodes` | WooCommerce modules | ❌ E-commerce | WC integration |
| `fusion_li_item` | List item | ⚠️ Child | List items |
| `fusion_map` | `divi/map` | ✅ Done | Google Maps |

## Priority Recommendations

### **High Priority (Already Working)**
- Video (YouTube/Vimeo) → `divi/video` ✅
- Testimonials → `divi/testimonial` ✅
- Social Links → `divi/social-media-follow` ✅
- Images → `divi/image` ✅
- Map → `divi/map` ✅
- Text/Title/Button/Separator → Basic modules ✅

### **Medium Priority (Partial/Need Implementation)**
1. **Person/Team Member** → `divi/team-member` (Dedicated module!)
2. **Content Box/Boxes** → `divi/blurb` (Very similar pattern)
3. **Tabs** → `divi/tabs` + `divi/tab` (Direct mapping)
4. **FAQ** → `divi/accordion` (Perfect match)
5. **Countdown** → `divi/countdown-timer` (Direct mapping)
6. **Gallery** → `divi/gallery` (Direct mapping)
7. **Blog** → `divi/blog` (Direct mapping)

### **Low Priority / Complex**
- Events → Custom/Calendar (No direct equivalent)
- WooCommerce → Skip (Different plugin)
- Global → Library items (Not page content)
- Checklist → `divi/icon-list` (Doable)

## Implementation Approach

For each new mapping, follow the proven pattern:
1. Add pattern to AvadaConverter
2. Add `_convert_{shortcode}_to_block` method
3. Use `divi5_blocks` generator function
4. Test with module/update endpoint if needed
5. Add to cleanup patterns in `_convert_column_to_blocks`