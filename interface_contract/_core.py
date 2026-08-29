"""Compatibility alias for the implementation module."""

import sys

from strict_interface import _core as _implementation

sys.modules[__name__] = _implementation
