from __future__ import annotations

from flask_hypergen import imports as imports_module


__all__ = list(imports_module.__all__)

for name in __all__:
    globals()[name] = getattr(imports_module, name)
