"""Divi 5 Block Schema Validator.

Validates generated Divi 5 block markup against JSON schema definitions
to prevent invalid blocks from being saved.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import jsonschema  # type: ignore[import-untyped]
from jsonschema import validate

logger = logging.getLogger(__name__)

# Divi 5 block schema definitions
DIVI5_BLOCK_SCHEMAS = {
    "divi/section": {
        "type": "object",
        "required": ["module"],
        "properties": {
            "module": {
                "type": "object",
                "required": ["decoration"],
                "properties": {
                    "decoration": {
                        "type": "object",
                        "properties": {
                            "layout": {"type": "object"},
                            "background": {"type": "object"},
                            "spacing": {"type": "object"},
                        },
                    },
                    "meta": {"type": "object"},
                    "builderVersion": {"type": "string"},
                },
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/row": {
        "type": "object",
        "required": ["module"],
        "properties": {
            "module": {
                "type": "object",
                "required": ["advanced", "decoration"],
                "properties": {
                    "advanced": {
                        "type": "object",
                        "properties": {
                            "columnStructure": {"type": "object"},
                            "flexColumnStructure": {"type": "object"},
                        },
                    },
                    "decoration": {
                        "type": "object",
                        "properties": {
                            "layout": {"type": "object"},
                            "background": {"type": "object"},
                            "spacing": {"type": "object"},
                        },
                    },
                },
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/column": {
        "type": "object",
        "required": ["options", "module"],
        "properties": {
            "options": {
                "type": "object",
                "required": ["columnLayout"],
                "properties": {"columnLayout": {"type": "string"}},
            },
            "module": {
                "type": "object",
                "required": ["advanced", "decoration"],
                "properties": {
                    "advanced": {"type": "object"},
                    "decoration": {
                        "type": "object",
                        "properties": {"sizing": {"type": "object"}},
                    },
                },
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/text": {
        "type": "object",
        "required": ["content", "module"],
        "properties": {
            "content": {
                "type": "object",
                "required": ["innerContent"],
                "properties": {"innerContent": {"type": "object"}},
            },
            "module": {
                "type": "object",
                "properties": {"decoration": {"type": "object"}},
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/heading": {
        "type": "object",
        "required": ["title", "content", "builderVersion"],
        "properties": {
            "title": {
                "type": "object",
                "required": ["headingLevel", "decoration"],
                "properties": {
                    "headingLevel": {"type": "string"},
                    "decoration": {"type": "object"},
                },
            },
            "content": {
                "type": "object",
                "required": ["innerContent"],
                "properties": {"innerContent": {"type": "object"}},
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/button": {
        "type": "object",
        "required": ["button", "builderVersion"],
        "properties": {
            "button": {
                "type": "object",
                "required": ["innerContent", "decoration", "sizing"],
                "properties": {
                    "innerContent": {"type": "object"},
                    "decoration": {"type": "object"},
                    "sizing": {"type": "object"},
                },
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/image": {
        "type": "object",
        "required": ["image", "builderVersion"],
        "properties": {
            "image": {
                "type": "object",
                "required": ["innerContent"],
                "properties": {"innerContent": {"type": "object"}},
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/divider": {
        "type": "object",
        "required": ["divider", "builderVersion"],
        "properties": {
            "divider": {
                "type": "object",
                "required": ["decoration"],
                "properties": {"decoration": {"type": "object"}},
            },
            "builderVersion": {"type": "string"},
        },
    },
    "divi/placeholder": {
        "type": "object",
        "required": ["builderVersion"],
        "properties": {"builderVersion": {"type": "string"}},
    },
    "divi/blurb": {
        "type": "object",
        "required": ["blurb", "builderVersion"],
        "properties": {
            "blurb": {
                "type": "object",
                "required": ["content", "decoration"],
                "properties": {
                    "content": {"type": "object"},
                    "decoration": {"type": "object"},
                },
            },
            "builderVersion": {"type": "string"},
        },
    },
}


class Divi5SchemaValidator:
    """Validates Divi 5 block markup against schema definitions."""

    def __init__(self) -> None:
        self.validator = jsonschema.Draft7Validator
        self._schemas = DIVI5_BLOCK_SCHEMAS

    def validate_block(self, block_type: str, attrs: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a single block's attributes against its schema.

        Args:
            block_type: Block type (e.g., "divi/section")
            attrs: Block attributes dict

        Returns:
            Tuple of (is_valid, error_messages)
        """
        schema = self._schemas.get(block_type)
        if not schema:
            return True, []  # Unknown block type - skip validation

        try:
            validate(instance=attrs, schema=schema)
            return True, []  # noqa: TRY300
        except jsonschema.ValidationError as e:
            return False, [str(e)]

    def validate_content(self, content: str) -> tuple[bool, list[str]]:
        """Validate entire Divi 5 content by parsing blocks.

        Args:
            content: Full Divi 5 block markup content

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []

        # Parse blocks from content
        block_pattern = re.compile(
            r"<!--\s*wp:(divi/[a-z]+)\s+(\{.*?\})\s*/?-->", re.DOTALL
        )

        for match in block_pattern.finditer(content):
            block_type = match.group(1)
            attrs_json = match.group(2)

            try:
                attrs = json.loads(attrs_json)
                is_valid, block_errors = self.validate_block(block_type, attrs)
                if not is_valid:
                    errors.extend([f"{block_type}: {e}" for e in block_errors])
            except json.JSONDecodeError as e:
                errors.append(f"{block_type}: Invalid JSON - {e}")

        return len(errors) == 0, errors


# Module-level validator instance
_validator: Divi5SchemaValidator | None = None


def get_validator() -> Divi5SchemaValidator:
    """Get global validator instance."""
    global _validator  # noqa: PLW0603
    if _validator is None:
        _validator = Divi5SchemaValidator()
    return _validator


def validate_divi5_blocks(content: str) -> tuple[bool, list[str]]:
    """Validate Divi 5 block markup.

    Args:
        content: Divi 5 block markup content

    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = get_validator()
    return validator.validate_content(content)
