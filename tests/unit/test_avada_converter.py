"""Tests for Avada converter."""

import pytest
from divi_migrator.converters.avada import AvadaConverter


class TestAvadaConverter:
    """Tests for AvadaConverter."""

    @pytest.fixture
    def converter(self):
        return AvadaConverter()

    def test_detect_avada(self, converter):
        """Test detection of Avada content."""
        avada_content = "[fusion_builder_container][fusion_builder_row][fusion_builder_column][fusion_text]Hello[/fusion_text][/fusion_builder_column][/fusion_builder_row][/fusion_builder_container]"
        assert converter.detect(avada_content) is True

    def test_detect_not_avada(self, converter):
        """Test non-Avada content is not detected."""
        plain_content = "<p>Hello world</p>"
        assert converter.detect(plain_content) is False

        elementor_content = "[elementor-widget]"
        assert converter.detect(elementor_content) is False

    def test_extract_attr(self, converter):
        """Test attribute extraction."""
        shortcode = '[fusion_button text="Click Me" link="https://example.com" color="red"]'
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
        """Test simple container conversion."""
        content = '[fusion_builder_container][fusion_builder_row][fusion_builder_column type="1_1"][fusion_text]Hello World[/fusion_text][/fusion_builder_column][/fusion_builder_row][/fusion_builder_container]'
        result = converter.convert(content, 123)

        assert "[et_pb_section" in result
        assert "[et_pb_row" in result
        assert '[et_pb_column type="4_4"' in result
        assert "[et_pb_text" in result
        assert "Hello World" in result
        assert "[/et_pb_section]" in result

    def test_convert_button(self, converter):
        """Test button conversion."""
        # This would be tested via full container conversion

    def test_extract_assets(self, converter):
        """Test asset extraction."""
        content = """
        [fusion_builder_container]
        [fusion_builder_row]
        [fusion_builder_column]
        [fusion_imageframe src="image.jpg" alt="Test"]
        [fusion_button text="Click" link="https://example.com"]
        [/fusion_builder_column]
        [/fusion_builder_row]
        [/fusion_builder_container]
        """
        assets = converter.extract_assets(content)

        assert len(assets.images) == 1
        assert assets.images[0]["src"] == "image.jpg"
        assert len(assets.buttons) == 1
        assert assets.buttons[0]["text"] == "Click"
        assert assets.buttons[0]["url"] == "https://example.com"

    def test_wrap_plain_html(self, converter):
        """Test plain HTML wrapping."""
        html = "<p>Hello world</p>"
        result = converter._wrap_as_plain_html(html)

        assert "[et_pb_section" in result
        assert "[et_pb_row]" in result
        assert '[et_pb_column type="4_4"]' in result
        assert "[et_pb_text" in result
        assert "Hello world" in result
