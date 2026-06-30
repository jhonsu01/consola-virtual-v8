"""Gestiona la version del proyecto de forma sincronizada (SemVer).

Actualiza en un solo paso:
- ``VERSION``                       (fuente de verdad)
- ``host/consola_v8/version.py``    (Host Python / MSI)
- ``mobile/pubspec.yaml``           (App Flutter / APK, formato X.Y.Z+build)

Uso:
    python scripts/bump_version.py 1.2.0
    python scripts/bump_version.py patch   # 1.0.0 -> 1.0.1
    python scripts/bump_version.py minor   # 1.0.1 -> 1.1.0
    python scripts/bump_version.py major   # 1.1.0 -> 2.0.0

Despues:
    git commit -am "chore: release vX.Y.Z"
    git tag vX.Y.Z
    git push --follow-tags        # Actions compila y publica la Release
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
PY_VERSION = ROOT / "host" / "consola_v8" / "version.py"
PUBSPEC = ROOT / "mobile" / "pubspec.yaml"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def read_current() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def bump(current: str, part: str) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(part)


def current_build() -> int:
    m = re.search(r"^version:\s*\d+\.\d+\.\d+\+(\d+)", PUBSPEC.read_text(encoding="utf-8"), re.M)
    return int(m.group(1)) if m else 0


def write_all(new_version: str) -> None:
    VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")

    PY_VERSION.write_text(
        '"""Version unica del Host. Fuente de verdad para el empaquetado MSI y la UI."""\n\n'
        f'__version__ = "{new_version}"\n',
        encoding="utf-8",
    )

    build = current_build() + 1
    text = PUBSPEC.read_text(encoding="utf-8")
    text = re.sub(
        r"^version:\s*.*$",
        f"version: {new_version}+{build}",
        text,
        count=1,
        flags=re.M,
    )
    PUBSPEC.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    arg = argv[1].strip()
    current = read_current()
    if arg in ("major", "minor", "patch"):
        new_version = bump(current, arg)
    elif SEMVER.match(arg):
        new_version = arg
    else:
        print(f"Version invalida: {arg!r}. Usa X.Y.Z o major/minor/patch.")
        return 1

    write_all(new_version)
    print(f"Version: {current} -> {new_version}")
    print("Archivos actualizados: VERSION, host/consola_v8/version.py, mobile/pubspec.yaml")
    print(f"Siguiente paso:  git commit -am \"chore: release v{new_version}\" && "
          f"git tag v{new_version} && git push --follow-tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
