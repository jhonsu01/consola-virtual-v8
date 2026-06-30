"""Utilidades compartidas del Host."""

from __future__ import annotations

import socket


def get_local_ip() -> str:
    """Devuelve la IP LAN de la maquina (la que deben usar los clientes).

    Abre un socket UDP "ficticio" hacia una IP externa para que el SO elija la
    interfaz de salida correcta; no se envia ningun paquete real.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()
