# Changelog

Todas las versiones notables de este proyecto se documentan aqui.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado es [SemVer](https://semver.org/lang/es/).

## [Unreleased]

## [1.1.0] - 2026-06-30

### Agregado
- **Autodescubrimiento del Host (LAN):** la app Android encuentra la IP del Host
  automaticamente mediante un sondeo UDP en broadcast (puerto 8079); ya no es
  obligatorio escribir la IP a mano. Botón "Buscar" para reintentar.
- **Emparejamiento por PIN:** el Host genera un PIN de 4 dígitos visible en su
  barra superior; cada dispositivo debe ingresarlo para conectarse. Eventos
  `auth` / `auth_result` en el protocolo. Botón "Nuevo PIN" para regenerarlo.
- **Sincronización inicial de estado** (`state_sync`): al autenticarse, el Host
  envía el estado actual de knobs y modos para que el móvil arranque sincronizado.
- **Botón "Abrir Firewall"** en el Host: crea (con UAC) las reglas de entrada
  para TCP 8080 y UDP 8079 — soluciona el "no se puede conectar" más común.

### Corregido
- **APK release ahora declara el permiso `INTERNET` y habilita
  `usesCleartextTraffic`** (Android 9+ bloquea `ws://` por defecto). Se parchea
  el `AndroidManifest.xml` tras `flutter create` en el CI y vía
  `mobile/tools/patch_android_manifest.py`.

## [1.0.0] - 2026-06-30

### Agregado
- **Host (Windows / Python + PySide6):** interfaz de tema oscuro con 7
  potenciometros rotativos dibujados a mano, 6 botones de modo naranjas
  conmutables y 12 efectos instantaneos.
- **Motor de audio (`pygame.mixer`):** carga de efectos en memoria para disparo
  de baja latencia y reproduccion no bloqueante.
- **Servidor WebSocket asincrono** en `0.0.0.0:8080` con protocolo JSON plano
  (`knob_update`, `effect_trigger`, `mode_toggle`) y difusion a multiples
  clientes para sincronizacion en tiempo real.
- **Dodge (ducking):** atenuacion automatica del 70% de la musica al detectar
  senal de microfono.
- **App remota (Android / Flutter):** pantalla de conexion por IP y replica
  tactil de la consola con envio throttled de eventos.
- **Empaquetado:** generacion de **MSI** (cx_Freeze) y **APK** (Flutter).
- **CI/CD (GitHub Actions):** pruebas en cada push y compilacion+publicacion
  automatica de MSI y APK como GitHub Release al crear un tag `vX.Y.Z`.
- **Gestion de versiones:** `scripts/bump_version.py` sincroniza Host y Mobile.

### Notas
- Los 12 efectos incluidos son placeholders sinteticos libres de derechos;
  reemplazables en `host/consola_v8/sfx/`.
- ECHO/TREBLE/BASS y modos de voz (Electro, Pitch Bend, Magic, Shock-Wave, MC)
  estan cableados como parametros del protocolo; su DSP en tiempo real se
  abordara en una version futura con backend `sounddevice + numpy`.

[Unreleased]: https://github.com/jhonsu01/consola-virtual-v8/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/jhonsu01/consola-virtual-v8/releases/tag/v1.1.0
[1.0.0]: https://github.com/jhonsu01/consola-virtual-v8/releases/tag/v1.0.0
