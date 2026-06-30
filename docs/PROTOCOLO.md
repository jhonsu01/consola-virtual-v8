# Protocolo de Comunicación LAN (V8)

Mensajes **JSON planos** sobre **WebSocket** en `ws://<IP_HOST>:8080`.
El Host es el servidor; las apps Android son clientes. El Host reenvía cada
cambio recibido al resto de clientes para mantenerlos sincronizados.

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
