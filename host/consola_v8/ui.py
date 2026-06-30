"""Interfaz grafica de la Consola Virtual V8 (PySide6, tema oscuro estricto).

Replica el hardware V8:
- 7 potenciometros rotativos (MIC, ECHO, TREBLE, BASS, RECORD, MUSIC, MONITOR).
- 6 botones de modo naranjas conmutables (Electro, Pitch Bend, Magic,
  Shock-Wave, MC, Dodge).
- 12 botones de efectos instantaneos en dos filas.
- Barra superior con la IP local y el estado del servidor de sockets.

La ventana solo EMITE senales de cambios; la logica de audio/red vive en
``app.py``. Tambien expone metodos ``apply_*`` para reflejar cambios que llegan
desde la app remota sin reenviarlos (evita bucles de eco).
"""

from __future__ import annotations

import math
from typing import Dict, List

from PySide6 import QtCore, QtGui, QtWidgets

# Paleta de tema oscuro -------------------------------------------------------
COLOR_BG = "#1a1a1a"
COLOR_PANEL = "#262626"
COLOR_TEXT = "#e0e0e0"
COLOR_ACCENT = "#ff5722"      # naranja vibrante de los modos
COLOR_EFFECT = "#333333"      # botones de efectos
COLOR_TRACK = "#3a3a3a"

KNOBS: List[str] = ["MIC", "ECHO", "TREBLE", "BASS", "RECORD", "MUSIC", "MONITOR"]
MODES: List[str] = ["Electro", "Pitch Bend", "Magic", "Shock-Wave", "MC", "Dodge"]
EFFECTS_ROW_2 = ["Despise", "Shot", "Beatings", "Coldfield", "Songs", "DogBarking"]
EFFECTS_ROW_3 = ["Laughter", "Applause", "Kiss", "Awkward", "Minions", "Time"]


class Knob(QtWidgets.QWidget):
    """Potenciometro rotativo dibujado a mano con indicador radial limpio.

    El valor interno siempre esta normalizado en ``[0.0, 1.0]`` para que el
    protocolo de red sea uniforme con la app Android. La conversion a dB de
    TREBLE/BASS es solo visual.
    """

    valueChanged = QtCore.Signal(float)

    SPAN = 270.0          # grados de barrido del knob
    START = 225.0         # angulo inicial (posicion 7:30)

    def __init__(self, label: str, value: float = 0.0, is_db: bool = False, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = max(0.0, min(1.0, value))
        self._is_db = is_db
        self._drag_y = None
        self.setMinimumSize(96, 118)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.setCursor(QtCore.Qt.SizeVerCursor)

    # -- API --------------------------------------------------------------- #
    def value(self) -> float:
        return self._value

    def setValue(self, v: float, emit: bool = True) -> None:
        v = max(0.0, min(1.0, float(v)))
        changed = abs(v - self._value) > 1e-6
        self._value = v
        self.update()
        if emit and changed:
            self.valueChanged.emit(v)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(110, 124)

    def _display_value(self) -> str:
        if self._is_db:
            return f"{(self._value * 24.0) - 12.0:+.0f} dB"
        return f"{int(round(self._value * 100))}"

    # -- Interaccion ------------------------------------------------------- #
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_y = event.position().y()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_y is None:
            return
        dy = self._drag_y - event.position().y()
        self._drag_y = event.position().y()
        self.setValue(self._value + dy / 150.0)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_y = None

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        self.setValue(self._value + event.angleDelta().y() / 1200.0)

    # -- Render ------------------------------------------------------------ #
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        side = min(self.width(), self.height() - 24)
        margin = 8
        diameter = side - 2 * margin
        cx = self.width() / 2.0
        cy = margin + diameter / 2.0
        radius = diameter / 2.0
        arc_rect = QtCore.QRectF(cx - radius, cy - radius, diameter, diameter)

        # Pista de fondo (arco gris).
        pen_bg = QtGui.QPen(QtGui.QColor(COLOR_TRACK), 6)
        pen_bg.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(arc_rect, int(self.START * 16), int(-self.SPAN * 16))

        # Arco de valor (naranja).
        pen_val = QtGui.QPen(QtGui.QColor(COLOR_ACCENT), 6)
        pen_val.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen_val)
        p.drawArc(arc_rect, int(self.START * 16), int(-self.SPAN * self._value * 16))

        # Cuerpo del knob.
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor("#1e1e1e"))
        p.drawEllipse(QtCore.QPointF(cx, cy), radius - 10, radius - 10)

        # Indicador radial.
        angle = math.radians(self.START - self.SPAN * self._value)
        x2 = cx + (radius - 12) * math.cos(angle)
        y2 = cy - (radius - 12) * math.sin(angle)
        x1 = cx + (radius - 26) * math.cos(angle)
        y1 = cy - (radius - 26) * math.sin(angle)
        pen_ind = QtGui.QPen(QtGui.QColor(COLOR_TEXT), 3)
        pen_ind.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen_ind)
        p.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))

        # Etiqueta + valor.
        p.setPen(QtGui.QColor(COLOR_TEXT))
        font = p.font()
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)
        label_rect = QtCore.QRectF(0, cy - 6, self.width(), 16)
        p.drawText(label_rect, QtCore.Qt.AlignCenter, self._label)

        font.setBold(False)
        font.setPointSize(7)
        p.setFont(font)
        p.setPen(QtGui.QColor(COLOR_ACCENT))
        val_rect = QtCore.QRectF(0, self.height() - 18, self.width(), 16)
        p.drawText(val_rect, QtCore.Qt.AlignCenter, self._display_value())
        p.end()


class ConsoleWindow(QtWidgets.QMainWindow):
    """Ventana principal del Host."""

    knobChanged = QtCore.Signal(str, float)
    modeToggled = QtCore.Signal(str, bool)
    effectTriggered = QtCore.Signal(str)
    firewallRequested = QtCore.Signal()
    regeneratePinRequested = QtCore.Signal()

    def __init__(self, version: str = "1.0.0"):
        super().__init__()
        self.setWindowTitle(f"Consola de Sonido Virtual V8  -  v{version}")
        self.resize(900, 640)

        self._knobs: Dict[str, Knob] = {}
        self._modes: Dict[str, QtWidgets.QToolButton] = {}

        self._build_ui()
        self._apply_styles()

    # -- Construccion ------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_knob_panel())
        root.addWidget(self._build_mode_panel())
        root.addWidget(self._build_effects_panel(), 1)

    def _build_top_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QFrame()
        bar.setObjectName("TopBar")
        outer = QtWidgets.QVBoxLayout(bar)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        # --- Fila 1: titulo + IP + estado ---
        row1 = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("CONSOLA VIRTUAL V8")
        title.setObjectName("Title")
        self.ip_label = QtWidgets.QLabel("IP local: --")
        self.ip_label.setObjectName("IpLabel")
        self.status_label = QtWidgets.QLabel("Servidor: iniciando...")
        self.status_label.setObjectName("StatusLabel")
        row1.addWidget(title)
        row1.addStretch(1)
        row1.addWidget(self.ip_label)
        row1.addSpacing(18)
        row1.addWidget(self.status_label)

        # --- Fila 2: PIN + acciones (Firewall / nuevo PIN) ---
        row2 = QtWidgets.QHBoxLayout()
        pin_caption = QtWidgets.QLabel("PIN de emparejamiento:")
        pin_caption.setObjectName("IpLabel")
        self.pin_label = QtWidgets.QLabel("----")
        self.pin_label.setObjectName("PinLabel")
        self.notify_label = QtWidgets.QLabel("")
        self.notify_label.setObjectName("StatusLabel")

        self.firewall_btn = QtWidgets.QPushButton("Abrir Firewall")
        self.firewall_btn.setObjectName("ActionButton")
        self.firewall_btn.setToolTip(
            "Crea la regla de Firewall para el puerto 8080. Pulsalo si el "
            "telefono no conecta (pedira permiso de administrador)."
        )
        self.firewall_btn.clicked.connect(self.firewallRequested.emit)

        self.newpin_btn = QtWidgets.QPushButton("Nuevo PIN")
        self.newpin_btn.setObjectName("ActionButton")
        self.newpin_btn.clicked.connect(self.regeneratePinRequested.emit)

        row2.addWidget(pin_caption)
        row2.addWidget(self.pin_label)
        row2.addSpacing(16)
        row2.addWidget(self.notify_label, 1)
        row2.addWidget(self.firewall_btn)
        row2.addWidget(self.newpin_btn)

        outer.addLayout(row1)
        outer.addLayout(row2)
        return bar

    # -- PIN y notificaciones --------------------------------------------- #
    def set_pin(self, pin: str) -> None:
        self.pin_label.setText(str(pin))

    def notify(self, message: str) -> None:
        """Muestra un mensaje transitorio en la barra superior."""
        self.notify_label.setText(message)
        QtCore.QTimer.singleShot(6000, lambda: self.notify_label.setText(""))

    def _build_knob_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QFrame()
        panel.setObjectName("Panel")
        layout = QtWidgets.QHBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        defaults = {"MIC": 0.8, "ECHO": 0.0, "TREBLE": 0.5, "BASS": 0.5,
                    "RECORD": 0.8, "MUSIC": 0.7, "MONITOR": 0.8}
        for name in KNOBS:
            is_db = name in ("TREBLE", "BASS")
            knob = Knob(name, value=defaults[name], is_db=is_db)
            knob.valueChanged.connect(lambda v, n=name: self.knobChanged.emit(n, v))
            self._knobs[name] = knob
            layout.addWidget(knob)
        return panel

    def _build_mode_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QFrame()
        panel.setObjectName("Panel")
        layout = QtWidgets.QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        for name in MODES:
            btn = QtWidgets.QToolButton()
            btn.setText(name)
            btn.setCheckable(True)
            btn.setObjectName("ModeButton")
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            btn.setMinimumHeight(46)
            btn.toggled.connect(lambda checked, n=name: self.modeToggled.emit(n, checked))
            self._modes[name] = btn
            layout.addWidget(btn)
        return panel

    def _build_effects_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QFrame()
        panel.setObjectName("Panel")
        grid = QtWidgets.QGridLayout(panel)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(10)

        for col, name in enumerate(EFFECTS_ROW_2):
            grid.addWidget(self._make_effect_button(name), 0, col)
        for col, name in enumerate(EFFECTS_ROW_3):
            grid.addWidget(self._make_effect_button(name), 1, col)
        return panel

    def _make_effect_button(self, name: str) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(name)
        btn.setObjectName("EffectButton")
        btn.setMinimumHeight(64)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        btn.clicked.connect(lambda _=False, n=name: self.effectTriggered.emit(n))
        return btn

    # -- Estado desde la red ---------------------------------------------- #
    @QtCore.Slot(str, float)
    def apply_knob(self, control: str, value: float) -> None:
        knob = self._knobs.get(control)
        if knob is not None:
            knob.setValue(value, emit=False)

    @QtCore.Slot(str, bool)
    def apply_mode(self, control: str, status: bool) -> None:
        btn = self._modes.get(control)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(status)
            btn.blockSignals(False)

    @QtCore.Slot(str)
    def flash_effect(self, control: str) -> None:
        """Realce visual breve cuando un cliente remoto dispara un efecto."""
        btn = None
        for child in self.findChildren(QtWidgets.QPushButton):
            if child.text() == control:
                btn = child
                break
        if btn is None:
            return
        btn.setStyleSheet(f"background:{COLOR_ACCENT};color:#000;")
        QtCore.QTimer.singleShot(180, lambda: btn.setStyleSheet(""))

    def set_network_info(self, ip: str, port: int, listening: bool) -> None:
        self.ip_label.setText(f"IP local: {ip}:{port}")
        if listening:
            self.status_label.setText("Servidor: ESCUCHANDO  ●")
            self.status_label.setProperty("ok", True)
        else:
            self.status_label.setText("Servidor: detenido")
            self.status_label.setProperty("ok", False)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_client_count(self, count: int) -> None:
        ip = self.ip_label.text()
        # No tocar IP; solo refresca el estado con el conteo de clientes.
        self.status_label.setText(f"Servidor: ESCUCHANDO  ●   clientes: {count}")

    # -- Estilos ----------------------------------------------------------- #
    def _apply_styles(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow {{ background: {COLOR_BG}; }}
            QWidget {{ color: {COLOR_TEXT}; font-family: 'Segoe UI', Arial; }}
            #TopBar {{ background: {COLOR_PANEL}; border-radius: 10px; }}
            #Title {{ font-size: 16px; font-weight: bold; color: {COLOR_ACCENT}; }}
            #IpLabel {{ font-size: 12px; color: {COLOR_TEXT}; }}
            #StatusLabel {{ font-size: 12px; color: #9aa0a6; }}
            #StatusLabel[ok="true"] {{ color: #4caf50; }}
            #PinLabel {{
                font-size: 18px; font-weight: bold; color: {COLOR_ACCENT};
                letter-spacing: 4px; font-family: 'Consolas', monospace;
            }}
            #ActionButton {{
                background: {COLOR_EFFECT}; color: {COLOR_TEXT};
                border: 1px solid {COLOR_ACCENT}; border-radius: 6px;
                padding: 4px 12px; font-size: 12px;
            }}
            #ActionButton:hover {{ background: {COLOR_ACCENT}; color: #1a1a1a; }}
            #Panel {{ background: {COLOR_PANEL}; border-radius: 12px; }}
            #ModeButton {{
                background: #3a2014; color: {COLOR_TEXT};
                border: 2px solid {COLOR_ACCENT}; border-radius: 8px;
                font-weight: bold; font-size: 12px; padding: 4px;
            }}
            #ModeButton:checked {{
                background: {COLOR_ACCENT}; color: #1a1a1a;
            }}
            #ModeButton:hover {{ border-color: #ff8a65; }}
            #EffectButton {{
                background: {COLOR_EFFECT}; color: white;
                border: 1px solid #444; border-radius: 8px;
                font-size: 13px; font-weight: 600;
            }}
            #EffectButton:hover {{ background: #404040; border-color: {COLOR_ACCENT}; }}
            #EffectButton:pressed {{ background: {COLOR_ACCENT}; color: #000; }}
        """)
