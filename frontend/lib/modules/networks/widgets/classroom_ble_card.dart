import 'dart:async';
import 'package:flutter/material.dart';
import '../../../services/api_client.dart';
import '../services/classroom_ble_api.dart';
import '../services/classroom_ble_observation.dart';

class ClassroomBleCard extends StatefulWidget {
  const ClassroomBleCard({super.key, this.api});
  final ClassroomBleApi? api;
  @override
  State<ClassroomBleCard> createState() => _ClassroomBleCardState();
}

class _ClassroomBleCardState extends State<ClassroomBleCard>
    with WidgetsBindingObserver {
  late final _api = widget.api ?? ClassroomBleApi();
  List<Map<String, dynamic>> _rooms = [];
  String? _room, _error, _code;
  String _errorResult = 'UNCERTAIN';
  Map<String, dynamic>? _result;
  ClassroomBleObservation? _observation;
  bool _busy = false;
  int _generation = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  String explanation(Object e) {
    if (e is ApiException) {
      if (e.status == 404 && e.code == null) {
        return 'Classroom BLE observation is unavailable on this backend.';
      }
      if (['NETWORK_ERROR', 'REQUEST_TIMEOUT'].contains(e.code)) {
        return 'Unable to reach the verification server. No BLE policy decision was confirmed.';
      }
      return e.message;
    }
    return 'The BLE check could not be confirmed. Check the backend connection and Android scanner, then retry.';
  }

  Future<void> _load() async {
    if (_busy) return;
    final gen = ++_generation;
    setState(() {
      _busy = true;
      _result = null;
      _observation = null;
      _error = null;
      _code = null;
      _errorResult = 'UNCERTAIN';
    });
    try {
      final rooms = await _api.classrooms();
      if (mounted && gen == _generation) {
        setState(() {
          _rooms = rooms;
          _room = rooms.isEmpty ? null : rooms.first['classroom_id'] as String;
        });
      }
    } catch (e) {
      if (mounted && gen == _generation) {
        setState(() {
          _rooms = [];
          _room = null;
          _error = explanation(e);
          _code = e is ApiException ? e.code : 'BLE_UNAVAILABLE';
        });
      }
    } finally {
      if (mounted && gen == _generation) setState(() => _busy = false);
    }
  }

  Future<void> _observe(Map<String, int> thresholds) async {
    if (_busy || thresholds.isEmpty) return;
    final gen = ++_generation;
    setState(() {
      _busy = true;
      _observation = null;
      _result = null;
      _error = null;
      _code = null;
    });
    try {
      final observation = await _api.observe(thresholds);
      if (mounted && gen == _generation) {
        setState(() => _observation = observation);
      }
    } catch (_) {
      if (mounted && gen == _generation) {
        setState(() {
          _observation = const ClassroomBleObservation(
            BleObservationStatus.unavailable,
            'BLE_UNAVAILABLE',
          );
        });
      }
    } finally {
      if (mounted && gen == _generation) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    if (_busy || _room == null) return;
    final gen = ++_generation;
    setState(() {
      _busy = true;
      _observation = null;
      _result = null;
      _error = null;
      _code = null;
    });
    try {
      final result = await _api
          .verify(_room!)
          .timeout(const Duration(seconds: 45));
      if (mounted && gen == _generation) setState(() => _result = result);
    } catch (e) {
      unawaited(_api.cancel());
      if (mounted && gen == _generation) {
        setState(() {
          _error = explanation(e);
          _code = e is ApiException ? e.code : 'BLE_CHECK_UNCONFIRMED';
          _errorResult =
              e is ApiException &&
                  e.status >= 400 &&
                  e.status < 500 &&
                  (e.status != 404 || e.code != null)
              ? 'FAIL'
              : 'UNCERTAIN';
        });
      }
    } finally {
      if (mounted && gen == _generation) setState(() => _busy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      _generation++;
      unawaited(_api.cancel());
      setState(() {
        _busy = false;
        _result = null;
        _observation = null;
        _error = null;
      });
    }
  }

  @override
  void dispose() {
    _generation++;
    unawaited(_api.cancel());
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final selected = _rooms
        .where((r) => r['classroom_id'] == _room)
        .firstOrNull;
    final policies = selected?['policies'] as List? ?? const [];
    final thresholds = <String, int>{
      for (final p in policies)
        if (p is Map &&
            p['enabled'] == true &&
            p['service_uuid'] is String &&
            p['rssi_threshold'] is int)
          (p['service_uuid'] as String).toLowerCase():
              p['rssi_threshold'] as int,
    };
    final observation = _observation;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Classroom BLE Observation',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Text(
              'Scan for a configured classroom beacon. UUID and RSSI are diagnostic observations only and do not authorize attendance.',
            ),
            if (_rooms.isNotEmpty)
              DropdownButtonFormField<String>(
                key: ValueKey(_room),
                initialValue: _room,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'BLE test classroom',
                ),
                items: _rooms
                    .map(
                      (r) => DropdownMenuItem(
                        value: r['classroom_id'] as String,
                        child: Text(r['name'] as String),
                      ),
                    )
                    .toList(),
                onChanged: _busy
                    ? null
                    : (v) => setState(() {
                        _room = v;
                        _result = null;
                        _observation = null;
                        _error = null;
                        _code = null;
                      }),
              ),
            if (selected != null)
              ...(policies.map(
                (p) => Text(
                  '${p['label'] ?? p['policy_id']}: ${p['service_uuid']}\n${p['enabled'] == true ? 'Enabled' : 'Disabled'} · signal reference ${p['rssi_threshold']} dBm',
                ),
              )),
            if (!_busy && selected != null && thresholds.isEmpty)
              const Text('No enabled BLE policy for this classroom.'),
            if (_busy)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Row(
                  children: [
                    SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        key: ValueKey('classroom-ble-progress'),
                      ),
                    ),
                    SizedBox(width: 12),
                    Flexible(child: Text('Checking classroom beacon…')),
                  ],
                ),
              ),
            if (observation != null) ...[
              Text(switch (observation.status) {
                BleObservationStatus.detected => 'Beacon detected',
                BleObservationStatus.notDetected =>
                  'Configured beacon not detected',
                BleObservationStatus.unavailable =>
                  'BLE observation unavailable',
              }, style: const TextStyle(fontWeight: FontWeight.bold)),
              if (observation.durationMs > 0)
                Text(
                  'Scan duration: ${(observation.durationMs / 1000).toStringAsFixed(1)} s',
                ),
              if (observation.status == BleObservationStatus.notDetected)
                const Text('Matching advertisements: 0'),
              for (final beacon in observation.beacons) ...[
                Text(beacon.uuid),
                Text('Matching advertisements: ${beacon.advertisements}'),
                Text('Median RSSI: ${beacon.medianRssi} dBm'),
                if (beacon.weak)
                  const Text(
                    'Weak signal relative to the configured reference.',
                  ),
              ],
              if (observation.status == BleObservationStatus.unavailable)
                Text(switch (observation.reason) {
                  'BLUETOOTH_OFF' => 'Turn Bluetooth on and retry.',
                  'BLE_PERMISSION_REQUIRED' =>
                    'Allow Nearby Devices in BLE Diagnostics.',
                  'LOCATION_PERMISSION_REQUIRED' =>
                    'Allow precise location in BLE Diagnostics.',
                  'LOCATION_DISABLED' => 'Turn on Android Location Services.',
                  'BLE_SCAN_TIMEOUT' =>
                    'The scan timed out. Start a fresh scan.',
                  'BLE_EVIDENCE_STALE' =>
                    'The scan was stale or the clock changed. Scan again.',
                  'BLE_SCAN_INCOMPLETE' || 'STOPPED' || 'CANCELLED' =>
                    'The scan did not finish. Run the full eight-second scan.',
                  _ =>
                    'The scanner could not complete the observation. Check BLE Diagnostics and retry.',
                }),
            ],
            if (_result != null) ...[
              Text(
                'Classroom BLE verification: ${_result!['result']}',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: _result!['result'] == 'PASS'
                      ? Colors.green
                      : _result!['result'] == 'FAIL'
                      ? Colors.red
                      : Colors.orange.shade800,
                ),
              ),
              Text('Reason: ${_result!['reason_code']}'),
              Text(_result!['message'] as String),
              Text('Approved-beacon samples: ${_result!['sample_count']}'),
              if (_result!['scan_duration_ms'] is int)
                Text(
                  'Scan duration: ${(_result!['scan_duration_ms'] / 1000).toStringAsFixed(1)} s',
                ),
              if (_result!['median_rssi_dbm'] != null)
                Text('Server median: ${_result!['median_rssi_dbm']} dBm'),
              if (_result!['rssi_threshold'] != null)
                Text(
                  'Experimental threshold: ${_result!['rssi_threshold']} dBm',
                ),
            ],
            if (_error != null) ...[
              Text(
                'Classroom BLE verification: $_errorResult',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              Text('Reason: ${_code ?? 'BLE_UNAVAILABLE'}'),
              Text(_error!),
            ],
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: _busy || thresholds.isEmpty
                      ? null
                      : () => _observe(thresholds),
                  child: const Text('Observe classroom beacon (8 seconds)'),
                ),
                OutlinedButton(
                  onPressed: _busy || thresholds.isEmpty ? null : _verify,
                  child: const Text('Verify classroom BLE'),
                ),
                TextButton(
                  onPressed: _busy ? null : _load,
                  child: const Text('Reload BLE policies'),
                ),
              ],
            ),
            const Text(
              'Observe scans locally. Verify runs a separate fresh scan and submits a signed diagnostic report. Manage permissions in BLE Diagnostics.',
            ),
          ],
        ),
      ),
    );
  }
}
