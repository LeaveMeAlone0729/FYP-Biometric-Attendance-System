import '../../../services/api_client.dart';
import 'device_api.dart';
import 'device_key_store.dart';

/// Explicit enrollment preparation only. Never rotates keys or activates devices.
class PendingDeviceService {
  PendingDeviceService({
    ApiClient? client,
    DeviceApi? api,
    DeviceKeyStore? keys,
  }) : _client = client ?? ApiClient.instance,
       _api = api ?? DeviceApi(client ?? ApiClient.instance),
       _keys = keys ?? const DeviceKeyStore();
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
    if (pending != null) {
      final key = await _keys.getPublicKey(student!);
      checkSession();
      if (key == null ||
          key['public_key_fingerprint'] != pending['public_key_fingerprint']) {
        throw const ApiException(
          'This installation cannot match the pending device key. Keep existing keys unchanged and refresh after the request expires.',
          409,
          'CANDIDATE_KEY_MISMATCH',
        );
      }
    }
    return pending;
  }

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
    if (listing['pending_enrollment_available'] != true) {
      throw const ApiException(
        'Slot 2 preparation is unavailable. Replacement is not enabled.',
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
        'This installation is already registered. Use your second Android device; keep this key unchanged.',
        409,
        'KEY_ALREADY_REGISTERED',
      );
    }
    // Called only after an explicit preparation action. Existing aliases are reused.
    key ??= await _keys.getOrCreateKey(student);
    checkSession();
    final fingerprint = key['public_key_fingerprint'];
    final pending = await _api.beginPending(
      publicKey: key['public_key_spki'] as String,
      deviceName: deviceName.trim(),
      deviceModel: key['device_model'] as String,
    );
    checkSession();
    void validate(Map<String, dynamic> data) {
      if (data['public_key_fingerprint'] != fingerprint ||
          data['operation'] != 'enroll_second_device' ||
          data['slot_number'] != 2 ||
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
