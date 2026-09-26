"""Directory-install entry point, loaded in Hermes' namespaced importer."""
from .orca_plugin import register

__all__ = ["register"]
