"""Responder de autodescubrimiento LAN (UDP) para la Consola Virtual V8.

El telefono envia un sondeo UDP en broadcast al puerto de descubrimiento; el
Host responde con su IP y puerto del WebSocket para que el usuario no tenga que
escribir la direccion a mano.

Protocolo:
  Cliente -> broadcast  : b"CONSOLA_V8_DISCOVER"  (UDP, puerto 8079)
  Host    -> respuesta  : {"app":"ConsolaV8","ip":"192.168.x.x","port":8080,
                           "name":"<hostname>","requires_pin":true}
"""

from __future__ import annotations

import json
import logging
import socket
import threading

from .utils import get_local_ip

logger = logging.getLogger("consola_v8.discovery")

DEFAULT_DISCOVERY_PORT = 8079
PROBE = b"CONSOLA_V8_DISCOVER"


class DiscoveryResponder:
    """Hilo de fondo que responde a los sondeos de descubrimiento."""

    def __init__(self, ws_port: int, disc_port: int = DEFAULT_DISCOVERY_PORT,
                 name: str | None = None, requires_pin: bool = True) -> None:
        self._ws_port = ws_port
        self._disc_port = disc_port
        self._name = name or socket.gethostname()
        self._requires_pin = requires_pin
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="consola-v8-discovery", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.settimeout(1.0)
            self._sock.bind(("0.0.0.0", self._disc_port))
            logger.info("Descubrimiento UDP escuchando en el puerto %d.", self._disc_port)
        except Exception as exc:  # pragma: no cover
            logger.warning("No se pudo iniciar el descubrimiento UDP: %s", exc)
            return

        while self._running:
            try:
                data, addr = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if data.strip() == PROBE:
                reply = json.dumps({
                    "app": "ConsolaV8",
                    "ip": get_local_ip(),
                    "port": self._ws_port,
                    "name": self._name,
                    "requires_pin": self._requires_pin,
                }).encode("utf-8")
                try:
                    self._sock.sendto(reply, addr)
                    logger.info("Descubrimiento: respondido a %s", addr)
                except Exception:  # pragma: no cover
                    pass

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:  # pragma: no cover
                pass
