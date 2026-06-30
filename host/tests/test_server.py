"""Pruebas del servidor: validacion del protocolo (sin abrir sockets reales)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from consola_v8.server import VALID_EVENTS, ConsoleServer  # noqa: E402


def test_valid_events():
    assert VALID_EVENTS == {"knob_update", "effect_trigger", "mode_toggle"}


def test_server_construction():
    received = []
    srv = ConsoleServer(on_event=received.append, port=18080)
    assert srv.client_count == 0
    assert srv.is_running is False
