"""Base converter classes and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T", bound="BaseConverter")


@dataclass
class ExtractedAssets:
    """Assets extracted from source content."""

    images: list[dict[str, Any]] = field(default_factory=list)
    buttons: list[dict[str, Any]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    videos: list[dict[str, Any]] = field(default_factory=list)
    other: list[dict[str, Any]] = field(default_factory=list)


class BaseConverter(ABC):
    """Abstract base class for format-specific converters."""

    format_name: str = "unknown"

    @abstractmethod
    def detect(self, content: str) -> bool:
        """Check if this converter can handle the content."""

    @abstractmethod
    def convert(self, content: str, source_id: int, design_system: Any = None) -> str:
        """Convert source content to Divi 5 block markup."""

    @abstractmethod
    def extract_assets(self, content: str) -> ExtractedAssets:
        """Extract images, buttons, forms, etc. from content."""

    def _wrap_as_plain_html(self, content: str) -> str:
        """Wrap content in default Divi 5 block structure."""
        return (
            '<!-- wp:divi/placeholder {"builderVersion":"5.9.0"} -->'
            '<!-- wp:divi/section {"module":{"decoration":{"layout":{"desktop":{"value":{"display":"block"}}},"background":{"desktop":{"value":{"color":"#ffffff"}}},"spacing":{"desktop":{"value":{}}}},"builderVersion":"5.9.0"} -->'  # noqa: E501
            '<!-- wp:divi/row {"module":{"decoration":{"layout":{"desktop":{"value":{"display":"flex","flexWrap":"nowrap","alignItems":"center"}}},"phone":{"value":{"flexWrap":"wrap"}},"phoneWide":{"value":{"flexWrap":"wrap"}}}},"builderVersion":"5.9.0"} -->'  # noqa: E501
            '<!-- wp:divi/column {"options":{"columnLayout":"4_4"},"module":{"advanced":{"type":{"desktop":{"value":"4_4"}}},"decoration":{"sizing":{"desktop":{"value":{"flexType":"24_24"}},"phone":{"value":{"flexType":"24_24"}},"phoneWide":{"value":{"flexType":"24_24"}}}},"builderVersion":"5.9.0"} -->'  # noqa: E501
            f'<!-- wp:divi/text {{"content":{{"innerContent":{{"desktop":{{"value":"{content}"}}}},"module":{{"decoration":{{"animation":{{"desktop":{{"value":{{"style":"fade","delay":"0ms"}}}}}}}},"builderVersion":"5.9.0"}} /-->'  # noqa: E501
            '<!-- /wp:divi/column -->'
            '<!-- /wp:divi/row -->'
            '<!-- /wp:divi/section -->'
            '<!-- /wp:divi/placeholder -->'
        )


class ConverterRegistry:
    """Registry for converter plugins."""

    def __init__(self) -> None:
        self._converters: dict[str, type[BaseConverter]] = {}
        self._instances: dict[str, BaseConverter] = {}

    def register(self, name: str, converter_class: type[BaseConverter]) -> None:
        """Register a converter class."""
        self._converters[name] = converter_class

    def get(self, name: str) -> BaseConverter:
        """Get converter instance by name (lazy instantiation)."""
        if name not in self._instances:
            if name not in self._converters:
                raise ValueError(f"UnknownConverterError({name})")
            self._instances[name] = self._converters[name]()
        return self._instances[name]

    def list(self) -> list[str]:
        return list(self._converters.keys())

    def detect_format(self, content: str) -> str:
        """Auto-detect format from content."""
        for name, _converter_class in self._converters.items():
            instance = self.get(name)
            if instance.detect(content):
                return name
        return "plain_html"

    def get_converter(self, format_name: str) -> BaseConverter:
        """Get converter instance for format."""
        return self.get(format_name)


class UnknownConverterError(ValueError):
    """Raised when converter not found."""


# Global registry
registry = ConverterRegistry()
