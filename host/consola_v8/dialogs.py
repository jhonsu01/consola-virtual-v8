"""Dialogos del Host: gestion de sesiones y personalizacion de sonidos."""

from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtWidgets

from .audio_engine import AudioEngine
from .sessions import SessionManager

COLOR_ACCENT = "#ff5722"
COLOR_PANEL = "#262626"
COLOR_TEXT = "#e0e0e0"


class SessionsDialog(QtWidgets.QDialog):
    """Muestra los PINs de acceso y los dispositivos conectados.

    Permite agregar/revocar PINs y expulsar sesiones. Se refresca solo cada
    segundo mientras esta abierto.
    """

    def __init__(self, sessions: SessionManager,
                 kick: Callable[[str], None], parent=None) -> None:
        super().__init__(parent)
        self._sessions = sessions
        self._kick = kick
        self.setWindowTitle("Gestion de sesiones y PINs")
        self.resize(560, 460)
        self.setStyleSheet(_DIALOG_QSS)

        root = QtWidgets.QVBoxLayout(self)

        root.addWidget(self._header("PINs de acceso"))
        sub = QtWidgets.QLabel(
            "Comparte un PIN distinto con cada persona/dispositivo. Cualquier "
            "PIN valido permite conectarse simultaneamente.")
        sub.setWordWrap(True)
        sub.setObjectName("Hint")
        root.addWidget(sub)

        self.pins_box = QtWidgets.QVBoxLayout()
        pins_container = QtWidgets.QWidget()
        pins_container.setLayout(self.pins_box)
        root.addWidget(pins_container)

        add_btn = QtWidgets.QPushButton("+ Agregar nuevo PIN")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add_pin)
        root.addWidget(add_btn)

        root.addSpacing(10)
        root.addWidget(self._header("Dispositivos conectados"))
        self.sessions_box = QtWidgets.QVBoxLayout()
        sess_container = QtWidgets.QWidget()
        sess_container.setLayout(self.sessions_box)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(sess_container)
        root.addWidget(scroll, 1)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    @staticmethod
    def _header(text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        lbl.setObjectName("Header")
        return lbl

    def _clear(self, layout: QtWidgets.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_pin(self) -> None:
        self._sessions.add_pin()
        self.refresh()

    def refresh(self) -> None:
        # PINs
        self._clear(self.pins_box)
        pins = self._sessions.pins()
        for pin in pins:
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(pin)
            lbl.setObjectName("Pin")
            row.addWidget(lbl)
            row.addStretch(1)
            remove = QtWidgets.QPushButton("Revocar")
            remove.setEnabled(len(pins) > 1)
            remove.clicked.connect(lambda _=False, p=pin: self._remove_pin(p))
            row.addWidget(remove)
            wrap = QtWidgets.QWidget()
            wrap.setLayout(row)
            self.pins_box.addWidget(wrap)

        # Sesiones
        self._clear(self.sessions_box)
        sessions = self._sessions.sessions()
        if not sessions:
            empty = QtWidgets.QLabel("(sin dispositivos conectados)")
            empty.setObjectName("Hint")
            self.sessions_box.addWidget(empty)
        for sid, info in sessions.items():
            row = QtWidgets.QHBoxLayout()
            text = f"📱 {info.get('device','?')}   {info.get('ip','?')}   ·   PIN {info.get('pin','?')}"
            lbl = QtWidgets.QLabel(text)
            row.addWidget(lbl)
            row.addStretch(1)
            kick = QtWidgets.QPushButton("Expulsar")
            kick.clicked.connect(lambda _=False, s=sid: self._kick_session(s))
            row.addWidget(kick)
            wrap = QtWidgets.QWidget()
            wrap.setLayout(row)
            self.sessions_box.addWidget(wrap)

    def _remove_pin(self, pin: str) -> None:
        self._sessions.remove_pin(pin)
        self.refresh()

    def _kick_session(self, sid: str) -> None:
        self._kick(sid)
        QtCore.QTimer.singleShot(300, self.refresh)


class SoundsDialog(QtWidgets.QDialog):
    """Permite reemplazar el audio de cada uno de los 12 efectos."""

    def __init__(self, audio: AudioEngine, parent=None) -> None:
        super().__init__(parent)
        self._audio = audio
        self.setWindowTitle("Personalizar sonidos")
        self.resize(620, 560)
        self.setStyleSheet(_DIALOG_QSS)

        root = QtWidgets.QVBoxLayout(self)
        root.addWidget(self._header("Personalizar los efectos"))

        spec = QtWidgets.QLabel(
            "Formato: WAV u OGG recomendado (MP3 tambien funciona).\n"
            "Duracion: efectos cortos, idealmente entre 0.2 y 5 segundos "
            "(maximo recomendado 10 s).\n"
            "Calidad: 44.1 kHz, mono o estereo.\n"
            f"Los archivos se guardan en:  {audio.user_dir}")
        spec.setObjectName("Hint")
        spec.setWordWrap(True)
        root.addWidget(spec)
        root.addSpacing(6)

        rows = QtWidgets.QVBoxLayout()
        container = QtWidgets.QWidget()
        container.setLayout(rows)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self._labels = {}
        for name in AudioEngine.EFFECTS:
            row = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel(name)
            title.setMinimumWidth(110)
            title.setObjectName("Pin")
            src = QtWidgets.QLabel("")
            src.setObjectName("Hint")
            self._labels[name] = src

            change = QtWidgets.QPushButton("Cambiar...")
            change.clicked.connect(lambda _=False, n=name: self._change(n))
            test = QtWidgets.QPushButton("Probar")
            test.clicked.connect(lambda _=False, n=name: self._audio.play_effect(n))
            reset = QtWidgets.QPushButton("Original")
            reset.clicked.connect(lambda _=False, n=name: self._reset(n))

            row.addWidget(title)
            row.addWidget(src, 1)
            row.addWidget(change)
            row.addWidget(test)
            row.addWidget(reset)
            wrap = QtWidgets.QWidget()
            wrap.setLayout(row)
            rows.addWidget(wrap)

        close = QtWidgets.QPushButton("Cerrar")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        root.addWidget(close)

        self._refresh_all()

    @staticmethod
    def _header(text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        lbl.setObjectName("Header")
        return lbl

    def _refresh_all(self) -> None:
        import os
        for name, lbl in self._labels.items():
            path, custom = self._audio.effect_source(name)
            tag = "personalizado" if custom else "original"
            lbl.setText(f"{os.path.basename(path)}  ({tag})")

    def _change(self, name: str) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Elegir audio para '{name}'", "",
            "Audio (*.wav *.ogg *.mp3)")
        if not path:
            return
        if self._audio.set_effect_file(name, path):
            self._refresh_all()
        else:
            QtWidgets.QMessageBox.warning(
                self, "Formato no valido",
                "Usa un archivo WAV, OGG o MP3.")

    def _reset(self, name: str) -> None:
        self._audio.reset_effect(name)
        self._refresh_all()


_DIALOG_QSS = f"""
    QDialog {{ background: #1a1a1a; }}
    QLabel {{ color: {COLOR_TEXT}; font-size: 12px; }}
    QLabel#Header {{ color: {COLOR_ACCENT}; font-size: 15px; font-weight: bold; }}
    QLabel#Hint {{ color: #9aa0a6; font-size: 11px; }}
    QLabel#Pin {{ color: {COLOR_ACCENT}; font-size: 16px; font-weight: bold;
                 letter-spacing: 2px; font-family: 'Consolas', monospace; }}
    QPushButton {{ background: #333; color: {COLOR_TEXT}; border: 1px solid #555;
                  border-radius: 6px; padding: 5px 12px; }}
    QPushButton:hover {{ border-color: {COLOR_ACCENT}; }}
    QPushButton#Primary {{ background: {COLOR_ACCENT}; color: #1a1a1a; font-weight: bold;
                          border: none; padding: 8px; }}
    QScrollArea {{ border: none; }}
"""
