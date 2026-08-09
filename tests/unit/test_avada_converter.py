"""Tests for Avada converter."""

import pytest
from typing import Any

from divi_migrator.converters.avada import AvadaConverter

# Test constants
MIN_PASSWORD_LENGTH = 16
DEFAULT_YOUTUBE_ID = "dQw4w9WgXcQ"
DEFAULT_YOUTUBE_URL = f"https://www.youtube.com/watch?v={DEFAULT_YOUTUBE_ID}"
DEFAULT_VIMEO_ID = "123456789"
EXPECTED_IMAGE_SRC = "123|medium"
EXPECTED_IMAGE_ALT = "Test Image"


class TestAvadaConverter:
    """Tests for AvadaConverter."""

    @pytest.fixture
    def converter(self):
        return AvadaConverter()

    def test_detect_avada(self, converter):
        """Test detection of Avada content."""
        avada_content = (
            "[fusion_builder_container][fusion_builder_row]"
            "[fusion_builder_column][fusion_text]Hello[/fusion_text]"
            "[/fusion_builder_column][/fusion_builder_row][/fusion_builder_container]"
        )
        assert converter.detect(avada_content) is True

    def test_detect_not_avada(self, converter):
        """Test non-Avada content is not detected."""
        plain_content = "<p>Hello world</p>"
        assert converter.detect(plain_content) is False

        elementor_content = "[elementor-widget]"
        assert converter.detect(elementor_content) is False

    def test_extract_attr(self, converter):
        """Test attribute extraction."""
        shortcode = (
            '[fusion_button text="Click Me" link="https://example.com" color="red"]'
        )
        assert converter.extract_attr(shortcode, "text") == "Click Me"
        assert converter.extract_attr(shortcode, "link") == "https://example.com"
        assert converter.extract_attr(shortcode, "color") == "red"
        assert converter.extract_attr(shortcode, "missing") is None

    def test_clean_attrs(self, converter):
        """Test attribute cleaning."""
        attrs = {
            "text": "Hello \u201cWorld\u201d",
            "size": "12\u00d724",
        }
        cleaned = converter.clean_attrs(attrs)
        assert cleaned["text"] == 'Hello "World"'
        assert cleaned["size"] == "12x24"

    def test_column_map(self, converter):
        """Test column type mapping."""
        assert converter.COLUMN_MAP["1_1"] == "4_4"
        assert converter.COLUMN_MAP["1_2"] == "2_4"
        assert converter.COLUMN_MAP["1_3"] == "3_12"
        assert converter.COLUMN_MAP["1_4"] == "2_12"
        assert converter.COLUMN_MAP["3_4"] == "9_12"
        assert converter.COLUMN_MAP["1_5"] == "1_5"
        assert converter.COLUMN_MAP["1_6"] == "1_6"

    def test_convert_simple_container(self, converter):
        """Test simple container conversion to Divi 5 blocks."""
        content = (
            "[fusion_builder_container][fusion_builder_row]"
            '[fusion_builder_column type="1_1"][fusion_text]Hello World'
            "[/fusion_text][/fusion_builder_column][/fusion_builder_row]"
            "[/fusion_builder_container]"
        )
        result = converter.convert(content, 123)

        # Check for Divi 5 block markup format (native sections, no placeholder
        # wrapper — placeholder is only for foreign/non-Divi blocks).
        assert "<!-- wp:divi/section" in result
        assert "<!-- wp:divi/row" in result
        assert "<!-- wp:divi/column" in result
        assert "<!-- wp:divi/text" in result
        assert "Hello World" in result
        assert "<!-- /wp:divi/section -->" in result

    def test_convert_button(self, converter):
        """Test button conversion."""
        # This would be tested via full container conversion

    def test_extract_assets(self, converter):
        """Test asset extraction."""
        content = """
        [fusion_builder_container]
        [fusion_builder_row]
        [fusion_builder_column]
        [fusion_imageframe image_id="123|medium" alt="Test"]
        [fusion_button text="Click" link="https://example.com"]
        [/fusion_builder_column]
        [/fusion_builder_row]
        [/fusion_builder_container]
        """
        assets = converter.extract_assets(content)

        assert len(assets.images) == 1
        assert assets.images[0]["src"] == EXPECTED_IMAGE_SRC
        assert assets.images[0]["type"] == "fusion_imageframe"
        assert len(assets.buttons) == 1
        assert assets.buttons[0]["text"] == "Click"
        assert assets.buttons[0]["url"] == "https://example.com"

    def test_wrap_plain_html(self, converter):
        """Test plain HTML wrapping."""
        html = "<p>Hello world</p>"
        result = converter._wrap_as_plain_html(html)  # noqa: SLF001

        # Check for Divi 5 block markup format (native sections, no placeholder
        # wrapper — placeholder is only for foreign/non-Divi blocks).
        assert "<!-- wp:divi/section" in result
        assert "<!-- wp:divi/row" in result
        assert "<!-- wp:divi/column" in result
        assert "<!-- wp:divi/text" in result
        assert "Hello world" in result
        assert "<!-- /wp:divi/section -->" in result

    def test_youtube_conversion(self, converter):
        """Test YouTube shortcode conversion to a real divi/video module.

        fusion_youtube becomes a proper divi/video block with
        video.innerContent.desktop.value = "<url>" (plain URL string, NOT an
        object) so the URL is saved into the Video module.
        """
        content = (
            "[fusion_builder_container][fusion_builder_row]"
            "[fusion_builder_column][fusion_youtube "
            f'id="{DEFAULT_YOUTUBE_ID}"]'
            "[/fusion_builder_column][/fusion_builder_row]"
            "[/fusion_builder_container]"
        )
        result = converter.convert(content, 123)

        # Real divi/video module, normalized embed URL, no raw iframe.
        assert "wp:divi/video" in result
        assert "wp:divi/text" not in result
        assert "<iframe" not in result
        assert f"youtube.com/embed/{DEFAULT_YOUTUBE_ID}" in result

    def test_vimeo_conversion(self, converter):
        """Test Vimeo shortcode conversion to a real divi/video module.

        fusion_vimeo becomes a proper divi/video block with
        video.innerContent.desktop.value = "<url>" (plain URL string).
        """
        content = (
            "[fusion_builder_container][fusion_builder_row]"
            f'[fusion_builder_column][fusion_vimeo id="{DEFAULT_VIMEO_ID}"]'
            "[/fusion_builder_column][/fusion_builder_row]"
            "[/fusion_builder_container]"
        )
        result = converter.convert(content, 123)

        assert "wp:divi/video" in result
        assert "wp:divi/text" not in result
        assert "<iframe" not in result
        assert f"player.vimeo.com/video/{DEFAULT_VIMEO_ID}" in result

    def test_testimonial_conversion(self, converter):
        """Test testimonial conversion to blurb."""
        content = (
            "[fusion_builder_container][fusion_builder_row]"
            '[fusion_builder_column][fusion_testimonial name="John Doe" '
            'company="Acme Corp"]Great service![/fusion_testimonial]'
            "[/fusion_builder_column][/fusion_builder_row]"
            "[/fusion_builder_container]"
        )
        result = converter.convert(content, 123)

        assert "wp:divi/blurb" in result
        assert "John Doe" in result
        assert "Acme Corp" in result
        assert "Great service" in result

    def test_person_conversion(self, converter):
        """Test person conversion to a native HTML profile card in divi/text.

        divi/team-member does not render from raw post_content markup on this
        host, so a native HTML card (name, title, bio) inside divi/text is
        emitted instead.
        """
        content = (
            "[fusion_builder_container][fusion_builder_row]"
            '[fusion_builder_column][fusion_person name="Jane Smith" '
            'title="CEO" description="Leader"]'
            "[/fusion_builder_column][/fusion_builder_row]"
            "[/fusion_builder_container]"
        )
        result = converter.convert(content, 123)

        # Native HTML card inside divi/text (no team-member module).
        assert "wp:divi/text" in result
        assert "wp:divi/team-member" not in result
        assert "Jane Smith" in result
        assert "person-card" in result
        assert "CEO" in result

    def test_image_conversion(self, converter):
        """Test imageframe conversion to a real divi/image module.

        fusion_imageframe becomes a proper divi/image block with
        image.innerContent.desktop.value = {src, id, alt, titleText} so it
        renders and is editable in the Visual Builder (not a native <img>
        inside divi/text). A direct URL is used here (no WP client needed).
        """
        direct_url = "https://example.com/uploads/test.jpg"
        content = (
            "[fusion_builder_container][fusion_builder_row]"
            "[fusion_builder_column][fusion_imageframe "
            f'src="{direct_url}" alt="{EXPECTED_IMAGE_ALT}"]'
            "[/fusion_builder_column][/fusion_builder_row]"
            "[/fusion_builder_container]"
        )
        result = converter.convert(content, 123)

        assert "wp:divi/image" in result
        assert "wp:divi/text" not in result
        assert '"src"' in result
        assert direct_url in result
        assert EXPECTED_IMAGE_ALT in result

    def test_image_id_resolution(self, converter):
        """An Avada image_id (e.g. '5481|full') is resolved to the media URL."""
        class FakeClient:
            def get(self, endpoint: str, params: Any = None) -> dict[str, Any]:  # noqa: ARG002
                if endpoint == "media/5481":
                    return {"source_url": "https://example.com/wp-content/uploads/x.jpg"}
                return {}

        converter.wp_client = FakeClient()
        converter._media_cache = {}  # noqa: SLF001
        result = converter._resolve_image_src("5481|full")  # noqa: SLF001
        assert result == "https://example.com/wp-content/uploads/x.jpg"

        # With no client, an unresolvable image_id yields empty (image dropped,
        # not a broken src).
        converter.wp_client = None
        assert converter._resolve_image_src("9999|full") == ""  # noqa: SLF001

    def test_checklist_conversion(self, converter):
        """fusion_checklist -> native <ul><li> (no raw shortcodes leaked).

        DiviOps cannot populate divi/icon-list from raw markup, so the
        checklist is rendered as a standard list inside a divi/text block.
        Each [fusion_li_item] becomes one <li>; its <p>-wrapped text is
        unwrapped and HTML entities decoded.
        """
        content = (
            "[fusion_builder_container][fusion_builder_row][fusion_builder_column]"
            "[fusion_text]<p>Intro</p>[/fusion_text]"
            "[fusion_checklist type=&#8221;icons&#8221; icon=&#8221;fa-heart fas&#8221;]"
            "[fusion_li_item icon=&#8221;&#8221;]"
            "</p><p>Holistic Fertility &amp; IVF Advocacy</p><p>"
            "[/fusion_li_item]"
            "[fusion_li_item icon=&#8221;&#8221;]"
            "</p><p>Relationship and Intimacy Counselling</p><p>"
            "[/fusion_li_item]"
            "[/fusion_checklist]"
            "[/fusion_builder_column][/fusion_builder_row][/fusion_builder_container]"
        )
        result = converter.convert(content, 124)

        # No raw Avada shortcodes must survive
        assert "fusion_li_item" not in result
        assert "fusion_checklist" not in result
        # Proper list markup with decoded entity
        assert "<ul>" in result
        assert "<li>Holistic Fertility & IVF Advocacy</li>" in result
        assert "<li>Relationship and Intimacy Counselling</li>" in result
        # Renders inside a divi/text block
        assert "wp:divi/text" in result


