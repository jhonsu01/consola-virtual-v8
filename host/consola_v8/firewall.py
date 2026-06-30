"""Ayudante de Firewall de Windows para la Consola Virtual V8.

El motivo numero 1 por el que el telefono "no se puede conectar" es que el
Firewall de Windows bloquea el trafico entrante en el puerto 8080. Este modulo
agrega reglas de entrada para el WebSocket (TCP 8080) y el descubrimiento
(UDP 8079).

``add_rules_elevated`` lanza UNA solicitud de UAC (consola elevada) que crea
ambas reglas de forma persistente. No requiere privilegios para llamarse: el
propio Windows pide la elevacion.
"""

from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger("consola_v8.firewall")

RULE_TCP = "Consola Virtual V8 (WebSocket TCP)"
RULE_UDP = "Consola Virtual V8 (Descubrimiento UDP)"

# Evita abrir una ventana de consola visible al invocar PowerShell.
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def add_rules_elevated(tcp_port: int = 8080, udp_port: int = 8079) -> bool:
    """Crea las reglas de entrada del Firewall pidiendo elevacion (UAC).

    Devuelve ``True`` si el lanzador se ejecuto (no garantiza que el usuario
    haya aceptado el UAC). En sistemas que no son Windows no hace nada.
    """
    if sys.platform != "win32":
        logger.info("Firewall: no aplica fuera de Windows.")
        return False

    netsh_tcp = (
        f'netsh advfirewall firewall delete rule name="{RULE_TCP}" >nul 2>&1 & '
        f'netsh advfirewall firewall add rule name="{RULE_TCP}" '
        f'dir=in action=allow protocol=TCP localport={tcp_port}'
    )
    netsh_udp = (
        f'netsh advfirewall firewall delete rule name="{RULE_UDP}" >nul 2>&1 & '
        f'netsh advfirewall firewall add rule name="{RULE_UDP}" '
        f'dir=in action=allow protocol=UDP localport={udp_port}'
    )
    # cmd.exe /c ejecuta ambos netsh encadenados; Start-Process -Verb RunAs eleva.
    inner = f"{netsh_tcp} & {netsh_udp}"
    launcher = (
        f"Start-Process -FilePath cmd.exe -Verb RunAs -ArgumentList '/c {inner}'"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", launcher],
            creationflags=_NO_WINDOW,
            timeout=120,
            check=False,
        )
        logger.info("Firewall: solicitud de reglas enviada (UAC).")
        return True
    except Exception as exc:  # pragma: no cover - depende del entorno
        logger.warning("Firewall: no se pudo lanzar el elevador: %s", exc)
        return False
