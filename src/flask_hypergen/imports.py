from __future__ import annotations

from flask_hypergen import context as context_module
from flask_hypergen import hypergen as hypergen_module
from flask_hypergen import liveview as liveview_module
from flask_hypergen import template as template_module
from flask_hypergen import websocket as websocket_module


MODULES = (
    context_module,
    hypergen_module,
    liveview_module,
    template_module,
    websocket_module,
)

__all__: list[str] = []

for module in MODULES:
    for name in getattr(module, '__all__', []):
        if name in __all__:
            continue
        globals()[name] = getattr(module, name)
        __all__.append(name)
