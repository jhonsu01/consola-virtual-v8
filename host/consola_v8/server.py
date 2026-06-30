"""Servidor WebSocket asincrono de la Consola Virtual V8.

Escucha en ``0.0.0.0:8080`` (todas las interfaces LAN) y procesa mensajes JSON
planos provenientes de la app remota Android:

- ``knob_update``    -> ajusta un potenciometro en tiempo real.
- ``effect_trigger`` -> dispara un efecto instantaneo.
- ``mode_toggle``    -> conmuta un modo especial (p. ej. Dodge).

Arquitectura de hilos:
El servidor corre su propio bucle ``asyncio`` en un hilo dedicado para no
bloquear la interfaz Qt. La comunicacion UI -> red se hace con
``broadcast_threadsafe`` (programa una corrutina en el bucle del servidor desde
cualquier hilo). La comunicacion red -> UI se hace mediante el callback
``on_event`` que recibe cada mensaje validado.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger("consola_v8.server")

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080

#: Eventos validos del protocolo (ver Guia V8, seccion 4).
VALID_EVENTS = {"knob_update", "effect_trigger", "mode_toggle"}


class ConsoleServer:
    """Servidor de sockets que sincroniza el Host con N clientes remotos."""

    def __init__(
        self,
        on_event: Callable[[Dict[str, Any]], None],
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._on_event = on_event
        self._host = host
        self._port = port

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._clients: Set[Any] = set()
        self._running = threading.Event()

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Arranca el servidor en un hilo de fondo con su propio bucle asyncio."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop, name="consola-v8-ws", daemon=True
        )
        self._thread.start()

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
            self._running.set()
            self._loop.run_forever()
        except Exception as exc:  # pragma: no cover
            logger.error("Error en el bucle del servidor: %s", exc)
        finally:
            self._loop.close()

    async def _serve(self) -> None:
        import websockets

        self._server = await websockets.serve(
            self._handler, self._host, self._port, ping_interval=20
        )
        logger.info(
            "Servidor WebSocket local iniciado en el puerto %d de manera "
            "exitosa. Escuchando peticiones...",
            self._port,
        )

    def stop(self) -> None:
        """Detiene el servidor de forma ordenada desde cualquier hilo."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ------------------------------------------------------------------ #
    # Manejo de conexiones
    # ------------------------------------------------------------------ #
    async def _handler(self, websocket) -> None:
        """Atiende una conexion entrante (un cliente Android)."""
        self._clients.add(websocket)
        peer = getattr(websocket, "remote_address", "?")
        logger.info("Cliente conectado: %s (total=%d)", peer, len(self._clients))
        try:
            async for raw in websocket:
                await self._process_message(websocket, raw)
        except Exception as exc:  # pragma: no cover - desconexiones normales
            logger.debug("Conexion finalizada (%s): %s", peer, exc)
        finally:
            self._clients.discard(websocket)
            logger.info("Cliente desconectado: %s (total=%d)", peer, len(self._clients))

    async def _process_message(self, sender, raw: str) -> None:
        """Valida un mensaje JSON, ejecuta el callback y reenvia a los demas."""
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Mensaje no-JSON descartado: %r", raw)
            return

        event = message.get("event")
        if event not in VALID_EVENTS:
            logger.warning("Evento invalido descartado: %r", event)
            return

        # 1) Notifica al Host (motor de audio + UI) en su propio hilo.
        try:
            self._on_event(message)
        except Exception as exc:  # pragma: no cover
            logger.error("Callback on_event fallo: %s", exc)

        # 2) Reenvia el cambio al resto de clientes para mantenerlos en sync.
        await self._broadcast(raw, exclude=sender)

    # ------------------------------------------------------------------ #
    # Difusion (broadcast)
    # ------------------------------------------------------------------ #
    async def _broadcast(self, raw: str, exclude=None) -> None:
        if not self._clients:
            return
        targets = [c for c in self._clients if c is not exclude]
        if not targets:
            return
        results = await asyncio.gather(
            *(self._safe_send(c, raw) for c in targets), return_exceptions=True
        )
        for c, res in zip(targets, results):
            if isinstance(res, Exception):
                self._clients.discard(c)

    @staticmethod
    async def _safe_send(client, raw: str) -> None:
        await client.send(raw)

    def broadcast_threadsafe(self, message: Dict[str, Any]) -> None:
        """Envia un mensaje a todos los clientes desde un hilo ajeno (la UI).

        Se usa cuando el usuario mueve un control en el Host y queremos que las
        apps remotas reflejen el cambio.
        """
        if not self._loop or not self._loop.is_running():
            return
        raw = json.dumps(message)
        asyncio.run_coroutine_threadsafe(self._broadcast(raw), self._loop)
