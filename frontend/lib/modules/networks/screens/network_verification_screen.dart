import 'package:flutter/material.dart';
import '../../../theme.dart';
import '../services/network_verification_api.dart';
import '../services/network_verification_failure.dart';

/// Independent FR-06 diagnostic. Attendance workflow is intentionally unchanged.
class NetworkVerificationScreen extends StatefulWidget {
  const NetworkVerificationScreen({super.key, this.api});
  final NetworkVerificationApi? api;
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
              const Text(
                'The backend checks its observed connection source IP against enabled authorised CIDR policies. This FYP uses a controlled simulation; it does not identify your exact Wi-Fi location.',
              ),
              const SizedBox(height: 20),
              if (_busy)
                const Column(
                  children: [
                    CircularProgressIndicator(),
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
                Text('Reason: ${_result!['reason_code']}'),
                const SizedBox(height: 12),
                Text(_result!['message'] as String),
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
                    'The backend could not verify the source IP. No network authorization was obtained.',
                  ),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _busy ? null : _check,
                child: const Text('Check current connection'),
              ),
              const SizedBox(height: 20),
              const InfoNotice(
                'This result does not authorize or record attendance. Final attendance authorization will perform a fresh network check for that exact request.',
              ),
              const SizedBox(height: 12),
              const Text(
                'USB ADB reverse may appear as 127.0.0.1 or ::1. Localhost is not accepted as campus-network proof. No Android location permission is needed.',
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
