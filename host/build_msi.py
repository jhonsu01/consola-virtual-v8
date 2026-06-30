"""Construye el instalador MSI del Host con cx_Freeze.

Uso (en Windows, dentro de la carpeta ``host/``):
    pip install -r requirements.txt -r requirements-build.txt
    python build_msi.py bdist_msi

El MSI resultante queda en ``host/dist/``.
"""

from __future__ import annotations

import sys

from cx_Freeze import Executable, setup

from consola_v8.version import __version__

# GUID estable de actualizacion: permite que un MSI nuevo reemplace al anterior
# en vez de instalar dos copias. NO cambiar entre versiones.
UPGRADE_CODE = "{6F2B1A7C-9D34-4E55-8A21-1C0F7E3B9A40}"

build_exe_options = {
    "packages": ["consola_v8", "PySide6", "pygame", "websockets", "asyncio"],
    "excludes": ["tkinter", "unittest", "pydoc", "test"],
    # Copia los efectos de audio junto al paquete congelado.
    "include_files": [("consola_v8/sfx", "lib/consola_v8/sfx")],
    "include_msvcr": True,
}

bdist_msi_options = {
    "upgrade_code": UPGRADE_CODE,
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFiles64Folder]\ConsolaVirtualV8",
    "all_users": True,
}

# La base "gui" (cx_Freeze 7.2+/8.x) evita abrir una consola negra detras de
# la interfaz. Sustituye a la antigua "Win32GUI" eliminada en cx_Freeze 8.
base = "gui" if sys.platform == "win32" else None

executables = [
    Executable(
        script="run_host.py",
        base=base,
        target_name="ConsolaVirtualV8.exe",
        shortcut_name="Consola Virtual V8",
        shortcut_dir="ProgramMenuFolder",
        copyright="Consola Virtual V8",
    )
]

setup(
    name="ConsolaVirtualV8",
    version=__version__,
    description="Consola de Sonido Virtual V8 - Host de escritorio",
    author="jhonsu777",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=executables,
)
