"""Motor de audio de la Consola Virtual V8.

Responsabilidades (Capa 3 - Ejecucion deterministica):
- Cargar en memoria los 12 efectos instantaneos (WAV/MP3) para disparo de
  latencia minima (sin lectura de disco al presionar).
- Reproducir efectos de forma NO bloqueante usando canales de ``pygame.mixer``.
- Mantener el estado de los 7 potenciometros (knobs) y aplicarlo a la mezcla.
- Implementar el "Dodge" (ducking): bajar la musica un 70% cuando hay senal
  de microfono.

Nota tecnica honesta sobre DSP:
``pygame.mixer`` es un mezclador de reproduccion; NO ofrece ecualizacion ni
eco en tiempo real. Por eso ECHO/TREBLE/BASS y los modos de voz (Electro,
Pitch Bend, Magic, Shock-Wave, MC) se almacenan como parametros y se emiten
al resto del ecosistema, pero su procesamiento DSP real queda preparado para
un backend ``sounddevice + numpy`` (ver roadmap del README). Los knobs de
volumen (MUSIC, MONITOR, RECORD) y todos los efectos instantaneos SI operan
de forma real.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from typing import Callable, Dict, Optional, Tuple

logger = logging.getLogger("consola_v8.audio")

#: Formatos de audio aceptados al personalizar efectos (por prioridad).
SUPPORTED_EXTS = (".wav", ".ogg", ".mp3")


class AudioEngine:
    """Encapsula el estado de mezcla y la reproduccion de efectos.

    Es seguro para hilos: todas las mutaciones de estado se protegen con un
    ``threading.Lock`` porque el motor recibe ordenes tanto de la UI (hilo
    principal Qt) como del servidor de red (hilo asincrono).
    """

    #: Mapa estricto string -> ruta relativa del archivo de audio.
    EFFECTS: Dict[str, str] = {
        "Despise": "sfx/despise.wav",
        "Shot": "sfx/shot.wav",
        "Beatings": "sfx/beatings.wav",
        "Coldfield": "sfx/coldfield.wav",
        "Songs": "sfx/songs.wav",
        "DogBarking": "sfx/dogbarking.wav",
        "Laughter": "sfx/laughter.wav",
        "Applause": "sfx/applause.wav",
        "Kiss": "sfx/kiss.wav",
        "Awkward": "sfx/awkward.wav",
        "Minions": "sfx/minions.wav",
        "Time": "sfx/time.wav",
    }

    #: Knobs y su valor inicial normalizado.
    KNOBS = ("MIC", "ECHO", "TREBLE", "BASS", "RECORD", "MUSIC", "MONITOR")

    #: Modos especiales (botones naranjas).
    MODES = ("Electro", "Pitch Bend", "Magic", "Shock-Wave", "MC", "Dodge")

    #: Porcentaje de atenuacion de la musica al activarse el ducking.
    DUCK_ATTENUATION = 0.70

    def __init__(self, base_dir: Optional[str] = None,
                 user_dir: Optional[str] = None) -> None:
        self._base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        # Carpeta ESCRIBIBLE para los sonidos personalizados del usuario.
        # (La carpeta sfx empaquetada vive en Program Files y es de solo lectura.)
        self._user_dir = user_dir or self._default_user_dir()
        try:
            os.makedirs(self._user_dir, exist_ok=True)
        except Exception:  # pragma: no cover
            pass
        self._lock = threading.RLock()
        self._available = False  # True si pygame.mixer inicializo bien.

        # Estado de knobs: TREBLE/BASS guardan dB (-12..+12); resto 0.0..1.0.
        self._knobs: Dict[str, float] = {
            "MIC": 0.8,
            "ECHO": 0.0,
            "TREBLE": 0.0,
            "BASS": 0.0,
            "RECORD": 0.8,
            "MUSIC": 0.7,
            "MONITOR": 0.8,
        }
        self._modes: Dict[str, bool] = {m: False for m in self.MODES}
        self._mic_active = False  # senal simulada para el Dodge.

        self._sounds: Dict[str, object] = {}  # name -> pygame.Sound
        self._mixer = None  # referencia perezosa a pygame.mixer

    # ------------------------------------------------------------------ #
    # Inicializacion
    # ------------------------------------------------------------------ #
    def init_audio(self) -> bool:
        """Inicializa ``pygame.mixer`` con baja latencia y carga los efectos.

        Devuelve ``True`` si el subsistema de audio quedo operativo. Si no hay
        dispositivo de audio (p. ej. en un runner de CI) degrada con elegancia
        a modo silencioso para no romper la aplicacion.
        """
        try:
            import pygame  # import perezoso: el motor no depende de Qt.

            # pre_init reduce el tamano del buffer => menor latencia al disparar.
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            self._mixer = pygame.mixer
            self._available = True
            logger.info("pygame.mixer inicializado (44.1kHz, buffer 512).")
            self.load_effects()
            self._apply_music_volume()
        except Exception as exc:  # pragma: no cover - depende del hardware
            self._available = False
            logger.warning("Audio no disponible (modo silencioso): %s", exc)
        return self._available

    def load_effects(self) -> None:
        """Carga en memoria cada efecto declarado en ``EFFECTS``.

        Da prioridad al sonido PERSONALIZADO del usuario; si no existe, usa el
        empaquetado. Inicializar los binarios en RAM evita demoras por lectura
        de disco al dispararlos (requisito de baja latencia de la guia V8).
        """
        if not self._available:
            return
        for name in self.EFFECTS:
            path = self._resolve_effect_path(name)
            if not path or not os.path.isfile(path):
                logger.warning("Efecto '%s' sin archivo.", name)
                continue
            try:
                self._sounds[name] = self._mixer.Sound(path)
            except Exception as exc:
                logger.warning("No se pudo cargar '%s': %s", name, exc)
        logger.info("Efectos cargados en memoria: %d", len(self._sounds))

    # ------------------------------------------------------------------ #
    # Personalizacion de sonidos
    # ------------------------------------------------------------------ #
    @staticmethod
    def _default_user_dir() -> str:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "ConsolaVirtualV8", "sfx")

    @property
    def user_dir(self) -> str:
        return self._user_dir

    def _stem(self, name: str) -> str:
        """Nombre de archivo base (sin extension) del efecto."""
        return os.path.splitext(os.path.basename(self.EFFECTS[name]))[0]

    def _resolve_effect_path(self, name: str) -> Optional[str]:
        """Ruta del efecto: primero el personalizado, luego el empaquetado."""
        stem = self._stem(name)
        for ext in SUPPORTED_EXTS:
            candidate = os.path.join(self._user_dir, stem + ext)
            if os.path.isfile(candidate):
                return candidate
        bundled = os.path.join(self._base_dir, self.EFFECTS[name])
        return bundled if os.path.isfile(bundled) else None

    def effect_source(self, name: str) -> Tuple[str, bool]:
        """Devuelve (ruta_actual, es_personalizado) del efecto."""
        stem = self._stem(name)
        for ext in SUPPORTED_EXTS:
            candidate = os.path.join(self._user_dir, stem + ext)
            if os.path.isfile(candidate):
                return candidate, True
        return os.path.join(self._base_dir, self.EFFECTS[name]), False

    def set_effect_file(self, name: str, src_path: str) -> bool:
        """Reemplaza el sonido de un efecto copiandolo a la carpeta de usuario.

        Acepta WAV/OGG/MP3. Recarga el efecto en memoria de inmediato.
        """
        if name not in self.EFFECTS:
            return False
        ext = os.path.splitext(src_path)[1].lower()
        if ext not in SUPPORTED_EXTS:
            logger.warning("Formato no soportado para '%s': %s", name, ext)
            return False
        stem = self._stem(name)
        # Elimina versiones previas (otras extensiones) para evitar ambiguedad.
        for old_ext in SUPPORTED_EXTS:
            old = os.path.join(self._user_dir, stem + old_ext)
            if os.path.isfile(old):
                try:
                    os.remove(old)
                except Exception:  # pragma: no cover
                    pass
        dest = os.path.join(self._user_dir, stem + ext)
        try:
            shutil.copyfile(src_path, dest)
        except Exception as exc:
            logger.warning("No se pudo copiar '%s': %s", src_path, exc)
            return False
        # Recarga solo este efecto.
        if self._available:
            try:
                with self._lock:
                    self._sounds[name] = self._mixer.Sound(dest)
            except Exception as exc:
                logger.warning("No se pudo recargar '%s': %s", name, exc)
                return False
        logger.info("Efecto '%s' personalizado -> %s", name, dest)
        return True

    def reset_effect(self, name: str) -> bool:
        """Restaura el sonido empaquetado original de un efecto."""
        if name not in self.EFFECTS:
            return False
        stem = self._stem(name)
        for ext in SUPPORTED_EXTS:
            custom = os.path.join(self._user_dir, stem + ext)
            if os.path.isfile(custom):
                try:
                    os.remove(custom)
                except Exception:  # pragma: no cover
                    pass
        bundled = os.path.join(self._base_dir, self.EFFECTS[name])
        if self._available and os.path.isfile(bundled):
            try:
                with self._lock:
                    self._sounds[name] = self._mixer.Sound(bundled)
            except Exception:  # pragma: no cover
                return False
        return True

    # ------------------------------------------------------------------ #
    # Reproduccion de efectos instantaneos
    # ------------------------------------------------------------------ #
    def play_effect(self, name: str) -> bool:
        """Dispara un efecto de forma inmediata y no bloqueante.

        ``pygame`` busca automaticamente un canal libre; la reproduccion ocurre
        en el hilo de audio nativo de SDL, por lo que no bloquea la red ni la UI.
        """
        with self._lock:
            sound = self._sounds.get(name)
        if not self._available or sound is None:
            logger.debug("play_effect('%s') ignorado (no disponible).", name)
            return False
        try:
            channel = self._mixer.find_channel(force=True)
            channel.set_volume(self._knobs["MONITOR"])
            channel.play(sound)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Fallo al reproducir '%s': %s", name, exc)
            return False

    # ------------------------------------------------------------------ #
    # Potenciometros (knobs)
    # ------------------------------------------------------------------ #
    def set_knob(self, control: str, value: float) -> None:
        """Actualiza el valor de un knob y aplica el efecto en la mezcla."""
        if control not in self._knobs:
            logger.debug("Knob desconocido: %s", control)
            return
        with self._lock:
            self._knobs[control] = float(value)
        if control in ("MUSIC",):
            self._apply_music_volume()

    def get_knob(self, control: str) -> float:
        with self._lock:
            return self._knobs.get(control, 0.0)

    def snapshot(self) -> Dict[str, object]:
        """Devuelve una copia del estado completo (para sincronizar clientes)."""
        with self._lock:
            return {
                "knobs": dict(self._knobs),
                "modes": dict(self._modes),
                "mic_active": self._mic_active,
            }

    # ------------------------------------------------------------------ #
    # Modos especiales y Dodge (ducking)
    # ------------------------------------------------------------------ #
    def set_mode(self, control: str, status: bool) -> None:
        if control not in self._modes:
            logger.debug("Modo desconocido: %s", control)
            return
        with self._lock:
            self._modes[control] = bool(status)
        if control == "Dodge":
            self._apply_music_volume()

    def simulate_mic_activity(self, active: bool) -> None:
        """Marca actividad de microfono para el ducking automatico (Dodge)."""
        with self._lock:
            self._mic_active = bool(active)
        self._apply_music_volume()

    def _apply_music_volume(self) -> None:
        """Calcula y aplica el volumen efectivo de la musica de fondo.

        Si Dodge esta activo y hay senal de microfono, atenua la musica el 70%.
        """
        with self._lock:
            base = self._knobs["MUSIC"]
            ducking = self._modes["Dodge"] and self._mic_active
            effective = base * (1.0 - self.DUCK_ATTENUATION) if ducking else base
        if self._available and self._mixer is not None:
            try:
                self._mixer.music.set_volume(effective)
            except Exception:  # pragma: no cover - sin pista cargada aun
                pass
        logger.debug("Volumen musica efectivo: %.2f (duck=%s)", effective, ducking)

    # ------------------------------------------------------------------ #
    # Musica de fondo opcional
    # ------------------------------------------------------------------ #
    def load_music(self, path: str) -> bool:
        """Carga una pista de fondo (controlada por el knob MUSIC)."""
        if not self._available:
            return False
        try:
            self._mixer.music.load(path)
            self._apply_music_volume()
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("No se pudo cargar musica '%s': %s", path, exc)
            return False

    def play_music(self, loops: int = -1) -> None:
        if self._available:
            try:
                self._mixer.music.play(loops)
            except Exception:  # pragma: no cover
                pass

    def shutdown(self) -> None:
        """Libera el subsistema de audio de forma ordenada."""
        if self._available and self._mixer is not None:
            try:
                self._mixer.quit()
            except Exception:  # pragma: no cover
                pass
        self._available = False
