// Consola de Sonido Virtual V8 - Controlador remoto (Flutter / Dart).
//
// App de un solo archivo, optimizada para rendimiento tactil. Se conecta al
// Host Windows por WebSocket (ws://IP:8080) y replica los controles del
// hardware V8: 7 knobs, 6 modos naranjas y 12 efectos instantaneos.
//
// Protocolo (JSON plano):
//   {"event":"knob_update","control":"MIC","value":0.85}
//   {"event":"mode_toggle","control":"Dodge","status":true}
//   {"event":"effect_trigger","control":"Applause"}

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

// Paleta del tema oscuro --------------------------------------------------
const Color kBg = Color(0xFF1A1A1A);
const Color kPanel = Color(0xFF262626);
const Color kAccent = Color(0xFFFF5722); // naranja vibrante
const Color kText = Color(0xFFE0E0E0);
const Color kEffect = Color(0xFF333333);

const int kPort = 8080;

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

/// Pantalla inicial: pide la IP del Host e intenta abrir el WebSocket.
class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final TextEditingController _ipController =
      TextEditingController(text: '192.168.1.');
  String? _error;
  bool _connecting = false;

  Future<void> _connect() async {
    final ip = _ipController.text.trim();
    if (ip.isEmpty) {
      setState(() => _error = 'Ingresa la IP del Host');
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
        builder: (_) => ConsoleScreen(channel: channel, host: ip),
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
                  style: TextStyle(
                      color: kAccent,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.5)),
              const Text('Controlador remoto',
                  style: TextStyle(color: kText, fontSize: 14)),
              const SizedBox(height: 32),
              TextField(
                controller: _ipController,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: kText, fontSize: 18),
                decoration: InputDecoration(
                  labelText: 'IP del Host Windows',
                  hintText: 'Ej: 192.168.1.15',
                  prefixIcon: const Icon(Icons.wifi, color: kAccent),
                  filled: true,
                  fillColor: kPanel,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!,
                    style: const TextStyle(color: Colors.redAccent)),
              ],
              const SizedBox(height: 24),
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

  @override
  void dispose() {
    _ipController.dispose();
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

/// Pantalla principal: replica la consola y sincroniza con el Host.
class ConsoleScreen extends StatefulWidget {
  const ConsoleScreen({super.key, required this.channel, required this.host});
  final WebSocketChannel channel;
  final String host;

  @override
  State<ConsoleScreen> createState() => _ConsoleScreenState();
}

class _ConsoleScreenState extends State<ConsoleScreen> {
  final Map<String, double> _knobs = {
    'MIC': 0.8, 'ECHO': 0.0, 'TREBLE': 0.5, 'BASS': 0.5,
    'RECORD': 0.8, 'MUSIC': 0.7, 'MONITOR': 0.8,
  };
  final Map<String, bool> _modes = {for (final m in kModes) m: false};
  final _Throttle _throttle = _Throttle(const Duration(milliseconds: 33));
  late final StreamSubscription _sub;
  bool _connected = true;

  @override
  void initState() {
    super.initState();
    // Escucha eventos entrantes (eco del Host u otros clientes) para sincronizar.
    _sub = widget.channel.stream.listen(
      _onMessage,
      onDone: () => setState(() => _connected = false),
      onError: (_) => setState(() => _connected = false),
    );
  }

  void _onMessage(dynamic raw) {
    try {
      final data = jsonDecode(raw as String) as Map<String, dynamic>;
      final event = data['event'];
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
    if (!_connected) return;
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
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            children: [
              _buildTopBar(),
              const SizedBox(height: 8),
              Expanded(flex: 7, child: _buildKnobs()),
              const SizedBox(height: 8),
              Expanded(flex: 2, child: _buildModes()),
              const SizedBox(height: 8),
              Expanded(flex: 4, child: _buildEffects()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
          color: kPanel, borderRadius: BorderRadius.circular(10)),
      child: Row(
        children: [
          Icon(_connected ? Icons.cloud_done : Icons.cloud_off,
              color: _connected ? Colors.green : Colors.redAccent, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _connected ? 'Conectado a ${widget.host}' : 'Desconectado',
              style: const TextStyle(color: kText, fontSize: 13),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: kAccent, size: 20),
            tooltip: 'Desconectar',
            onPressed: () {
              widget.channel.sink.close();
              Navigator.of(context).pop();
            },
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
          width: 64,
          child: Text(name,
              style: const TextStyle(
                  color: kText, fontWeight: FontWeight.bold, fontSize: 12)),
        ),
        Expanded(
          child: Slider(
            value: value.clamp(0.0, 1.0),
            onChanged: (v) => _onKnob(name, v),
            onChangeEnd: (_) => _onKnobEnd(name),
          ),
        ),
        SizedBox(
          width: 44,
          child: Text(display,
              textAlign: TextAlign.right,
              style: const TextStyle(color: kAccent, fontSize: 12)),
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
                  child: Text(
                    m,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: active ? Colors.black : kText,
                      fontWeight: FontWeight.bold,
                      fontSize: 11,
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
      children: names.map((n) {
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: kEffect,
                foregroundColor: Colors.white,
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                    side: const BorderSide(color: Color(0xFF444444))),
              ),
              onPressed: () => _onEffect(n),
              child: FittedBox(
                child: Padding(
                  padding: const EdgeInsets.all(4),
                  child: Text(n, textAlign: TextAlign.center),
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  @override
  void dispose() {
    _throttle.dispose();
    _sub.cancel();
    widget.channel.sink.close();
    super.dispose();
  }
}
