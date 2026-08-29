"""Compatibility alias for the adapter module."""

import sys

from strict_interface import adapters as _implementation

sys.modules[__name__] = _implementation
