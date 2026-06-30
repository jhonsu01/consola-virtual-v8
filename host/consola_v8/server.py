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

    #: Segundos que un cliente tiene para enviar su PIN antes de cerrarse.
    AUTH_TIMEOUT = 20

    def __init__(
        self,
        on_event: Callable[[Dict[str, Any]], None],
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        auth_callback: Optional[Callable[[str, str, str], Optional[str]]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self._on_event = on_event
        self._host = host
        self._port = port
        # auth_callback(pin, device, ip) -> session_id si el PIN es valido, None si no.
        # Si es None, el emparejamiento esta desactivado y se acepta a todos.
        self._auth_callback = auth_callback
        # on_disconnect(session_id): se llama cuando una sesion se cierra.
        self._on_disconnect = on_disconnect
        # Devuelve el estado actual (knobs/modes) para sincronizar al conectar.
        self._state_provider = state_provider

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._clients: Set[Any] = set()  # solo clientes AUTENTICADOS
        self._sessions: Dict[str, Any] = {}  # session_id -> websocket
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
        """Atiende una conexion entrante. Multiples conexiones coexisten."""
        peer = getattr(websocket, "remote_address", "?")

        # Emparejamiento por PIN ANTES de aceptar cualquier evento.
        sid = await self._authenticate(websocket, peer)
        if sid is None:
            return

        self._clients.add(websocket)
        self._sessions[sid] = websocket
        logger.info("Sesion ABIERTA %s: %s (activas=%d)", sid, peer, len(self._clients))
        await self._send_state(websocket)
        try:
            async for raw in websocket:
                await self._process_message(websocket, raw)
        except Exception as exc:  # pragma: no cover - desconexiones normales
            logger.debug("Conexion finalizada (%s): %s", peer, exc)
        finally:
            self._clients.discard(websocket)
            self._sessions.pop(sid, None)
            logger.info("Sesion CERRADA %s: %s (activas=%d)", sid, peer, len(self._clients))
            if self._on_disconnect:
                try:
                    self._on_disconnect(sid)
                except Exception:  # pragma: no cover
                    pass

    async def _authenticate(self, websocket, peer) -> Optional[str]:
        """Exige ``auth`` con un PIN valido. Devuelve el session_id o None.

        Si no hay ``auth_callback`` el emparejamiento esta desactivado y se
        acepta la conexion con un id generico.
        """
        if self._auth_callback is None:
            return "open"

        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=self.AUTH_TIMEOUT)
        except Exception:
            logger.info("Auth: timeout/cierre sin PIN de %s", peer)
            await self._safe_close(websocket)
            return None

        try:
            msg = json.loads(raw)
        except Exception:
            msg = {}

        pin = str(msg.get("pin", "")).strip()
        device = str(msg.get("device", "?"))
        ip = peer[0] if isinstance(peer, (tuple, list)) and peer else str(peer)

        sid = None
        if msg.get("event") == "auth":
            sid = self._auth_callback(pin, device, ip)

        if sid:
            await self._try_send(websocket, {"event": "auth_result", "status": "ok"})
            logger.info("Auth OK: %s (device=%s, session=%s)", peer, device, sid)
            return sid

        logger.info("Auth FALLIDA: %s (PIN incorrecto)", peer)
        await self._try_send(websocket, {"event": "auth_result", "status": "fail"})
        await self._safe_close(websocket)
        return None

    def disconnect_session(self, sid: str) -> None:
        """Expulsa una sesion por id desde cualquier hilo (la UI)."""
        if not self._loop or not self._loop.is_running():
            return
        ws = self._sessions.get(sid)
        if ws is not None:
            asyncio.run_coroutine_threadsafe(self._safe_close(ws), self._loop)

    @staticmethod
    async def _try_send(websocket, message: Dict[str, Any]) -> None:
        """Envia un mensaje ignorando errores (para handshake/estado)."""
        try:
            await websocket.send(json.dumps(message))
        except Exception:  # pragma: no cover
            pass

    async def _send_state(self, websocket) -> None:
        """Envia el estado actual (knobs/modes) al cliente recien autenticado."""
        if not self._state_provider:
            return
        try:
            snap = self._state_provider()
            payload = {"event": "state_sync", "knobs": snap.get("knobs", {}),
                       "modes": snap.get("modes", {})}
            await self._try_send(websocket, payload)
        except Exception as exc:  # pragma: no cover
            logger.debug("No se pudo enviar state_sync: %s", exc)

    @staticmethod
    async def _safe_close(websocket) -> None:
        try:
            await websocket.close()
        except Exception:  # pragma: no cover
            pass

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
