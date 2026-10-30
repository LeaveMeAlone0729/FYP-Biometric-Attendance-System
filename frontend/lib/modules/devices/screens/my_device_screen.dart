import 'package:flutter/material.dart';
import '../../../theme.dart';
import '../services/device_api.dart';
import '../services/device_verification_service.dart';
import 'device_registration_screen.dart';

/// Read-only registration/check status. Verification runs on entry and resume.
class MyDeviceScreen extends StatefulWidget {
  const MyDeviceScreen({super.key, this.api, this.verificationService});
  final DeviceApi? api;
  final DeviceVerificationService? verificationService;
  @override
  State<MyDeviceScreen> createState() => _MyDeviceScreenState();
}

class _MyDeviceScreenState extends State<MyDeviceScreen>
    with WidgetsBindingObserver {
  late final DeviceApi _api = widget.api ?? DeviceApi();
  late final DeviceVerificationService _verification =
      widget.verificationService ?? DeviceVerificationService();
  Map<String, dynamic>? _device;
  DeviceVerificationResult? _result;
  String? _error;
  bool _checking = false, _again = false, _loaded = false, _foreground = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _check();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) _check();
  }

  Future<void> _check() async {
    if (!mounted) return;
    if (_checking) {
      _again = true;
      return;
    }
    setState(() {
      _checking = true;
      _result = null;
      _error = null;
    });
    try {
      final device = await _api.current();
      if (!mounted) return;
      setState(() {
        _device = device;
        _loaded = true;
      });
      final result = await _verification.verify();
      if (mounted) setState(() => _result = result);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() => _checking = false);
        if (_again && _foreground) {
          _again = false;
          _check();
        }
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('My Device')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'Registered device',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 16),
        if (_device != null) ...[
          Text(
            _device!['device_name'] as String,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          Text(_device!['device_model'] as String),
          Text('Status: ${_device!['status']}'),
          Text('Registered: ${_device!['registered_at']}'),
        ] else if (_loaded) ...[
          const Text('No device registered for this account.'),
          TextButton(
            onPressed: _checking
                ? null
                : () async {
                    await Navigator.push<void>(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const DeviceRegistrationScreen(),
                      ),
                    );
                    if (mounted) _check();
                  },
            child: const Text('Open device registration'),
          ),
        ],
        const SizedBox(height: 24),
        if (_checking)
          const Column(
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text('Checking this device automatically...'),
            ],
          ),
        if (_result != null)
          InfoNotice(
            'Automatic device verification: PASS\nChecked: ${_result!.verifiedAt.toIso8601String()}',
          ),
        if (_error != null) InfoNotice(_error!, warning: true),
        const SizedBox(height: 20),
        const InfoNotice(
          'Each device check uses a fresh signed challenge. This status does not authorize attendance. Replacement requires approval.',
        ),
      ],
    ),
  );
}
