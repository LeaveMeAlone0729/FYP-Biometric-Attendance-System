import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import '../services/network_ble_test_api.dart';

class NetworkBleTestScreen extends StatefulWidget {
  const NetworkBleTestScreen({super.key, this.api, this.initialPin = ''});
  final NetworkBleTestApi? api;
  final String initialPin;
  @override
  State<NetworkBleTestScreen> createState() => _NetworkBleTestScreenState();
}

class _NetworkBleTestScreenState extends State<NetworkBleTestScreen> {
  late final _api = widget.api ?? NetworkBleTestApi();
  late final _pin = TextEditingController(text: widget.initialPin);
  List<Map<String, dynamic>> _sessions = [];
  int? _session;
  bool _busy = true;
  Map<String, dynamic>? _result;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
      _result = null;
    });
    try {
      final rows = await _api.sessions();
      if (mounted) {
        setState(() {
          _sessions = rows;
          _session = rows.firstOrNull?['session_id'] as int?;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException && error.status == 404
              ? 'TEST MODE DISABLED'
              : 'Unable to load test sessions. Check the backend connection.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _run() async {
    if (_busy || _session == null) return;
    setState(() {
      _busy = true;
      _result = null;
      _error = null;
    });
    try {
      final result = await _api.run(_session!, _pin.text.trim());
      if (mounted) setState(() => _result = result);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? '${error.code ?? (error.status == 404 ? 'TEST_MODE_DISABLED' : 'TEST_REQUEST_FAILED')} — ${error.message}'
              : 'TEST_RESULT_UNAVAILABLE — No complete server result was confirmed.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    unawaited(_api.cancel().catchError((Object _) {}));
    _pin.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Network + BLE Test')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Temporary diagnostic simulation. No attendance is recorded.',
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<int>(
          key: ValueKey(_session),
          initialValue: _session,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Open test session'),
          items: _sessions
              .map(
                (row) => DropdownMenuItem(
                  value: row['session_id'] as int,
                  child: Text(
                    'Session ${row['session_id']} · ${row['classroom_id']}',
                  ),
                ),
              )
              .toList(),
          onChanged: _busy
              ? null
              : (value) => setState(() {
                  _session = value;
                  _result = null;
                  _error = null;
                }),
        ),
        if (!_busy && _sessions.isEmpty)
          const Text('No eligible open session with a classroom.'),
        const SizedBox(height: 12),
        TextField(
          controller: _pin,
          enabled: !_busy,
          obscureText: true,
          keyboardType: TextInputType.number,
          inputFormatters: [
            FilteringTextInputFormatter.digitsOnly,
            LengthLimitingTextInputFormatter(6),
          ],
          decoration: const InputDecoration(labelText: 'Session PIN'),
          onChanged: (_) => setState(() {
            _result = null;
            _error = null;
          }),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: _busy || _session == null ? null : _run,
          child: const Text('Run diagnostic test'),
        ),
        TextButton(
          onPressed: _busy ? null : _load,
          child: const Text('Refresh sessions'),
        ),
        if (_busy) const Center(child: CircularProgressIndicator()),
        if (_error != null) ...[
          const Text(
            'TEST FAIL',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          Text(_error!),
        ],
        if (_result != null) ...[
          Semantics(
            liveRegion: true,
            child: Text(
              'TEST ${_result!['test_result']}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
          ),
          Text('Reason: ${_result!['reason_code']}'),
          Text(
            'Session ${_result!['session_id']} · ${_result!['classroom_id']}',
          ),
          for (final (key, label) in [
            ('network', 'CIDR network'),
            ('wifi', 'Classroom Wi-Fi'),
            ('ble', 'BLE beacon'),
          ])
            Text(
              '$label: ${_result![key] is Map ? '${_result![key]['result']} · ${_result![key]['reason_code']}' : 'NOT CHECKED'}',
            ),
        ],
      ],
    ),
  );
}
