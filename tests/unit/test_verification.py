"""Tests for verification engine."""

from unittest.mock import Mock
from divi_migrator.core.verification import VerificationEngine


class MockDiviOpsClient:
    def __init__(self):
        self.get_page_layout = Mock()
        self.get_design_system = Mock()


class MockConfig:
    def __init__(self):
        self.verification = type(
            "obj",
            (object,),
            {
                "require_sections": True,
                "require_modules": True,
                "min_images": 0,
                "min_buttons": 0,
                "primary_color_token": "gcid-primary-color",
            },
        )()
        self.migration = type(
            "obj",
            (object,),
            {
                "rate_limit": 2.0,
                "batch_size": 50,
                "checkpoint_dir": "./checkpoints",
                "max_retries": 3,
                "timeout": 30,
            },
        )()


# Constants for test assertions
EXPECTED_SECTIONS = 1
EXPECTED_ROWS = 1
EXPECTED_MODULES = 2


def test_verify_layout_passed():
    """Test layout verification passes."""
    diviops = MockDiviOpsClient()
    config = MockConfig()
    engine = VerificationEngine(diviops, config)

    # Mock layout with valid structure
    diviops.get_page_layout.return_value = {
        "ok": True,
        "data": {
            "blocks": [
                {
                    "block_name": "divi/section",
                    "attributes": {"background_color": "gcid-primary-color"},
                    "inner_blocks": [
                        {
                            "block_name": "divi/row",
                            "inner_blocks": [
                                {
                                    "block_name": "divi/column",
                                    "inner_blocks": [{"block_name": "divi/text", "attributes": {}}],  # noqa: E501
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }

    result = engine.verify_layout(
        diviops.get_page_layout.return_value, {"images": 0, "buttons": 0, "forms": 0}
    )

    assert result.verification_passed is True
    assert result.sections == EXPECTED_SECTIONS
    assert result.rows == EXPECTED_ROWS
    # column + text = 2 modules (column is counted as module since it starts with divi/)
    assert result.modules == EXPECTED_MODULES


def test_verify_layout_no_sections():
    """Test layout verification fails with no sections."""
    diviops = MockDiviOpsClient()
    config = MockConfig()
    engine = VerificationEngine(diviops, config)

    diviops.get_page_layout.return_value = {"ok": True, "data": {"blocks": []}}

    result = engine.verify_layout(diviops.get_page_layout.return_value, {})

    assert result.verification_passed is False
    assert "No sections found" in result.issues


def test_verify_layout_missing_images():
    """Test layout verification warns about missing images."""
    diviops = MockDiviOpsClient()
    config = MockConfig()
    engine = VerificationEngine(diviops, config)

    diviops.get_page_layout.return_value = {
        "ok": True,
        "data": {
            "blocks": [
                {
                    "block_name": "divi/section",
                    "attributes": {"background_color": "gcid-primary-color"},
                    "inner_blocks": [
                        {
                            "block_name": "divi/row",
                            "inner_blocks": [
                                {
                                    "block_name": "divi/column",
                                    "inner_blocks": [{"block_name": "divi/text", "attributes": {}}],  # noqa: E501
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }

    result = engine.verify_layout(diviops.get_page_layout.return_value, {"images": 2, "buttons": 0})

    assert result.verification_passed is False
    assert any("Images" in issue for issue in result.issues)


def test_verify_layout_missing_primary_color():
    """Test layout verification warns about missing primary color."""
    diviops = MockDiviOpsClient()
    config = MockConfig()
    engine = VerificationEngine(diviops, config)

    diviops.get_page_layout.return_value = {
        "ok": True,
        "data": {
            "blocks": [
                {
                    "block_name": "divi/section",
                    "attributes": {"background_color": "#ffffff"},
                    "inner_blocks": [
                        {
                            "block_name": "divi/row",
                            "inner_blocks": [
                                {
                                    "block_name": "divi/column",
                                    "inner_blocks": [{"block_name": "divi/text", "attributes": {}}],  # noqa: E501
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }

    result = engine.verify_layout(diviops.get_page_layout.return_value, {})

    assert result.verification_passed is False
    assert any("Primary color token" in issue for issue in result.issues)


def test_verify_page_failed_fetch():
    """Test verify_page handles fetch failure."""
    diviops = MockDiviOpsClient()
    config = MockConfig()

    diviops.get_page_layout.return_value = {"ok": False, "error": "Not found"}

    # Create proper engine and call verify_layout directly
    engine = VerificationEngine(diviops, config)
    result = engine.verify_layout(diviops.get_page_layout.return_value, {})

    assert result.passed is False
    assert "Layout fetch failed" in result.issues[0]
