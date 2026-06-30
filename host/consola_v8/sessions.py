"""Gestor de sesiones y PINs de acceso de la Consola Virtual V8.

Permite multiples dispositivos conectados al mismo tiempo, cada uno autenticado
con uno de varios PINs de acceso. El Host puede:
- Generar varios PINs validos (uno por persona/dispositivo).
- Ver las sesiones activas (dispositivo, IP, PIN usado).
- Expulsar una sesion o revocar un PIN.

Es seguro para hilos: lo consultan tanto el hilo de red como el de la UI.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Dict, List, Optional


class SessionManager:
    """Mantiene los PINs validos y las sesiones activas."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pins: List[str] = []
        self._sessions: Dict[str, Dict[str, object]] = {}
        self._counter = 0
        self.add_pin()  # un PIN inicial al arrancar

    # ----------------------------- PINs ------------------------------ #
    def add_pin(self) -> str:
        """Genera y agrega un nuevo PIN unico de 4 digitos."""
        with self._lock:
            for _ in range(100):
                pin = f"{random.randint(0, 9999):04d}"
                if pin not in self._pins:
                    self._pins.append(pin)
                    return pin
            return self._pins[0]

    def remove_pin(self, pin: str) -> None:
        """Revoca un PIN (no se permite quedar sin ninguno)."""
        with self._lock:
            if pin in self._pins and len(self._pins) > 1:
                self._pins.remove(pin)

    def pins(self) -> List[str]:
        with self._lock:
            return list(self._pins)

    def primary_pin(self) -> str:
        with self._lock:
            return self._pins[0] if self._pins else "----"

    def validate(self, pin: str) -> bool:
        with self._lock:
            return str(pin).strip() in self._pins

    # --------------------------- Sesiones ---------------------------- #
    def open(self, device: str, ip: str, pin: str) -> str:
        """Registra una sesion y devuelve su id."""
        with self._lock:
            self._counter += 1
            sid = f"s{self._counter}"
            self._sessions[sid] = {
                "device": device or "?",
                "ip": ip,
                "pin": pin,
                "ts": time.time(),
            }
            return sid

    def close(self, sid: str) -> None:
        with self._lock:
            self._sessions.pop(sid, None)

    def sessions(self) -> Dict[str, Dict[str, object]]:
        with self._lock:
            return {k: dict(v) for k, v in self._sessions.items()}

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)
