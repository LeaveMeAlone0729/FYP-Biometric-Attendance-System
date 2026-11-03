import '../../../services/api_client.dart';
import 'device_api.dart';
import 'device_key_store.dart';

/// Explicit enrollment preparation only. Never rotates keys or activates devices.
class PendingDeviceService {
  PendingDeviceService({
    ApiClient? client,
    DeviceApi? api,
    DeviceKeyStore? keys,
    this.replacementTarget,
  }) : _client = client ?? ApiClient.instance,
       _api = api ?? DeviceApi(client ?? ApiClient.instance),
       _keys = keys ?? const DeviceKeyStore();
  final Map<String, dynamic>? replacementTarget;
  String get operation =>
      replacementTarget == null ? 'enroll_second_device' : 'replace_device';
  int get slot => replacementTarget?['slot_number'] as int? ?? 2;
  final ApiClient _client;
  final DeviceApi _api;
  final DeviceKeyStore _keys;

  /// Restores display state with read-only key access; never generates a key.
  Future<Map<String, dynamic>?> current() async {
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    void checkSession() {
      if (student == null ||
          !_client.authenticated.value ||
          revision != _client.sessionRevision ||
          _client.student?['student_id'] != student) {
        throw const ApiException(
          'Your sign-in changed. Open device preparation again.',
          401,
          'SESSION_CHANGED',
        );
      }
    }

    checkSession();
    final pending = await _api.currentPending();
    checkSession();
    final open =
        pending != null &&
        ['CHALLENGE_ISSUED', 'KEY_PROVEN'].contains(pending['status']);
    if (pending != null &&
        (pending['operation'] != operation ||
            pending['slot_number'] != slot ||
            (replacementTarget != null &&
                pending['replaced_device_id'] !=
                    replacementTarget!['device_id']))) {
      if (!open) return null;
      throw const ApiException(
        'Another pending request exists. Open its target slot or wait for expiry.',
        409,
        'PENDING_EXISTS',
      );
    }
    if (pending != null) {
      final key = await _keys.getPublicKey(student!);
      checkSession();
      if (key == null ||
          key['public_key_fingerprint'] != pending['public_key_fingerprint']) {
        if (!open) return null;
        throw const ApiException(
          'This installation cannot match the pending device key. Keep existing keys unchanged and refresh after the request expires.',
          409,
          'CANDIDATE_KEY_MISMATCH',
        );
      }
    }
    return pending;
  }

  Future<Map<String, dynamic>> cancel(
    String id,
  ) async => Map<String, dynamic>.from(
    await _client.post(
          '/api/v1/devices/pending-registrations/${Uri.encodeComponent(id)}/cancel',
          {},
        )
        as Map,
  );

  Future<void> requestApproval(String id) => _api.requestDeviceApproval(id);

  Future<Map<String, dynamic>> prepare(String deviceName) async {
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    void checkSession() {
      if (student == null ||
          !_client.authenticated.value ||
          _client.sessionRevision != revision ||
          _client.student?['student_id'] != student) {
        throw const ApiException(
          'Your sign-in changed. Open device preparation again.',
          401,
          'SESSION_CHANGED',
        );
      }
    }

    checkSession();
    if (deviceName.trim().isEmpty) {
      throw const ApiException('Enter a name for this candidate device.');
    }
    final listing = await _api.listDevices();
    checkSession();
    if (replacementTarget == null &&
        listing['pending_enrollment_available'] != true) {
      throw const ApiException(
        'Slot 2 enrollment is unavailable. Use the selected occupied slot for approved replacement.',
      );
    }
    final devices = (listing['devices'] as List).cast<Map>();
    var key = await _keys.getPublicKey(student!);
    checkSession();
    if (key != null &&
        devices.any(
          (d) => d['public_key_fingerprint'] == key!['public_key_fingerprint'],
        )) {
      throw const ApiException(
        'This installation is already registered. Start replacement on the new Android device; keep existing keys unchanged.',
        409,
        'KEY_ALREADY_REGISTERED',
      );
    }
    // Called only after an explicit preparation action. Existing aliases are reused.
    key ??= await _keys.getOrCreateKey(student);
    checkSession();
    final fingerprint = key['public_key_fingerprint'];
    final Map<String, dynamic> pending;
    if (replacementTarget != null) {
      pending = Map<String, dynamic>.from(
        await _client.post('/api/v1/devices/replacements', {
              'public_key_spki': key['public_key_spki'],
              'platform': 'android',
              'device_name': deviceName.trim(),
              'device_model': key['device_model'],
              'slot_number': slot,
              'old_device_id': replacementTarget!['device_id'],
            })
            as Map,
      );
    } else {
      pending = await _api.beginPending(
        publicKey: key['public_key_spki'] as String,
        deviceName: deviceName.trim(),
        deviceModel: key['device_model'] as String,
      );
    }
    checkSession();
    void validate(Map<String, dynamic> data) {
      if (data['public_key_fingerprint'] != fingerprint ||
          data['operation'] != operation ||
          data['slot_number'] != slot ||
          (replacementTarget != null &&
              (data['replaced_device_id'] != replacementTarget!['device_id'] ||
                  data['replaced_device_fingerprint'] !=
                      replacementTarget!['public_key_fingerprint'])) ||
          data['activation_enabled'] != false ||
          data['attendance_authorized'] != false ||
          data['algorithm'] != 'ECDSA_P256_SHA256' ||
          data['signature_encoding'] != 'base64-DER') {
        throw const ApiException(
          'The server returned an incompatible candidate response.',
        );
      }
    }

    validate(pending);
    if (pending['status'] == 'KEY_PROVEN') return pending;
    if (pending['status'] != 'CHALLENGE_ISSUED') {
      throw const ApiException(
        'Candidate challenge has ended. Start preparation again using the same key.',
      );
    }
    final id = pending['pending_registration_id'] as String;
    final signature = await _keys.sign(
      student,
      pending['signing_payload'] as String,
    );
    checkSession();
    try {
      final proven = await _api.provePending(id, signature);
      checkSession();
      validate(proven);
      if (proven['status'] != 'KEY_PROVEN') {
        throw const ApiException('Candidate key proof was not confirmed.');
      }
      return proven;
    } catch (_) {
      checkSession();
      // The proof may have committed before a response was lost. Never rotate
      // the key or blindly replay a consumed proof.
      final recovered = await _api.pendingStatus(id);
      checkSession();
      validate(recovered);
      if (recovered['status'] == 'KEY_PROVEN') return recovered;
      rethrow;
    }
  }
}
