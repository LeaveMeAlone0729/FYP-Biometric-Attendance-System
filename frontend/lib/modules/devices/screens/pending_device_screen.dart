import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../theme.dart';
import '../services/pending_device_service.dart';
import '../services/device_biometric_api.dart';
import '../services/device_activation_service.dart';
import 'device_biometric_approval_screen.dart';

class PendingDeviceScreen extends StatefulWidget {
  const PendingDeviceScreen({super.key, this.service, this.replacementTarget});
  final PendingDeviceService? service;
  final Map<String, dynamic>? replacementTarget;
  @override
  State<PendingDeviceScreen> createState() => _PendingDeviceScreenState();
}

class _PendingDeviceScreenState extends State<PendingDeviceScreen> {
  late final _service =
      widget.service ??
      PendingDeviceService(replacementTarget: widget.replacementTarget);
  final _name = TextEditingController();
  Map<String, dynamic>? _pending;
  String? _error;
  bool _busy = true, _loaded = false;

  bool get _expired {
    if (_pending?['status'] == 'EXPIRED') return true;
    final expires = DateTime.tryParse(_pending?['expires_at'] as String? ?? '');
    return expires != null && !expires.isAfter(DateTime.now());
  }

  bool get _activated => _pending?['status'] == 'ACTIVATED';
  bool get _proven => _pending?['status'] == 'KEY_PROVEN' && !_expired;
  bool get _canPrepare => _loaded && !_busy && !_proven && !_activated;

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
          api: widget.replacementTarget == null
              ? null
              : DeviceBiometricApi(
                  null,
                  'replace_device',
                  widget.replacementTarget!['slot_number'] as int,
                ),
          activationService: widget.replacementTarget == null
              ? null
              : DeviceActivationService(
                  operation: 'replace_device',
                  slotNumber: widget.replacementTarget!['slot_number'] as int,
                  replacedDeviceId:
                      widget.replacementTarget!['device_id'] as String,
                  replacedDeviceFingerprint:
                      widget.replacementTarget!['public_key_fingerprint']
                          as String,
                ),
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
    appBar: AppBar(
      title: Text(
        widget.replacementTarget == null
            ? 'Prepare second device'
            : 'Replace Slot ${widget.replacementTarget!["slot_number"]} device',
      ),
    ),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'Step 1 of 2: Device key preparation',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        if (widget.replacementTarget != null)
          InfoNotice(
            'Replacing ${widget.replacementTarget!["device_name"]} in Slot ${widget.replacementTarget!["slot_number"]}. The old device remains ACTIVE until the server atomically approves replacement. The other slot stays unchanged.',
          ),
        Text(
          widget.replacementTarget == null
              ? 'Create a pending Slot 2 enrollment request and prove that this installation holds its private key. This step does not complete device registration.'
              : 'Prepare this new installation as the replacement candidate. Face, liveness and genuine trusted approval are required.',
        ),
        const SizedBox(height: 16),
        if (_activated) ...[
          const InfoNotice(
            'Server confirmed device activation. Return to My Device to refresh the registered devices.',
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Back to My Device'),
          ),
        ] else if (_proven) ...[
          const ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.check_circle_outline, color: Colors.green),
            title: Text('Device key verified successfully'),
          ),
          InfoNotice(
            widget.replacementTarget == null
                ? 'This device is not yet an ACTIVE registration. Slot 2 remains inactive.'
                : 'This candidate is not ACTIVE. The old device remains registered.',
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
          Text(
            widget.replacementTarget == null
                ? 'Device key proof failed'
                : 'Replacement verification failed',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const Text(
            'The device is not registered. Start a new pending request using the retained local key.',
          ),
        ] else if (_pending?['status'] == 'CANCELLED') ...[
          const Text(
            'Pending request cancelled. Registered devices are unchanged.',
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
        if (!_proven && !_activated && _loaded) ...[
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
        if (_pending != null &&
            ['CHALLENGE_ISSUED', 'KEY_PROVEN'].contains(_pending!['status']))
          TextButton(
            onPressed: _busy
                ? null
                : () async {
                    setState(() => _busy = true);
                    try {
                      final result = await _service.cancel(
                        _pending!['pending_registration_id'] as String,
                      );
                      if (mounted) setState(() => _pending = result);
                    } catch (error) {
                      if (mounted) setState(() => _error = message(error));
                    } finally {
                      if (mounted) setState(() => _busy = false);
                    }
                  },
            child: const Text('Cancel pending request'),
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
