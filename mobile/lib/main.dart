// Consola de Sonido Virtual V8 - Controlador remoto (Flutter / Dart).
//
// App de un solo archivo, optimizada para rendimiento tactil. Se conecta al
// Host Windows por WebSocket (ws://IP:8080) y replica los controles del
// hardware V8: 7 knobs, 6 modos naranjas y 12 efectos instantaneos.
//
// v1.1.0:
//   - Autodescubrimiento del Host en la LAN (sondeo UDP en el puerto 8079).
//   - Emparejamiento por PIN: tras conectar, se envia {"event":"auth","pin":...}
//     y se espera {"event":"auth_result","status":"ok"}.
//
// Protocolo (JSON plano):
//   {"event":"auth","pin":"1234","device":"Android"}
//   {"event":"knob_update","control":"MIC","value":0.85}
//   {"event":"mode_toggle","control":"Dodge","status":true}
//   {"event":"effect_trigger","control":"Applause"}

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

// Paleta del tema oscuro --------------------------------------------------
const Color kBg = Color(0xFF1A1A1A);
const Color kPanel = Color(0xFF262626);
const Color kAccent = Color(0xFFFF5722); // naranja vibrante
const Color kText = Color(0xFFE0E0E0);
const Color kEffect = Color(0xFF333333);

const int kPort = 8080;
const int kDiscoveryPort = 8079;
const String kProbe = 'CONSOLA_V8_DISCOVER';

const List<String> kKnobs = [
  'MIC', 'ECHO', 'TREBLE', 'BASS', 'RECORD', 'MUSIC', 'MONITOR'
];
const List<String> kModes = [
  'Electro', 'Pitch Bend', 'Magic', 'Shock-Wave', 'MC', 'Dodge'
];
const List<String> kEffectsRow2 = [
  'Despise', 'Shot', 'Beatings', 'Coldfield', 'Songs', 'DogBarking'
];
const List<String> kEffectsRow3 = [
  'Laughter', 'Applause', 'Kiss', 'Awkward', 'Minions', 'Time'
];

void main() => runApp(const ConsolaV8App());

class ConsolaV8App extends StatelessWidget {
  const ConsolaV8App({super.key});

  @override
  Widget build(BuildContext context) {
    final base = ThemeData.dark(useMaterial3: true);
    return MaterialApp(
      title: 'Consola V8 Remote',
      debugShowCheckedModeBanner: false,
      theme: base.copyWith(
        scaffoldBackgroundColor: kBg,
        colorScheme: base.colorScheme.copyWith(
          primary: kAccent,
          secondary: kAccent,
          surface: kPanel,
        ),
        sliderTheme: base.sliderTheme.copyWith(
          activeTrackColor: kAccent,
          inactiveTrackColor: kEffect,
          thumbColor: kAccent,
          overlayColor: kAccent.withOpacity(0.2),
        ),
      ),
      home: const ConnectScreen(),
    );
  }
}

/// Busca el Host en la LAN enviando un sondeo UDP en broadcast y esperando la
/// respuesta del DiscoveryResponder del Host. Devuelve la IP o null.
Future<String?> discoverHost({Duration timeout = const Duration(seconds: 3)}) async {
  RawDatagramSocket? socket;
  final completer = Completer<String?>();
  try {
    socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
    socket.broadcastEnabled = true;
    final probe = utf8.encode(kProbe);
    final target = InternetAddress('255.255.255.255');

    socket.listen((event) {
      if (event == RawSocketEvent.read) {
        final dg = socket!.receive();
        if (dg == null) return;
        try {
          final data = jsonDecode(utf8.decode(dg.data)) as Map<String, dynamic>;
          if (data['app'] == 'ConsolaV8' && data['ip'] is String) {
            if (!completer.isCompleted) completer.complete(data['ip'] as String);
          }
        } catch (_) {}
      }
    });

    // Envia el sondeo varias veces para mayor fiabilidad en redes con perdida.
    socket.send(probe, target, kDiscoveryPort);
    Timer(const Duration(milliseconds: 350),
        () => socket?.send(probe, target, kDiscoveryPort));
    Timer(const Duration(milliseconds: 900),
        () => socket?.send(probe, target, kDiscoveryPort));

    return await completer.future.timeout(timeout, onTimeout: () => null);
  } catch (_) {
    return null;
  } finally {
    socket?.close();
  }
}

/// Pantalla inicial: autodescubre la IP, pide el PIN y abre el WebSocket.
class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final TextEditingController _ipController = TextEditingController();
  final TextEditingController _pinController = TextEditingController();
  String? _error;
  String _discoveryMsg = '';
  bool _connecting = false;
  bool _discovering = false;

  @override
  void initState() {
    super.initState();
    // Intenta autodetectar el Host al abrir la pantalla.
    WidgetsBinding.instance.addPostFrameCallback((_) => _autoDiscover());
  }

  Future<void> _autoDiscover() async {
    setState(() {
      _discovering = true;
      _discoveryMsg = 'Buscando el Host en la red...';
    });
    final ip = await discoverHost();
    if (!mounted) return;
    setState(() {
      _discovering = false;
      if (ip != null) {
        _ipController.text = ip;
        _discoveryMsg = 'Host detectado: $ip';
      } else {
        _discoveryMsg = 'No se detecto automaticamente. Ingresa la IP manual.';
      }
    });
  }

  Future<void> _connect() async {
    final ip = _ipController.text.trim();
    final pin = _pinController.text.trim();
    if (ip.isEmpty) {
      setState(() => _error = 'Ingresa o detecta la IP del Host');
      return;
    }
    setState(() {
      _connecting = true;
      _error = null;
    });
    try {
      final channel = WebSocketChannel.connect(Uri.parse('ws://$ip:$kPort'));
      await channel.ready; // lanza excepcion si no conecta
      if (!mounted) return;
      Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => ConsoleScreen(channel: channel, host: ip, pin: pin),
      ));
    } catch (e) {
      setState(() => _error = 'No se pudo conectar a $ip:$kPort');
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.graphic_eq, color: kAccent, size: 72),
              const SizedBox(height: 12),
              const Text('CONSOLA VIRTUAL V8',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      color: kAccent,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.5)),
              const Text('Controlador remoto',
                  style: TextStyle(color: kText, fontSize: 14)),
              const SizedBox(height: 28),
              TextField(
                controller: _ipController,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: kText, fontSize: 18),
                decoration: _decoration(
                  label: 'IP del Host Windows',
                  hint: 'Ej: 192.168.1.15',
                  icon: Icons.wifi,
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: Text(_discoveryMsg,
                        style: TextStyle(
                            color: _discovering ? kAccent : kText, fontSize: 12)),
                  ),
                  TextButton.icon(
                    onPressed: _discovering ? null : _autoDiscover,
                    icon: _discovering
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: kAccent))
                        : const Icon(Icons.radar, color: kAccent, size: 18),
                    label: const Text('Buscar',
                        style: TextStyle(color: kAccent)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _pinController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                style: const TextStyle(color: kText, fontSize: 18, letterSpacing: 4),
                decoration: _decoration(
                  label: 'PIN de emparejamiento',
                  hint: 'Mostrado en el Host',
                  icon: Icons.lock,
                ).copyWith(counterText: ''),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: Colors.redAccent)),
              ],
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: kAccent,
                    foregroundColor: Colors.black,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: _connecting ? null : _connect,
                  icon: _connecting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.black))
                      : const Icon(Icons.power_settings_new),
                  label: Text(_connecting ? 'Conectando...' : 'CONECTAR'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  InputDecoration _decoration(
      {required String label, required String hint, required IconData icon}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      prefixIcon: Icon(icon, color: kAccent),
      filled: true,
      fillColor: kPanel,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide.none,
      ),
    );
  }

  @override
  void dispose() {
    _ipController.dispose();
    _pinController.dispose();
    super.dispose();
  }
}

/// Limita la frecuencia de envio de eventos para no saturar el socket,
/// pero garantizando que el ultimo valor siempre se entregue.
class _Throttle {
  _Throttle(this.interval);
  final Duration interval;
  Timer? _timer;
  void Function()? _pending;

  void run(void Function() action) {
    if (_timer == null) {
      action();
      _timer = Timer(interval, _flush);
    } else {
      _pending = action;
    }
  }

  void _flush() {
    if (_pending != null) {
      final action = _pending!;
      _pending = null;
      action();
      _timer = Timer(interval, _flush);
    } else {
      _timer = null;
    }
  }

  void dispose() => _timer?.cancel();
}

/// Pantalla principal: autentica con PIN, replica la consola y sincroniza.
class ConsoleScreen extends StatefulWidget {
  const ConsoleScreen(
      {super.key, required this.channel, required this.host, required this.pin});
  final WebSocketChannel channel;
  final String host;
  final String pin;

  @override
  State<ConsoleScreen> createState() => _ConsoleScreenState();
}

enum _Auth { connecting, ok, fail }

class _ConsoleScreenState extends State<ConsoleScreen> {
  final Map<String, double> _knobs = {
    'MIC': 0.8, 'ECHO': 0.0, 'TREBLE': 0.5, 'BASS': 0.5,
    'RECORD': 0.8, 'MUSIC': 0.7, 'MONITOR': 0.8,
  };
  final Map<String, bool> _modes = {for (final m in kModes) m: false};
  final _Throttle _throttle = _Throttle(const Duration(milliseconds: 33));
  late final StreamSubscription _sub;
  Timer? _authTimer;
  _Auth _auth = _Auth.connecting;

  @override
  void initState() {
    super.initState();
    _sub = widget.channel.stream.listen(
      _onMessage,
      onDone: () {
        if (mounted && _auth == _Auth.connecting) {
          setState(() => _auth = _Auth.fail);
        }
      },
      onError: (_) {
        if (mounted) setState(() => _auth = _Auth.fail);
      },
    );
    // Handshake de emparejamiento.
    widget.channel.sink
        .add(jsonEncode({'event': 'auth', 'pin': widget.pin, 'device': 'Android'}));
    _authTimer = Timer(const Duration(seconds: 8), () {
      if (mounted && _auth == _Auth.connecting) setState(() => _auth = _Auth.fail);
    });
  }

  void _onMessage(dynamic raw) {
    try {
      final data = jsonDecode(raw as String) as Map<String, dynamic>;
      final event = data['event'];
      if (event == 'auth_result') {
        setState(() => _auth = data['status'] == 'ok' ? _Auth.ok : _Auth.fail);
        return;
      }
      if (event == 'state_sync') {
        setState(() {
          final knobs = (data['knobs'] as Map?) ?? {};
          knobs.forEach((k, v) {
            if (_knobs.containsKey(k)) _knobs[k] = (v as num).toDouble();
          });
          final modes = (data['modes'] as Map?) ?? {};
          modes.forEach((k, v) {
            if (_modes.containsKey(k)) _modes[k] = v == true;
          });
        });
        return;
      }
      final control = data['control'] as String?;
      if (control == null) return;
      setState(() {
        if (event == 'knob_update' && _knobs.containsKey(control)) {
          _knobs[control] = (data['value'] as num).toDouble();
        } else if (event == 'mode_toggle' && _modes.containsKey(control)) {
          _modes[control] = data['status'] == true;
        }
      });
    } catch (_) {
      // Mensaje malformado: se ignora.
    }
  }

  void _send(Map<String, dynamic> msg) {
    if (_auth != _Auth.ok) return;
    widget.channel.sink.add(jsonEncode(msg));
  }

  void _onKnob(String name, double value) {
    setState(() => _knobs[name] = value);
    _throttle.run(() => _send({
          'event': 'knob_update',
          'control': name,
          'value': double.parse(value.toStringAsFixed(4)),
        }));
  }

  void _onKnobEnd(String name) {
    _send({
      'event': 'knob_update',
      'control': name,
      'value': double.parse(_knobs[name]!.toStringAsFixed(4)),
    });
  }

  void _onMode(String name) {
    final next = !_modes[name]!;
    setState(() => _modes[name] = next);
    _send({'event': 'mode_toggle', 'control': name, 'status': next});
  }

  void _onEffect(String name) {
    _send({'event': 'effect_trigger', 'control': name});
  }

  @override
  Widget build(BuildContext context) {
    if (_auth != _Auth.ok) return _buildAuthOverlay();
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: OrientationBuilder(
            builder: (context, orientation) => orientation == Orientation.portrait
                ? _buildPortrait()
                : _buildLandscape(),
          ),
        ),
      ),
    );
  }

  // Vertical: pila de paneles que llenan toda la altura.
  Widget _buildPortrait() {
    return Column(
      children: [
        _buildTopBar(),
        const SizedBox(height: 8),
        Expanded(flex: 7, child: _buildKnobs()),
        const SizedBox(height: 8),
        Expanded(flex: 3, child: _buildModes()),
        const SizedBox(height: 8),
        Expanded(flex: 5, child: _buildEffects()),
      ],
    );
  }

  // Horizontal: knobs a la izquierda; modos + efectos a la derecha. Asi se
  // aprovecha el ancho y no queda "aplanado".
  Widget _buildLandscape() {
    return Column(
      children: [
        _buildTopBar(),
        const SizedBox(height: 8),
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(flex: 5, child: _buildKnobs()),
              const SizedBox(width: 8),
              Expanded(
                flex: 5,
                child: Column(
                  children: [
                    Expanded(flex: 3, child: _buildModes()),
                    const SizedBox(height: 8),
                    Expanded(flex: 5, child: _buildEffects()),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAuthOverlay() {
    final connecting = _auth == _Auth.connecting;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(connecting ? Icons.lock_clock : Icons.lock_outline,
                color: kAccent, size: 64),
            const SizedBox(height: 16),
            Text(
              connecting ? 'Verificando PIN...' : 'PIN incorrecto o sin respuesta',
              style: const TextStyle(color: kText, fontSize: 16),
            ),
            const SizedBox(height: 20),
            if (connecting)
              const CircularProgressIndicator(color: kAccent)
            else
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                    backgroundColor: kAccent, foregroundColor: Colors.black),
                onPressed: () {
                  widget.channel.sink.close();
                  Navigator.of(context).pop();
                },
                icon: const Icon(Icons.arrow_back),
                label: const Text('Volver'),
              ),
          ],
        ),
      ),
    );
  }

  // Aviso de conexion discreto: un punto verde, la IP en gris tenue y un
  // pequeno boton para desconectar.
  Widget _buildTopBar() {
    return SizedBox(
      height: 22,
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
                color: Color(0xFF4CAF50), shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(widget.host,
                style: const TextStyle(color: Color(0xFF777777), fontSize: 11)),
          ),
          InkWell(
            onTap: () {
              widget.channel.sink.close();
              Navigator.of(context).pop();
            },
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              child: Icon(Icons.logout, color: Color(0xFF777777), size: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildKnobs() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
          color: kPanel, borderRadius: BorderRadius.circular(12)),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: kKnobs.map(_buildKnobRow).toList(),
      ),
    );
  }

  Widget _buildKnobRow(String name) {
    final value = _knobs[name]!;
    final isDb = name == 'TREBLE' || name == 'BASS';
    final display =
        isDb ? '${(value * 24 - 12).round()} dB' : '${(value * 100).round()}';
    return Row(
      children: [
        SizedBox(
          width: 74,
          child: Text(name,
              style: const TextStyle(
                  color: kText, fontWeight: FontWeight.bold, fontSize: 14)),
        ),
        Expanded(
          child: Slider(
            value: value.clamp(0.0, 1.0),
            onChanged: (v) => _onKnob(name, v),
            onChangeEnd: (_) => _onKnobEnd(name),
          ),
        ),
        SizedBox(
          width: 50,
          child: Text(display,
              textAlign: TextAlign.right,
              style: const TextStyle(
                  color: kAccent, fontSize: 14, fontWeight: FontWeight.w600)),
        ),
      ],
    );
  }

  Widget _buildModes() {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
          color: kPanel, borderRadius: BorderRadius.circular(12)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: kModes.map((m) {
          final active = _modes[m]!;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: GestureDetector(
                onTap: () => _onMode(m),
                child: Container(
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: active ? kAccent : const Color(0xFF3A2014),
                    border: Border.all(color: kAccent, width: 2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Padding(
                      padding: const EdgeInsets.all(4),
                      child: Text(
                        m,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: active ? Colors.black : kText,
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildEffects() {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
          color: kPanel, borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          Expanded(child: _buildEffectRow(kEffectsRow2)),
          const SizedBox(height: 8),
          Expanded(child: _buildEffectRow(kEffectsRow3)),
        ],
      ),
    );
  }

  Widget _buildEffectRow(List<String> names) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: names.map((n) {
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: kEffect,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.all(4),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                    side: const BorderSide(color: Color(0xFF444444))),
              ),
              onPressed: () => _onEffect(n),
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(n,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w600)),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  @override
  void dispose() {
    _authTimer?.cancel();
    _throttle.dispose();
    _sub.cancel();
    widget.channel.sink.close();
    super.dispose();
  }
}
