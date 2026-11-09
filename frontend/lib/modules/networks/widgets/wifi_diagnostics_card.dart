import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/wifi_diagnostics.dart';

class WifiDiagnosticsCard extends StatefulWidget {
  const WifiDiagnosticsCard({super.key, this.diagnostics});
  final WifiDiagnostics? diagnostics;
  @override
  State<WifiDiagnosticsCard> createState() => _WifiDiagnosticsCardState();
}

class _WifiDiagnosticsCardState extends State<WifiDiagnosticsCard>
    with WidgetsBindingObserver {
  late final _service = widget.diagnostics ?? const WifiDiagnostics();
  WifiReading? _reading;
  String? _error;
  bool _busy = false, _again = false, _foreground = true;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
  }

  Future<void> _refresh({bool requestPermission = false}) async {
    if (_busy) {
      _again = true;
      return;
    }
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _reading = null;
      _error = null;
    });
    try {
      if (requestPermission) await _service.requestPermission();
      final reading = await _service.read();
      if (mounted && generation == _generation && _foreground) {
        setState(() => _reading = reading);
      }
    } catch (error) {
      if (mounted && generation == _generation && _foreground) {
        setState(
          () => _error = error is MissingPluginException
              ? 'Wi-Fi diagnostics are unavailable on this platform.'
              : 'Wi-Fi reading unavailable. Check Android permissions and refresh.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        if (_again && _foreground) {
          _again = false;
          _refresh();
        }
      }
    }
  }

  Future<void> _settings(String page) async {
    try {
      await _service.openSettings(page);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Open Android Settings manually, then return and refresh.',
        );
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (!_foreground) {
      ++_generation;
      setState(() => _reading = null);
    } else {
      _refresh();
    }
  }

  @override
  void dispose() {
    ++_generation;
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  String _state(bool? value, String yes, String no) => value == null
      ? 'Unavailable'
      : value
      ? yes
      : no;

  String _message(WifiReading reading) => switch (reading.status) {
    'PERMISSION_REQUIRED' =>
      'Allow precise location to read Wi-Fi identifiers. Android treats these as location-sensitive.',
    'LOCATION_DISABLED' => 'Turn on Android Location services, then refresh.',
    'WIFI_OFF' => 'Wi-Fi is off. Connect to Wi-Fi to collect readings.',
    'NOT_CONNECTED' => 'This device is not connected to Wi-Fi.',
    'REDACTED' =>
      'Android hid one or more identifiers. Check precise location permission and Location services.',
    'UNSUPPORTED' => 'Wi-Fi diagnostics are unavailable on this device.',
    'AVAILABLE' => '',
    _ =>
      'No connected Wi-Fi details returned. Connect to Wi-Fi and refresh; Android may also hide identifiers.',
  };

  @override
  Widget build(BuildContext context) {
    final reading = _reading;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              children: [
                Text(
                  'Wi-Fi diagnostics',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : () => _refresh(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
              ],
            ),
            const Text('Local readings only; not attendance authorization.'),
            const SizedBox(height: 12),
            if (_busy)
              const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  LinearProgressIndicator(),
                  SizedBox(height: 8),
                  Text('Reading Wi-Fi...'),
                ],
              ),
            if (_error != null) Text(_error!),
            if (reading != null) ...[
              SelectableText(
                'Connection type: ${reading.connectionType.replaceAll('_', ' ')}',
              ),
              Text('Wi-Fi: ${_state(reading.wifiEnabled, 'On', 'Off')}'),
              Text(
                'Wi-Fi association: ${_state(reading.wifiConnected, 'Connected', 'Not connected')}',
              ),
              SelectableText(
                'SSID: ${reading.ssid ?? 'Unavailable / redacted'}',
              ),
              SelectableText(
                'BSSID: ${reading.bssid ?? 'Unavailable / redacted'}',
              ),
              SelectableText(
                'RSSI: ${reading.rssi == null ? 'Unavailable' : '${reading.rssi} dBm'}',
              ),
              Text(
                'Location permission: ${reading.permission.replaceAll('_', ' ')}',
              ),
              Text(
                'Location services: ${_state(reading.locationEnabled, 'On', 'Off')}',
              ),
              if (reading.observedAt != null)
                Text('Device sample time: ${reading.observedAt!.toLocal()}'),
              if (_message(reading).isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(_message(reading)),
              ],
              if (reading.wifiEnabled == true &&
                  reading.permission != 'PRECISE_GRANTED')
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => reading.permission == 'SETTINGS_REQUIRED'
                            ? _settings('app')
                            : _refresh(requestPermission: true),
                  child: Text(
                    reading.permission == 'SETTINGS_REQUIRED'
                        ? 'Open app permissions'
                        : 'Allow precise location',
                  ),
                ),
              if (reading.wifiEnabled == true &&
                  reading.locationEnabled == false)
                TextButton(
                  onPressed: () => _settings('location'),
                  child: const Text('Open Location settings'),
                ),
              if (reading.wifiEnabled == false)
                TextButton(
                  onPressed: () => _settings('wifi'),
                  child: const Text('Open Wi-Fi settings'),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
