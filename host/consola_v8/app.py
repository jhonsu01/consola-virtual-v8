"""Orquestador del Host: une UI (PySide6) + servidor (WebSocket) + audio.

Modelo de hilos:
- Hilo principal Qt: interfaz grafica.
- Hilo de red: bucle asyncio del ``ConsoleServer``.
Los eventos que llegan por red se reenvian a la UI mediante un ``_Bridge``
(QObject con senales); Qt los entrega de forma segura al hilo principal. Los
cambios hechos en la UI se difunden a los clientes con ``broadcast_threadsafe``.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any, Dict

from PySide6 import QtCore, QtWidgets

from . import firewall
from .audio_engine import AudioEngine
from .dialogs import SessionsDialog, SoundsDialog
from .discovery import DEFAULT_DISCOVERY_PORT, DiscoveryResponder
from .server import ConsoleServer, DEFAULT_PORT
from .sessions import SessionManager
from .ui import ConsoleWindow
from .utils import get_local_ip
from .version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("consola_v8")

MIC_THRESHOLD = 0.05  # umbral para considerar "actividad" de microfono (Dodge)


class _Bridge(QtCore.QObject):
    """Puente seguro entre el hilo de red y el hilo de la UI."""

    knob = QtCore.Signal(str, float)
    mode = QtCore.Signal(str, bool)
    effect = QtCore.Signal(str)
    sessions = QtCore.Signal()  # refresca el PIN/contador tras conectar/desconectar


class ConsolaApp:
    """Aplicacion de escritorio completa."""

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self.port = port
        self.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.qt_app.setApplicationName("Consola Virtual V8")

        self.audio = AudioEngine()
        self.audio.init_audio()

        # Gestor de multiples PINs de acceso y sesiones simultaneas.
        self.sessions = SessionManager()

        self.window = ConsoleWindow(version=__version__)
        self.bridge = _Bridge()
        self.server = ConsoleServer(
            on_event=self._on_network_event,
            port=port,
            auth_callback=self._authorize_session,
            on_disconnect=self._on_session_closed,
            state_provider=self.audio.snapshot,
        )
        self.discovery = DiscoveryResponder(ws_port=port, disc_port=DEFAULT_DISCOVERY_PORT)

        self._wire_ui()
        self._wire_bridge()

    # ------------------------------------------------------------------ #
    # Cableado de senales
    # ------------------------------------------------------------------ #
    def _wire_ui(self) -> None:
        self.window.knobChanged.connect(self._on_ui_knob)
        self.window.modeToggled.connect(self._on_ui_mode)
        self.window.effectTriggered.connect(self._on_ui_effect)
        self.window.firewallRequested.connect(self._on_firewall_requested)
        self.window.regeneratePinRequested.connect(self._on_regenerate_pin)
        self.window.sessionsRequested.connect(self._open_sessions)
        self.window.soundsRequested.connect(self._open_sounds)

    @QtCore.Slot()
    def _on_firewall_requested(self) -> None:
        """Abre el puerto en el Firewall (UAC) sin bloquear la UI."""
        threading.Thread(
            target=lambda: firewall.add_rules_elevated(self.port, DEFAULT_DISCOVERY_PORT),
            daemon=True,
        ).start()
        self.window.notify("Solicitando permiso de Firewall (acepta el aviso de Windows)...")

    @QtCore.Slot()
    def _on_regenerate_pin(self) -> None:
        new_pin = self.sessions.add_pin()
        self._refresh_pin_label()
        self.window.notify(f"Nuevo PIN {new_pin} generado. Compartelo con otro dispositivo.")

    @QtCore.Slot()
    def _open_sessions(self) -> None:
        dlg = SessionsDialog(
            self.sessions, kick=self.server.disconnect_session, parent=self.window)
        dlg.exec()

    @QtCore.Slot()
    def _open_sounds(self) -> None:
        dlg = SoundsDialog(self.audio, parent=self.window)
        dlg.exec()

    # ------------------------------------------------------------------ #
    # Autorizacion de sesiones (corren en el hilo de red)
    # ------------------------------------------------------------------ #
    def _authorize_session(self, pin: str, device: str, ip: str):
        """Valida el PIN y abre una sesion. Devuelve session_id o None."""
        if not self.sessions.validate(pin):
            return None
        sid = self.sessions.open(device, ip, pin)
        self.bridge.sessions.emit()
        return sid

    def _on_session_closed(self, sid: str) -> None:
        self.sessions.close(sid)
        self.bridge.sessions.emit()

    @QtCore.Slot()
    def _refresh_pin_label(self) -> None:
        pins = self.sessions.pins()
        primary = pins[0] if pins else "----"
        self.window.set_pin(primary, extra=max(0, len(pins) - 1))

    def _wire_bridge(self) -> None:
        self.bridge.knob.connect(self.window.apply_knob)
        self.bridge.knob.connect(self._apply_audio_knob)
        self.bridge.mode.connect(self.window.apply_mode)
        self.bridge.effect.connect(self.window.flash_effect)
        self.bridge.sessions.connect(self._refresh_pin_label)

    # ------------------------------------------------------------------ #
    # Eventos de la UI local -> audio + difusion a clientes
    # ------------------------------------------------------------------ #
    @QtCore.Slot(str, float)
    def _on_ui_knob(self, control: str, value: float) -> None:
        self._apply_audio_knob(control, value)
        self.server.broadcast_threadsafe(
            {"event": "knob_update", "control": control, "value": round(value, 4)}
        )

    @QtCore.Slot(str, bool)
    def _on_ui_mode(self, control: str, status: bool) -> None:
        self.audio.set_mode(control, status)
        self.server.broadcast_threadsafe(
            {"event": "mode_toggle", "control": control, "status": status}
        )

    @QtCore.Slot(str)
    def _on_ui_effect(self, control: str) -> None:
        self.audio.play_effect(control)
        self.server.broadcast_threadsafe(
            {"event": "effect_trigger", "control": control}
        )

    # ------------------------------------------------------------------ #
    # Eventos de red (corren en el hilo del servidor)
    # ------------------------------------------------------------------ #
    def _on_network_event(self, message: Dict[str, Any]) -> None:
        event = message.get("event")
        control = message.get("control", "")
        if event == "knob_update":
            self.bridge.knob.emit(control, float(message.get("value", 0.0)))
        elif event == "mode_toggle":
            status = bool(message.get("status", False))
            self.audio.set_mode(control, status)
            self.bridge.mode.emit(control, status)
        elif event == "effect_trigger":
            self.audio.play_effect(control)
            self.bridge.effect.emit(control)

    @QtCore.Slot(str, float)
    def _apply_audio_knob(self, control: str, value: float) -> None:
        self.audio.set_knob(control, value)
        if control == "MIC":
            self.audio.simulate_mic_activity(value > MIC_THRESHOLD)

    # ------------------------------------------------------------------ #
    # Arranque
    # ------------------------------------------------------------------ #
    def run(self) -> int:
        self.server.start()
        self.discovery.start()
        ip = get_local_ip()
        self.window.set_network_info(ip, self.port, listening=False)
        self._refresh_pin_label()
        self.window.show()

        # Refresca el estado del servidor y conteo de clientes periodicamente.
        timer = QtCore.QTimer()
        timer.timeout.connect(self._refresh_status)
        timer.start(1000)
        self._status_timer = timer  # evita garbage collection

        exit_code = self.qt_app.exec()
        self.discovery.stop()
        self.server.stop()
        self.audio.shutdown()
        return exit_code

    def _refresh_status(self) -> None:
        if self.server.is_running:
            self.window.set_client_count(self.server.client_count)


def main() -> int:
    """Punto de entrada del Host."""
    app = ConsolaApp()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
