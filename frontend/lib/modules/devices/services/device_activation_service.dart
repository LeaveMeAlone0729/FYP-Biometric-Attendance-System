import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import 'device_key_store.dart';

/// Automatic coordinator. B3 PASS is only a trigger; the server alone finds and
/// validates a separate trusted grant. Never creates/rotates a key or sends PASS.
class DeviceActivationService {
  DeviceActivationService({
    ApiClient? client,
    DeviceKeyStore? keys,
    this.operation = 'enroll_second_device',
    this.slotNumber = 2,
    this.replacedDeviceId,
    this.replacedDeviceFingerprint,
  }) : _client = client ?? ApiClient.instance,
       _keys = keys ?? const DeviceKeyStore();
  final String operation;
  final int slotNumber;
  final String? replacedDeviceId, replacedDeviceFingerprint;
  final ApiClient _client;
  final DeviceKeyStore _keys;
  final Map<String, Future<Map<String, dynamic>>> _flights = {};

  Future<Map<String, dynamic>> activate(
    String pendingId, {
    void Function(String)? onProgress,
    bool Function()? isCurrent,
    String? expectedCandidateId,
    String? expectedFingerprint,
  }) {
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    final key =
        '$revision:$student:$pendingId:$expectedCandidateId:$expectedFingerprint';
    return _flights.putIfAbsent(
      key,
      () =>
          _activate(
            pendingId,
            student,
            revision,
            onProgress,
            isCurrent ?? () => true,
            expectedCandidateId,
            expectedFingerprint,
          ).whenComplete(() {
            _flights.remove(key);
          }),
    );
  }

  Future<Map<String, dynamic>> _activate(
    String pendingId,
    String? student,
    int revision,
    void Function(String)? progress,
    bool Function() isCurrent,
    String? expectedCandidateId,
    String? expectedFingerprint,
  ) async {
    void check() {
      if (!isCurrent()) {
        throw const ApiException(
          'Activation stopped. Check My Device for server status.',
          0,
          'ACTIVATION_CANCELLED',
        );
      }
      if (!_client.authenticated.value ||
          student == null ||
          _client.student?['student_id'] != student ||
          _client.sessionRevision != revision) {
        throw const ApiException(
          'Your login changed. Sign in and refresh My Device.',
          401,
          'SESSION_CHANGED',
        );
      }
    }

    Never invalid() => throw const ApiException(
      'The server returned an incompatible activation response.',
      0,
      'INVALID_ACTIVATION_RESPONSE',
    );
    Future<dynamic> bounded(
      Future<dynamic> request, {
      int seconds = 15,
    }) => request.timeout(
      Duration(seconds: seconds),
      onTimeout: () => throw const ApiException(
        'Device activation request timed out. Refresh My Device before retrying.',
        0,
        'ACTIVATION_TIMEOUT',
      ),
    );
    final path =
        '/api/v1/devices/pending-registrations/${Uri.encodeComponent(pendingId)}';
    check();
    final local = await _keys
        .getPublicKey(student!)
        .timeout(const Duration(seconds: 5));
    check();
    if (local == null) {
      throw const ApiException(
        'Candidate private key is missing. Keep the original installation; replacement requires approval.',
        409,
        'LOCAL_KEY_MISSING',
      );
    }
    final fingerprint = local['public_key_fingerprint'];
    if (fingerprint is! String || fingerprint.isEmpty) invalid();
    if (expectedFingerprint != null && expectedFingerprint != fingerprint) {
      invalid();
    }
    String? candidate = expectedCandidateId;
    Map<String, dynamic> binding(dynamic raw) {
      if (raw is! Map) invalid();
      final data = Map<String, dynamic>.from(raw);
      if (data['success'] != true ||
          data['pending_registration_id'] != pendingId ||
          data['public_key_fingerprint'] != fingerprint ||
          data['operation'] != operation ||
          data['slot_number'] != slotNumber ||
          data['candidate_device_id'] is! String ||
          (data['candidate_device_id'] as String).isEmpty ||
          (candidate != null && candidate != data['candidate_device_id'])) {
        invalid();
      }
      candidate = data['candidate_device_id'] as String;
      return data;
    }

    Map<String, dynamic> device(dynamic raw) {
      if (raw is! Map) invalid();
      final data = Map<String, dynamic>.from(raw);
      if (data['device_id'] != candidate ||
          data['public_key_fingerprint'] != fingerprint ||
          data['slot_number'] != slotNumber ||
          data['status'] != 'ACTIVE') {
        invalid();
      }
      return data;
    }

    Future<Map<String, dynamic>> status() async {
      final data = binding(
        await bounded(_client.get('$path/activation-status'), seconds: 5),
      );
      check();
      if (data['attendance_authorized'] != false ||
          data['maximum_active_devices'] != 2) {
        invalid();
      }
      return data;
    }

    progress?.call('Checking activation status');
    final initial = await status();
    if (initial['status'] == 'ACTIVE') return device(initial['device']);
    if (initial['status'] == 'EXPIRED') {
      throw const ApiException(
        'Pending registration expired. Renew preparation with the retained key.',
        410,
        'PENDING_EXPIRED',
      );
    }
    if (initial['status'] != 'NOT_ACTIVE') invalid();
    progress?.call('Checking trusted biometric approval');
    final ready = binding(
      await bounded(_client.post('$path/activation-readiness', {})),
    );
    check();
    if (ready['status'] != 'ELIGIBLE') invalid();
    for (final name in [
      'approval_id',
      'trusted_template_revision_id',
      'biometric_result_id',
    ]) {
      if (ready[name] is! String || (ready[name] as String).isEmpty) invalid();
    }
    final challenge = binding(
      await bounded(
        _client.post('$path/activation-challenges', {
          'approval_id': ready['approval_id'],
        }),
      ),
    );
    check();
    for (final name in [
      'approval_id',
      'trusted_template_revision_id',
      'biometric_result_id',
    ]) {
      if (challenge[name] != ready[name]) invalid();
    }
    if (challenge['algorithm'] != 'ECDSA_P256_SHA256' ||
        challenge['signature_encoding'] != 'base64-DER') {
      invalid();
    }
    try {
      final payload =
          jsonDecode(
                utf8.decode(
                  base64Decode(challenge['signing_payload'] as String),
                ),
              )
              as Map;
      for (final name in [
        'pending_registration_id',
        'candidate_device_id',
        'public_key_fingerprint',
        'operation',
        'slot_number',
        'approval_id',
        'trusted_template_revision_id',
        'biometric_result_id',
        'challenge_id',
      ]) {
        if (payload[name] != challenge[name]) invalid();
      }
      if (operation == 'replace_device' &&
          (payload['replaced_device_id'] != replacedDeviceId ||
              payload['replaced_device_fingerprint'] !=
                  replacedDeviceFingerprint)) {
        invalid();
      }
      if (payload['purpose'] != 'device_activation' ||
          payload['version'] != 1 ||
          payload['student_id'] != student ||
          payload['nonce'] is! String ||
          (payload['nonce'] as String).isEmpty ||
          payload['expires_at'] != challenge['expires_at'] ||
          !DateTime.parse(
            challenge['expires_at'] as String,
          ).isAfter(DateTime.now())) {
        invalid();
      }
    } on ApiException {
      rethrow;
    } catch (_) {
      invalid();
    }
    progress?.call('Signing activation challenge');
    String signature;
    try {
      signature = await _keys
          .sign(student, challenge['signing_payload'] as String)
          .timeout(const Duration(seconds: 8));
    } on PlatformException {
      throw const ApiException(
        'The retained candidate key could not sign. Do not reinstall or rotate its key.',
        409,
        'LOCAL_KEY_MISSING',
      );
    }
    check();
    progress?.call('Waiting for server activation confirmation');
    try {
      final raw = await bounded(
        _client.post('$path/activate', {
          'challenge_id': challenge['challenge_id'],
          'approval_id': challenge['approval_id'],
          'signature': signature,
        }),
      );
      check();
      if (raw is! Map ||
          raw['success'] != true ||
          raw['attendance_authorized'] != false) {
        invalid();
      }
      return device(raw['device']);
    } on ApiException catch (error) {
      check();
      if (error.status != 0 || error.code == 'INVALID_ACTIVATION_RESPONSE') {
        rethrow;
      }
      // Reconcile uncertain submission once; never replay a consumed signature.
      final recovered = await status();
      if (recovered['status'] == 'ACTIVE') return device(recovered['device']);
      rethrow;
    }
  }
}
