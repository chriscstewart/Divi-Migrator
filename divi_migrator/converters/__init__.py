"""Converters package - auto-register all converters."""

from divi_migrator.converters.avada import AvadaConverter
from divi_migrator.converters.elementor import ElementorConverter
from divi_migrator.converters.plain_html import PlainHTMLConverter
from divi_migrator.converters.base import registry

# Register all converters
registry.register("avada", AvadaConverter)
registry.register("elementor", ElementorConverter)
registry.register("plain_html", PlainHTMLConverter)

__all__ = ["AvadaConverter", "ElementorConverter", "PlainHTMLConverter", "registry"]
