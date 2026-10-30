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
  List<Map<String, dynamic>> _devices = [];
  bool _initialRegistrationAvailable = false;
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
      final listing = await _api.listDevices();
      if (!mounted) return;
      setState(() {
        _devices = (listing['devices'] as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList();
        _initialRegistrationAvailable =
            listing['initial_registration_available'] == true;
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
        Text('${_devices.length} / 2 active trusted devices'),
        for (final device in _devices) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Slot ${device['slot_number']}: ${device['device_name']}',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  Text(device['device_model'] as String),
                  Text('Status: ${device['status']}'),
                  Text('Registered: ${device['registered_at']}'),
                  if (_result?.deviceId == device['device_id'])
                    const Text(
                      'This installation',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                ],
              ),
            ),
          ),
        ],
        if (_loaded && _initialRegistrationAvailable) ...[
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
        ] else if (_loaded) ...[
          const SizedBox(height: 12),
          const InfoNotice(
            'Additional device enrollment is locked until Stage B biometric and liveness approval. Replacement is not enabled.',
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
