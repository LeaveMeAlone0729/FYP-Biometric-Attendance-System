import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../theme.dart';
import '../services/pending_device_service.dart';
import 'device_biometric_approval_screen.dart';

class PendingDeviceScreen extends StatefulWidget {
  const PendingDeviceScreen({super.key, this.service});
  final PendingDeviceService? service;
  @override
  State<PendingDeviceScreen> createState() => _PendingDeviceScreenState();
}

class _PendingDeviceScreenState extends State<PendingDeviceScreen> {
  late final _service = widget.service ?? PendingDeviceService();
  final _name = TextEditingController();
  Map<String, dynamic>? _pending;
  String? _error;
  bool _busy = true, _loaded = false;

  bool get _expired {
    if (_pending?['status'] == 'EXPIRED') return true;
    final expires = DateTime.tryParse(_pending?['expires_at'] as String? ?? '');
    return expires != null && !expires.isAfter(DateTime.now());
  }

  bool get _proven => _pending?['status'] == 'KEY_PROVEN' && !_expired;
  bool get _canPrepare => _loaded && !_busy && !_proven;

  @override
  void initState() {
    super.initState();
    _load();
  }

  String message(Object error) => error is PlatformException
      ? error.message ?? 'Android Keystore is unavailable.'
      : error is MissingPluginException
      ? 'Use the Android app with Android Keystore support.'
      : error.toString();

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
      _loaded = false;
    });
    try {
      final pending = await _service.current();
      if (mounted) {
        setState(() {
          _pending = pending;
          _loaded = true;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = message(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _prepare() async {
    if (!_canPrepare) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final pending = await _service.prepare(_name.text);
      if (mounted) setState(() => _pending = pending);
      // KEY_PROVEN completes this step. Never retry preparation or start a
      // biometric request automatically to imply that registration is complete.
    } catch (error) {
      // Recover server expiry/failed state for the same retained local key.
      try {
        final pending = await _service.current();
        if (mounted) setState(() => _pending = pending);
      } catch (_) {
        /* Keep the original actionable preparation error. */
      }
      if (mounted) setState(() => _error = message(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openApproval() async {
    if (!_proven || _busy) return;
    final backToMyDevice = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => DeviceBiometricApprovalScreen(
          pendingRegistrationId: _pending!['pending_registration_id'] as String,
          expiresAt: _pending!['expires_at'] as String,
        ),
      ),
    );
    // A successful result returns through this preparation route to My Device.
    // Normal system/app-bar Back still returns to preparation without changes.
    if (backToMyDevice == true && mounted) Navigator.pop(context);
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Prepare second device')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'Step 1 of 2: Device key preparation',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        const Text(
          'Create a pending Slot 2 enrollment request and prove that this installation holds its private key. This step does not complete device registration.',
        ),
        const SizedBox(height: 16),
        if (_proven) ...[
          const ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.check_circle_outline, color: Colors.green),
            title: Text('Device key verified successfully'),
          ),
          const InfoNotice(
            'This device is not yet an ACTIVE registration. Slot 2 remains inactive.',
          ),
          const SizedBox(height: 12),
          const Text(
            'Step 2: Trusted biometric approval',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const Text(
            'After face recognition and liveness, the app automatically checks for a separate trusted server approval. An untrusted test result cannot activate this device.',
          ),
          const Text(
            'Trusted biometric approval: checked on the server after biometric verification',
          ),
          const Text(
            'Device activation: automatic only after server eligibility and key proof',
          ),
          const SizedBox(height: 8),
          const Text(
            'Key preparation is complete for this pending request. Repeating it will not complete registration.',
          ),
        ] else if (_expired) ...[
          const Text(
            'Pending registration expired',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const Text(
            'The device was not activated. Your local key is retained. A new request starts key preparation again; it does not bypass biometric approval.',
          ),
        ] else if (_pending?['status'] == 'FAILED') ...[
          const Text(
            'Device key proof failed',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const Text(
            'The device is not registered. Start a new pending request using the retained local key.',
          ),
        ] else if (_pending != null) ...[
          const Text('Device key preparation is incomplete.'),
        ],
        if (_pending != null) ...[
          const SizedBox(height: 12),
          Text('Last server status: ${_pending!['status']}'),
          Text('Pending registration expires: ${_pending!['expires_at']}'),
          const SizedBox(height: 8),
          const Text(
            'Refresh status to check this pending request. The server determines whether it is still valid.',
          ),
        ],
        if (!_proven && _loaded) ...[
          const SizedBox(height: 16),
          TextField(
            controller: _name,
            enabled: !_busy,
            maxLength: 100,
            decoration: const InputDecoration(
              labelText: 'Candidate device name',
            ),
          ),
          TextButton(
            onPressed: _canPrepare ? _prepare : null,
            child: Text(
              _expired || _pending?['status'] == 'FAILED'
                  ? 'Start a new pending request'
                  : 'Prepare and prove device key',
            ),
          ),
        ],
        if (_proven)
          TextButton(
            onPressed: _busy ? null : _openApproval,
            child: const Text('Open facial recognition and liveness'),
          ),
        TextButton(
          onPressed: _busy ? null : _load,
          child: const Text('Refresh pending status'),
        ),
        if (_busy) const Center(child: CircularProgressIndicator()),
        if (_error != null) InfoNotice(_error!, warning: true),
        const SizedBox(height: 20),
        const Text(
          'Your private key stays in Android Keystore and is reused after app restarts. Keep this app installed and retain its data. Your existing trusted device is unchanged.',
        ),
        const SizedBox(height: 8),
        const Text(
          'A new login uses a different server session. If another pending request exists, wait for it to expire before starting a new request with the same local key.',
        ),
      ],
    ),
  );
}
