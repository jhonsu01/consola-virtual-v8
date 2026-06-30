# 🎛️ Consola de Sonido Virtual V8

[![CI](https://github.com/jhonsu01/consola-virtual-v8/actions/workflows/ci.yml/badge.svg)](https://github.com/jhonsu01/consola-virtual-v8/actions/workflows/ci.yml)
[![Release](https://github.com/jhonsu01/consola-virtual-v8/actions/workflows/release.yml/badge.svg)](https://github.com/jhonsu01/consola-virtual-v8/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/jhonsu01/consola-virtual-v8?color=ff5722)](https://github.com/jhonsu01/consola-virtual-v8/releases/latest)

Réplica software de la tarjeta de sonido **V8 Sound Card** con interfaz de tema
oscuro. Un **Host de escritorio (Windows)** actúa como motor de audio y servidor
LAN, y una **app móvil (Android)** lo controla de forma remota por Wi-Fi en
tiempo real.

> ⬇️ **Descargas:** el **APK** (Android) y el **MSI** (Windows) se publican
> automáticamente en la [página de Releases](https://github.com/jhonsu01/consola-virtual-v8/releases/latest)
> cada vez que se crea un tag de versión.

---

## 🧩 Arquitectura

```
┌─────────────────────────────┐         WebSocket (JSON, ws://IP:8080)
│   HOST  (Windows, Python)    │◀───────────────────────────────────────┐
│                             │                                         │
│  PySide6 UI (tema oscuro)   │      ┌──────────────────────────────┐   │
│  pygame.mixer (audio)       │      │  APP REMOTA (Android, Flutter) │──┘
│  websockets (servidor LAN)  │      │  Sliders + modos + efectos     │
└─────────────────────────────┘      └──────────────────────────────┘
```

| Componente | Carpeta  | Tecnología                         | Artefacto |
| ---------- | -------- | ---------------------------------- | --------- |
| Host       | `host/`  | Python 3.10+, PySide6, pygame, websockets | `.msi` |
| Remoto     | `mobile/`| Flutter (Dart), web_socket_channel | `.apk`    |

---

## 🎚️ Controles (mapeo del hardware V8)

- **7 potenciómetros:** MIC · ECHO · TREBLE · BASS · RECORD · MUSIC · MONITOR
- **6 modos (naranjas, conmutables):** Electro · Pitch Bend · Magic · Shock-Wave · MC · Dodge
- **12 efectos instantáneos:** Despise · Shot · Beatings · Coldfield · Songs · DogBarking · Laughter · Applause · Kiss · Awkward · Minions · Time
- **Dodge (ducking):** baja la música un 70 % automáticamente cuando hay señal de micrófono.

---

## 🚀 Uso rápido

### Host (Windows)

```bash
cd host
python -m pip install -r requirements.txt
python -m consola_v8
```

La consola reportará en el log:
`Servidor WebSocket local iniciado en el puerto 8080 ... Escuchando peticiones...`
y mostrará la **IP local** en la barra superior. Abre el puerto **8080** en el
Firewall de Windows para tráfico LAN entrante.

### App remota (Android)

1. Instala el **APK** desde [Releases](https://github.com/jhonsu01/consola-virtual-v8/releases/latest).
2. Conecta el teléfono a la **misma red Wi-Fi** que el PC.
3. Abre la app, escribe la IP del Host (ej. `192.168.1.15`) y pulsa **Conectar**.

---

## 📡 Protocolo de red (JSON plano sobre WebSocket)

```json
{ "event": "knob_update",    "control": "ECHO",     "value": 0.85 }
{ "event": "effect_trigger", "control": "Applause" }
{ "event": "mode_toggle",    "control": "Dodge",    "status": true }
```

Detalle completo en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

---

## 📦 Compilar los binarios localmente (opcional)

El CI ya los compila en la nube, pero también puedes hacerlo tú:

### MSI (Windows)

```bash
cd host
pip install -r requirements.txt -r requirements-build.txt
python build_msi.py bdist_msi   # -> host/dist/ConsolaVirtualV8-<ver>-win64.msi
```

### APK (Android)

```bash
cd mobile
flutter create --platforms=android --project-name consola_v8_remote --org com.consolav8 .
git checkout -- pubspec.yaml lib/main.dart
flutter pub get
flutter build apk --release   # -> mobile/build/app/outputs/flutter-apk/app-release.apk
```

> El scaffold de Android (`mobile/android/`) **no se versiona**: se regenera con
> `flutter create`, lo que mantiene el repositorio limpio.

---

## 🔖 Gestión de versiones y Releases

El proyecto usa **SemVer**. Una sola orden sincroniza Host y Mobile:

```bash
python scripts/bump_version.py patch        # 1.0.0 -> 1.0.1  (o minor / major / X.Y.Z)
git commit -am "chore: release v1.0.1"
git tag v1.0.1
git push --follow-tags
```

Al subir el tag `v*.*.*`, **GitHub Actions**:
1. Compila el **MSI** (runner Windows) y el **APK** (runner con Flutter).
2. Crea una **GitHub Release** con notas automáticas y ambos binarios adjuntos.

Así, las releases se visualizan y crecen conforme avanza el proyecto.

---

## 🧪 Pruebas

```bash
cd host && pytest tests/ -q        # lógica del Host (sin audio/red)
cd mobile && flutter analyze       # análisis estático de la app
```

---

## 🗺️ Roadmap

- [ ] DSP real de ECHO/TREBLE/BASS y modos de voz con `sounddevice + numpy`.
- [ ] Captura real de micrófono para el Dodge (hoy se simula con el knob MIC).
- [ ] Persistencia de presets.
- [ ] Firma de APK/MSI para distribución verificada.

---

## 📁 Estructura

```
consola-virtual-v8/
├── host/                 # Host de escritorio (Windows)
│   ├── consola_v8/       # paquete: audio_engine, server, ui, app
│   │   └── sfx/          # 12 efectos WAV (placeholders)
│   ├── tests/            # pruebas de lógica
│   ├── tools/            # generador de SFX
│   ├── build_msi.py      # empaquetado MSI (cx_Freeze)
│   └── requirements*.txt
├── mobile/               # App remota (Flutter)
│   └── lib/main.dart     # app de un solo archivo
├── scripts/              # bump_version.py
├── docs/                 # documentación (protocolo)
├── .github/workflows/    # CI + Release
├── VERSION · CHANGELOG.md · LICENSE
```

---

## 📜 Licencia

[MIT](LICENSE) © 2026 jhonsu01
