"""Compatibility facade for the split Windows native helper layer."""
import sys as _sys
from native import windows as _implementation

# Keep legacy ``import winapi`` callers and monkeypatches bound to one module.
_sys.modules[__name__] = _implementation
