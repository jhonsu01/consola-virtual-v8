"""Consola de Sonido Virtual V8 - Host de escritorio (Windows).

Paquete que agrupa:
- ``audio_engine``: motor de audio (pygame.mixer) para efectos y mezcla.
- ``server``: servidor WebSocket asincrono para la app remota Android.
- ``ui``: interfaz grafica PySide6 con tema oscuro.
- ``app``: punto de orquestacion que une UI + servidor + audio.
"""

from .version import __version__

__all__ = ["__version__"]
