# Efectos de sonido (SFX)

Estos 12 archivos `.wav` son **marcadores de posicion sinteticos** generados con
`tools/generate_sfx.py` (tonos cortos libres de derechos), para que la consola
funcione apenas se instala.

## Reemplazar por tus propios efectos

Sustituye cada archivo manteniendo **exactamente** el mismo nombre:

| Boton (UI)  | Archivo            |
| ----------- | ------------------ |
| Despise     | `despise.wav`      |
| Shot        | `shot.wav`         |
| Beatings    | `beatings.wav`     |
| Coldfield   | `coldfield.wav`    |
| Songs       | `songs.wav`        |
| DogBarking  | `dogbarking.wav`   |
| Laughter    | `laughter.wav`     |
| Applause    | `applause.wav`     |
| Kiss        | `kiss.wav`         |
| Awkward     | `awkward.wav`      |
| Minions     | `minions.wav`      |
| Time        | `time.wav`         |

Formatos soportados por `pygame.mixer`: WAV y OGG (recomendados). MP3 funciona
en la mayoria de plataformas pero WAV/OGG dan menor latencia.
