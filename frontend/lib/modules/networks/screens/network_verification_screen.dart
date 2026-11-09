import 'package:flutter/material.dart';
import '../../../theme.dart';
import '../services/network_verification_api.dart';
import '../services/network_verification_failure.dart';
import '../widgets/wifi_diagnostics_card.dart';
import '../services/wifi_diagnostics.dart';
import '../services/classroom_wifi_api.dart';
import '../widgets/classroom_wifi_card.dart';
import '../services/ble_diagnostics.dart';
import '../widgets/ble_diagnostics_card.dart';
import '../services/classroom_ble_api.dart';
import '../widgets/classroom_ble_card.dart';

/// Independent FR-06 diagnostic. Attendance workflow is intentionally unchanged.
class NetworkVerificationScreen extends StatefulWidget {
  const NetworkVerificationScreen({
    super.key,
    this.api,
    this.wifiDiagnostics,
    this.classroomApi,
    this.bleDiagnostics,
    this.bleApi,
  });
  final NetworkVerificationApi? api;
  final WifiDiagnostics? wifiDiagnostics;
  final ClassroomWifiApi? classroomApi;
  final BleDiagnostics? bleDiagnostics;
  final ClassroomBleApi? bleApi;
  @override
  State<NetworkVerificationScreen> createState() =>
      _NetworkVerificationScreenState();
}

class _NetworkVerificationScreenState extends State<NetworkVerificationScreen>
    with WidgetsBindingObserver {
  late final _api = widget.api ?? NetworkVerificationApi();
  Map<String, dynamic>? _result;
  NetworkVerificationFailure? _error;
  bool _busy = false, _again = false, _foreground = true;
  int _generation = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _check();
  }

  Future<void> _check() async {
    if (_busy) {
      _again = true;
      return;
    }
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _result = null;
      _error = null;
    });
    try {
      final result = await _api.check();
      if (mounted && generation == _generation) {
        setState(() => _result = result);
      }
    } catch (error) {
      if (mounted && generation == _generation) {
        setState(() => _error = NetworkVerificationFailure.from(error));
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        if (_again && _foreground) {
          _again = false;
          _check();
        }
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (!_foreground) {
      _generation++;
      setState(() {
        _result = null;
        _error = null;
      });
    } else {
      _check();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _generation++;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Network Verification')),
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                'Current connection',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 16),
              const Text('Check whether your current connection is allowed.'),
              const SizedBox(height: 20),
              if (_busy)
                const Column(
                  children: [
                    CircularProgressIndicator(key: ValueKey('cidr-progress')),
                    SizedBox(height: 12),
                    Text('Checking the connection on the server...'),
                  ],
                ),
              if (_result != null) ...[
                Icon(
                  _result!['result'] == 'PASS'
                      ? Icons.check_circle_outline
                      : Icons.cancel_outlined,
                  color: _result!['result'] == 'PASS'
                      ? Colors.green
                      : Colors.red,
                  size: 48,
                ),
                Text(
                  'Network verification: ${_result!['result']}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (_result!['result'] != 'PASS') ...[
                  Text('Reason: ${_result!['reason_code']}'),
                  const SizedBox(height: 12),
                  Text(_result!['message'] as String),
                ],
                const SizedBox(height: 12),
                Text(
                  'Backend-observed source IP: ${_result!['source_ip'] ?? 'unavailable'}',
                ),
                if (_result!['matched_policy_id'] != null)
                  Text(
                    'Matched policy: ${_result!['matched_policy_name'] ?? _result!['matched_policy_id']} (${_result!['matched_policy_id']})',
                  ),
                Text('Checked: ${_result!['verified_at']}'),
              ],
              if (_error != null) ...[
                const Icon(Icons.cancel_outlined, color: Colors.red, size: 48),
                Text(
                  'Network verification: FAIL',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text('Reason: ${_error!.code}'),
                const SizedBox(height: 12),
                InfoNotice(_error!.message, warning: true),
                if (_error!.unreachable)
                  const Text(
                    'No network check completed. Attendance is blocked.',
                  ),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _busy ? null : _check,
                child: const Text('Check current connection'),
              ),
              const SizedBox(height: 20),
              const Text(
                'Attendance checks your connection again before saving.',
              ),
              const SizedBox(height: 20),
              WifiDiagnosticsCard(diagnostics: widget.wifiDiagnostics),
              const SizedBox(height: 20),
              BleDiagnosticsCard(diagnostics: widget.bleDiagnostics),
              const SizedBox(height: 20),
              ClassroomWifiCard(
                api:
                    widget.classroomApi ??
                    ClassroomWifiApi(wifi: widget.wifiDiagnostics),
              ),
              const SizedBox(height: 20),
              ClassroomBleCard(
                api:
                    widget.bleApi ??
                    ClassroomBleApi(scanner: widget.bleDiagnostics),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
