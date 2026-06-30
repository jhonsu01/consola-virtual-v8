# Protocolo de Comunicación LAN (V8)

Mensajes **JSON planos** sobre **WebSocket** en `ws://<IP_HOST>:8080`.
El Host es el servidor; las apps Android son clientes. El Host reenvía cada
cambio recibido al resto de clientes para mantenerlos sincronizados.

## Autodescubrimiento (UDP, puerto 8079)

Antes de conectar por WebSocket, el cliente puede localizar al Host:

```
Cliente -> broadcast 255.255.255.255:8079 : "CONSOLA_V8_DISCOVER"   (UDP)
Host    -> respuesta unicast              : {"app":"ConsolaV8","ip":"192.168.x.x",
                                             "port":8080,"name":"<host>","requires_pin":true}
```

## Emparejamiento por PIN (primer mensaje obligatorio)

Tras abrir el WebSocket, el cliente DEBE autenticarse antes de enviar eventos:

```json
{ "event": "auth", "pin": "1234", "device": "Android" }
```

El Host responde:

```json
{ "event": "auth_result", "status": "ok" }     // PIN correcto: continúa
{ "event": "auth_result", "status": "fail" }   // PIN incorrecto: cierra la conexión
```

Si la autenticación es correcta, el Host envía de inmediato el estado actual:

```json
{ "event": "state_sync", "knobs": {"MIC":0.8, ...}, "modes": {"Dodge":false, ...} }
```

Mientras el cliente no esté autenticado, cualquier otro evento se ignora y la
conexión se cierra tras 20 s sin un `auth` válido.

## Eventos

### 1. `knob_update` — movimiento de potenciómetro

```json
{ "event": "knob_update", "control": "ECHO", "value": 0.85 }
```

| Campo     | Tipo   | Valores                                                        |
| --------- | ------ | -------------------------------------------------------------- |
| `control` | string | `MIC` `ECHO` `TREBLE` `BASS` `RECORD` `MUSIC` `MONITOR`        |
| `value`   | float  | `0.0`–`1.0` (normalizado; TREBLE/BASS se muestran como dB)     |

### 2. `effect_trigger` — disparo de efecto instantáneo

```json
{ "event": "effect_trigger", "control": "Applause" }
```

| Campo     | Tipo   | Valores                                                                                 |
| --------- | ------ | --------------------------------------------------------------------------------------- |
| `control` | string | `Despise` `Shot` `Beatings` `Coldfield` `Songs` `DogBarking` `Laughter` `Applause` `Kiss` `Awkward` `Minions` `Time` |

### 3. `mode_toggle` — conmutación de modo

```json
{ "event": "mode_toggle", "control": "Dodge", "status": true }
```

| Campo     | Tipo    | Valores                                                       |
| --------- | ------- | ------------------------------------------------------------- |
| `control` | string  | `Electro` `Pitch Bend` `Magic` `Shock-Wave` `MC` `Dodge`      |
| `status`  | boolean | `true` (activo) / `false` (inactivo)                          |

## Reglas

- Los mensajes que no sean JSON válido o cuyo `event` no esté en la lista se
  **descartan** silenciosamente (el servidor no se cae).
- `value` se normaliza siempre a `0.0`–`1.0` para que Host y Móvil compartan la
  misma escala sin conversiones de tipos.
- El Host hace **broadcast** del cambio a los demás clientes (excluyendo al
  emisor) para sincronización en tiempo real.

## Puerto y red

- Puerto por defecto: **8080** (TCP), escuchando en `0.0.0.0` (todas las
  interfaces LAN).
- Requiere que el Firewall de Windows permita tráfico entrante en ese puerto.
- Host y móvil deben estar en el **mismo segmento de red Wi-Fi/LAN**.
