"""Parchea el AndroidManifest generado por `flutter create`.

Android (API 28+) BLOQUEA el trafico en texto plano por defecto, lo que impide
las conexiones `ws://` a la LAN, y el APK release necesita declarar el permiso
INTERNET explicitamente. Este script agrega ambas cosas de forma idempotente:

  1. <uses-permission android:name="android.permission.INTERNET"/>
  2. android:usesCleartextTraffic="true" en <application>

Uso (desde mobile/):
    python tools/patch_android_manifest.py
"""

from __future__ import annotations

import os
import sys

MANIFEST = os.path.join("android", "app", "src", "main", "AndroidManifest.xml")


def main() -> int:
    if not os.path.isfile(MANIFEST):
        print(f"No se encontro {MANIFEST}. Ejecuta `flutter create` primero.")
        return 1

    with open(MANIFEST, "r", encoding="utf-8") as fh:
        content = fh.read()

    changed = False

    if "android.permission.INTERNET" not in content:
        content = content.replace(
            "<application",
            '<uses-permission android:name="android.permission.INTERNET"/>\n    <application',
            1,
        )
        changed = True
        print("  + permiso INTERNET agregado")

    if "usesCleartextTraffic" not in content:
        content = content.replace(
            "<application",
            '<application android:usesCleartextTraffic="true"',
            1,
        )
        changed = True
        print("  + usesCleartextTraffic=true agregado")

    if changed:
        with open(MANIFEST, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"AndroidManifest parcheado: {MANIFEST}")
    else:
        print("AndroidManifest ya estaba parcheado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
