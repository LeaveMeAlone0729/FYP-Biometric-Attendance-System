import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/ble_diagnostics.dart';

class BleDiagnosticsCard extends StatefulWidget {
  const BleDiagnosticsCard({super.key, this.diagnostics});
  final BleDiagnostics? diagnostics;
  @override
  State<BleDiagnosticsCard> createState() => _BleDiagnosticsCardState();
}

class _BleDiagnosticsCardState extends State<BleDiagnosticsCard>
    with WidgetsBindingObserver {
  late final _service = widget.diagnostics ?? const BleDiagnostics();
  BleSnapshot? _snapshot;
  String? _error;
  bool _busy = false, _scanning = false, _foreground = true;
  int _generation = 0;
  Timer? _ageTimer;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  String feedback(Object error) {
    if (error is TimeoutException) {
      return 'BLE scan or request timed out. No current beacon result was confirmed. Retry after checking Bluetooth.';
    }
    if (error is MissingPluginException) {
      return 'BLE diagnostics are unavailable on this platform.';
    }
    if (error is PlatformException && error.code == 'BLE_SCAN_BUSY') {
      return 'A scan is already running. Wait or stop it first.';
    }
    return 'Bluetooth request could not complete. Check Nearby Devices/location permissions and retry.';
  }

  Future<void> _load() async {
    if (_busy || !_foreground) return;
    final gen = ++_generation;
    setState(() {
      _busy = true;
      _snapshot = null;
      _error = null;
    });
    try {
      final data = await _service.status().timeout(const Duration(seconds: 4));
      if (mounted && _foreground && gen == _generation) {
        setState(() => _snapshot = data);
      }
    } catch (e) {
      if (mounted && gen == _generation) setState(() => _error = feedback(e));
    } finally {
      if (mounted && gen == _generation) setState(() => _busy = false);
    }
  }

  Future<void> _scan() async {
    if (_busy || !_foreground) return;
    final gen = ++_generation;
    _ageTimer?.cancel();
    setState(() {
      _busy = true;
      _scanning = true;
      _snapshot = null;
      _error = null;
    });
    try {
      // This explicit action starts scanning automatically only if native
      // Bluetooth/permission checks pass; there is no scan-on-open/background.
      final data = await _service.scan().timeout(const Duration(seconds: 12));
      if (mounted && _foreground && gen == _generation) {
        setState(() => _snapshot = data);
        if (data.advertisements.isNotEmpty) {
          _ageTimer = Timer.periodic(const Duration(seconds: 1), (_) {
            if (mounted && _foreground) setState(() {});
          });
        }
      }
    } catch (e) {
      unawaited(_service.cancel());
      if (mounted && _foreground && gen == _generation) {
        setState(() => _error = feedback(e));
      }
    } finally {
      if (mounted && gen == _generation) {
        setState(() {
          _busy = false;
          _scanning = false;
        });
      }
    }
  }

  Future<void> _action(Future<void> Function() action) async {
    if (_busy) return;
    var failed = false;
    setState(() => _busy = true);
    try {
      await action();
    } catch (e) {
      failed = true;
      if (mounted) setState(() => _error = feedback(e));
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        if (_foreground && !failed) _load();
      }
    }
  }

  Future<void> _stop() async {
    if (!_scanning) return;
    await _service.stop(); // Original scan future returns its STOPPED snapshot.
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (!_foreground) {
      _generation++;
      _ageTimer?.cancel();
      unawaited(_service.cancel());
      setState(() {
        _busy = false;
        _scanning = false;
        _snapshot = null;
      });
    } else {
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    _ageTimer?.cancel();
    unawaited(_service.cancel());
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  String message(String code) => switch (code) {
    'READY' => 'Tap Scan BLE to collect advertisements for eight seconds.',
    'COMPLETE' =>
      'Scan complete. Results are a local snapshot, not a live feed.',
    'STOPPED' =>
      'Scan stopped. These are only the advertisements already observed.',
    'BLUETOOTH_OFF' =>
      'Bluetooth is OFF. Use the Android enable prompt or Settings.',
    'BLE_PERMISSION_REQUIRED' =>
      'Nearby Devices permission is required. Allow scan access in Android.',
    'LOCATION_PERMISSION_REQUIRED' =>
      'Precise location permission is required for beacon-location research.',
    'LOCATION_DISABLED' =>
      'Location Services are OFF. Enable them to make beacon observations available.',
    'BLE_UNSUPPORTED' =>
      'Bluetooth LE scanning is not supported on this device.',
    'BLE_SCAN_RATE_LIMITED' =>
      'Scans were started too quickly. Wait a few seconds and retry.',
    'BLE_SCAN_FAILED' =>
      'Android could not start the scan. Wait before retrying; frequent starts may be throttled.',
    'CANCELLED' => 'Scan cancelled when this screen became inactive.',
    _ => 'BLE scanner unavailable. Check Bluetooth and Android permissions.',
  };

  @override
  Widget build(BuildContext context) {
    final s = _snapshot;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'BLE Diagnostics',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Text(
              'Local eight-second scan. No pairing or attendance authorization.',
            ),
            if (_busy)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Row(
                  children: [
                    const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        key: ValueKey('ble-progress'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Flexible(
                      child: Text(
                        _scanning
                            ? 'Scanning for BLE advertisements…'
                            : 'Checking Bluetooth…',
                      ),
                    ),
                  ],
                ),
              ),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (s != null) ...[
              Text(
                'Bluetooth: ${s.bluetoothEnabled == true
                    ? 'ON'
                    : s.bluetoothEnabled == false
                    ? 'OFF'
                    : 'Unknown (permission required)'}',
              ),
              Text('Scan permission: ${s.scanPermission}'),
              Text('Bluetooth status permission: ${s.connectPermission}'),
              Text(
                'Location: ${s.locationPermission}; Services ${s.locationEnabled == true
                    ? 'ON'
                    : s.locationEnabled == false
                    ? 'OFF'
                    : 'Unknown'}',
              ),
              Text(message(s.status)),
              if (s.scanPermission == 'SETTINGS_REQUIRED')
                const Text(
                  'Permission is denied; Android app settings may be required.',
                ),
              if (s.errorCode != null)
                Text('Android scan error code: ${s.errorCode}'),
              if (['COMPLETE', 'STOPPED'].contains(s.status)) ...[
                Text('Scan duration: ${s.scanDurationMs} ms'),
                Text('Detected advertisers: ${s.advertisements.length}'),
                if (s.advertisements.isEmpty)
                  const Text(
                    'No BLE advertisements detected in this window. This is not classroom authorization.',
                  ),
                ...s.advertisements.map(
                  (ad) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Nearby advertiser ${ad.id}${ad.name == null ? '' : ' — ${ad.name}'}',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        Text(
                          'RSSI: ${ad.rssi} dBm; median: ${ad.medianRssi.toStringAsFixed(1)} dBm',
                        ),
                        Text(
                          'RSSI samples: ${ad.samples.length}; advertisements: ${ad.count}',
                        ),
                        Text(
                          'Last advertisement: ${ad.timestamp.toIso8601String()}',
                        ),
                        Text(
                          'Advertisement age: ${ad.ageSeconds.toStringAsFixed(1)} s${ad.ageSeconds > 10 ? ' (old snapshot)' : ''}',
                        ),
                        ...ad.serviceUuids.map(
                          (uuid) => Text('Service UUID: $uuid'),
                        ),
                        ...ad.serviceData.map(
                          (v) => Text(
                            'Service data ${v['uuid']}: ${v['data_hex']}',
                          ),
                        ),
                        ...ad.manufacturerData.map(
                          (v) => Text(
                            'Manufacturer ${v['company_id']}: ${v['data_hex']}',
                          ),
                        ),
                        if (ad.serviceUuids.isEmpty &&
                            ad.serviceData.isEmpty &&
                            ad.manufacturerData.isEmpty)
                          const Text(
                            'No beacon identifier exposed in this advertisement.',
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: _busy ? null : _scan,
                  child: const Text('Scan BLE (8 seconds)'),
                ),
                if (_scanning)
                  OutlinedButton(
                    onPressed: _stop,
                    child: const Text('Stop scan'),
                  ),
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => _action(_service.requestPermission),
                  child: const Text('Allow scan permissions'),
                ),
                if (s?.bluetoothEnabled != true)
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _action(_service.enableBluetooth),
                    child: const Text('Enable Bluetooth'),
                  ),
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => _action(() => _service.openSettings('app')),
                  child: const Text('App permissions'),
                ),
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => _action(() => _service.openSettings('location')),
                  child: const Text('Location settings'),
                ),
                TextButton(
                  onPressed: _busy ? null : _load,
                  child: const Text('Refresh Bluetooth status'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
