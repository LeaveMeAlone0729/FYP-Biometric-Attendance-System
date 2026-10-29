import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import '../../../theme.dart';
import '../services/device_api.dart';
import '../services/device_key_store.dart';

class MyDeviceScreen extends StatefulWidget {
  const MyDeviceScreen({super.key, this.api, this.keyStore, this.studentId});
  final DeviceApi? api;
  final DeviceKeyStore? keyStore;
  final String? studentId;
  @override
  State<MyDeviceScreen> createState() => _MyDeviceScreenState();
}

class _MyDeviceScreenState extends State<MyDeviceScreen> {
  late final DeviceApi _api = widget.api ?? DeviceApi();
  late final DeviceKeyStore _keys = widget.keyStore ?? const DeviceKeyStore();
  late final String _studentId =
      widget.studentId ??
      ApiClient.instance.student?['student_id'] as String? ??
      '';
  final _name = TextEditingController();
  Map<String, dynamic>? _device;
  String? _error;
  bool _loading = true, _busy = false, _localMatch = false, _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _message(Object error) => error is PlatformException
      ? error.message ?? 'Android Keystore is unavailable.'
      : error is MissingPluginException
      ? 'Device registration requires the Android app. Rebuild the app after updating.'
      : error.toString();

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final device = await _api.current();
      if (mounted) {
        setState(() {
          _device = device;
          _loaded = true;
        });
      }
      // Never create a new key merely by viewing a registered device.
      final local = device == null
          ? null
          : await _keys.getPublicKey(_studentId);
      if (!mounted) {
        return;
      }
      setState(() {
        _device = device;
        _localMatch =
            device != null &&
            local != null &&
            local['public_key_fingerprint'] == device['public_key_fingerprint'];
      });
    } catch (error) {
      if (mounted) setState(() => _error = _message(error));
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _register() async {
    if (_busy) return;
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Enter a name for this device.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final key = await _keys.getOrCreateKey(_studentId);
      final challenge = await _api.begin(
        publicKey: key['public_key_spki'] as String,
        deviceName: name,
        deviceModel: key['device_model'] as String,
      );
      final signature = await _keys.sign(
        _studentId,
        challenge['signing_payload'] as String,
      );
      final device = await _api.confirm(
        challenge['registration_id'] as String,
        signature,
      );
      if (mounted) {
        setState(() {
          _device = device;
          _localMatch = true;
        });
      }
    } catch (error) {
      // A lost confirmation response may have committed. Refresh before retrying;
      // never rotate/delete the key as a recovery shortcut.
      try {
        final device = await _api.current();
        if (device != null) {
          final local = await _keys.getPublicKey(_studentId);
          if (mounted) {
            setState(() {
              _device = device;
              _localMatch =
                  local?['public_key_fingerprint'] ==
                  device['public_key_fingerprint'];
            });
          }
          return;
        }
      } catch (_) {
        /* Preserve the original actionable error. */
      }
      if (mounted) setState(() => _error = _message(error));
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('My Device')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                'Device registration',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 16),
              if (_device != null) ...[
                const Icon(Icons.verified_user_outlined, size: 48, color: teal),
                const SizedBox(height: 16),
                Text(
                  _device!['device_name'] as String,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(_device!['device_model'] as String),
                Text('Status: ${_device!['status']}'),
                Text('Registered: ${_device!['registered_at']}'),
                const SizedBox(height: 16),
                InfoNotice(
                  _localMatch
                      ? 'This installation holds the registered device key.'
                      : 'The registered key is not available in this installation. Device replacement requires approval and is not available yet.',
                  warning: !_localMatch,
                ),
              ] else if (_loaded) ...[
                const Text(
                  'Register this Android installation as your trusted device. Only one device can be registered to your account.',
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _name,
                  maxLength: 100,
                  enabled: !_busy,
                  decoration: const InputDecoration(
                    labelText: 'Device name',
                    hintText: 'My phone',
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _busy ? null : _register,
                  icon: const Icon(Icons.phonelink_lock),
                  label: Text(_busy ? 'Registering…' : 'Register this device'),
                ),
              ],
              const SizedBox(height: 20),
              const InfoNotice(
                'Your private key stays in Android Keystore. Device registration does not change attendance verification in Phase 1.',
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                InfoNotice(_error!, warning: true),
              ],
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _busy ? null : _load,
                child: const Text('Refresh'),
              ),
            ],
          ),
  );
}
