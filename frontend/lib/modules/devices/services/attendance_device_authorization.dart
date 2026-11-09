import 'dart:convert';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import 'device_key_store.dart';
import '../../networks/services/classroom_wifi_api.dart';

/// Caches only a signed, attempt-bound unconsumed nonce, never a PASS/grant.
/// The final writer rechecks ACTIVE ownership, expiry, one-time use and network.
class AttendanceDeviceAuthorization {
  AttendanceDeviceAuthorization({
    ApiClient? client,
    DeviceKeyStore? keys,
    DateTime Function()? now,
    ClassroomWifiApi? classroomWifi,
  }) : _client = client ?? ApiClient.instance,
       _keys = keys ?? const DeviceKeyStore(),
       _now = now ?? DateTime.now,
       _wifi = classroomWifi ?? ClassroomWifiApi(client: client, keys: keys);
  final ClassroomWifiApi _wifi;
  final DateTime Function() _now;
  final ApiClient _client;
  final DeviceKeyStore _keys;
  final Map<String, Map<String, dynamic>> _proofs = {};
  final Map<String, Future<Map<String, String>>> _flights = {};

  /// Fresh server check only; the final writer requires another signed nonce.
  Future<void> preflight(String attendanceId) async {
    final revision = _client.sessionRevision;
    final fields = await _proof(attendanceId, '', preflight: true);
    final response = await _client
        .post('/api/v1/attendance/preflight', {
          'attendance_challenge_id': attendanceId,
          'challenge_id': fields['device_challenge_id'],
          'signature': fields['device_signature'],
          if (fields['classroom_wifi_proof_id'] != null)
            'classroom_wifi_proof_id': fields['classroom_wifi_proof_id'],
        })
        .timeout(const Duration(seconds: 15));
    if (!_client.authenticated.value ||
        revision != _client.sessionRevision ||
        response is! Map ||
        response['success'] != true ||
        response['result'] != 'PASS' ||
        response['attendance_authorized'] != false ||
        response['attendance_challenge_id'] != attendanceId) {
      throw const ApiException(
        'Attendance readiness could not be confirmed. Enter the PIN again.',
        403,
        'ATTENDANCE_PREFLIGHT_FAILED',
      );
    }
  }

  Future<Map<String, String>> proof(String attendanceId) {
    final key =
        '${_client.sessionRevision}:${_client.student?['student_id']}:$attendanceId';
    return _flights.putIfAbsent(
      key,
      () => _proof(attendanceId, key).whenComplete(() {
        _flights.remove(key);
      }),
    );
  }

  Future<Map<String, String>> _proof(
    String attendanceId,
    String cacheKey, {
    bool preflight = false,
  }) async {
    final operation = preflight
        ? 'attendance_preflight'
        : 'attendance_authorization';
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    void current() {
      if (student == null ||
          !_client.authenticated.value ||
          revision != _client.sessionRevision ||
          _client.student?['student_id'] != student) {
        throw const ApiException(
          'Your login changed. Enter the class PIN again.',
          401,
          'ATTENDANCE_SESSION_CHANGED',
        );
      }
    }

    Never invalid() => throw const ApiException(
      'Invalid attendance device challenge. Restart attendance.',
      409,
      'ATTENDANCE_DEVICE_BINDING_CHANGED',
    );
    current();
    Map<String, dynamic>? local;
    try {
      local = await _keys
          .getPublicKey(student!)
          .timeout(const Duration(seconds: 5));
    } on PlatformException {
      throw const ApiException(
        'The registered Android key is unavailable. Use the original registered installation.',
        409,
        'LOCAL_KEY_MISSING',
      );
    }
    current();
    if (local == null) {
      throw const ApiException(
        'The registered private key is missing from this installation. Use an ACTIVE registered phone or complete approved device enrollment.',
        409,
        'LOCAL_KEY_MISSING',
      );
    }
    final fingerprint = local['public_key_fingerprint'];
    if (fingerprint is! String || fingerprint.isEmpty) {
      invalid();
    }
    final cached = preflight ? null : _proofs[cacheKey];
    if (cached != null &&
        cached['fingerprint'] == fingerprint &&
        DateTime.parse(cached['expires_at'] as String).isAfter(_now())) {
      return _withWifi(
        attendanceId,
        Map<String, String>.from(cached['fields'] as Map),
        cached['challenge'] as Map,
        preflight: false,
      );
    }
    _proofs.removeWhere(
      (key, value) =>
          !DateTime.parse(value['expires_at'] as String).isAfter(_now()),
    );
    final raw = await _client
        .post(
          preflight
              ? '/api/v1/attendance/preflight-challenges'
              : '/api/v1/attendance/device-challenges',
          {
            'attendance_challenge_id': attendanceId,
            'public_key_fingerprint': fingerprint,
          },
        )
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => throw const ApiException(
            'Attendance device verification timed out. Check the backend and start again.',
            0,
            'ATTENDANCE_DEVICE_TIMEOUT',
          ),
        );
    current();
    if (raw is! Map) {
      invalid();
    }
    final challenge = Map<String, dynamic>.from(raw);
    if (challenge['success'] != true ||
        challenge['attendance_challenge_id'] != attendanceId ||
        challenge['public_key_fingerprint'] != fingerprint ||
        challenge['operation'] != operation ||
        ![1, 2].contains(challenge['slot_number']) ||
        challenge['algorithm'] != 'ECDSA_P256_SHA256' ||
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
      for (final field in [
        'challenge_id',
        'attendance_challenge_id',
        'attendance_session_id',
        'device_id',
        'slot_number',
        'public_key_fingerprint',
        'operation',
        'expires_at',
      ]) {
        if (payload[field] != challenge[field]) {
          invalid();
        }
      }
      if (payload['purpose'] != operation ||
          payload['version'] != 1 ||
          payload['student_id'] != student ||
          payload['auth_session_hash'] is! String ||
          payload['nonce'] is! String ||
          payload['biometric_verification_id'] is! int ||
          !DateTime.parse(challenge['expires_at'] as String).isAfter(_now())) {
        invalid();
      }
    } on ApiException {
      rethrow;
    } catch (_) {
      invalid();
    }
    String signature;
    try {
      signature = await _keys
          .sign(student, challenge['signing_payload'] as String)
          .timeout(const Duration(seconds: 8));
    } on PlatformException {
      throw const ApiException(
        'The registered device key could not sign attendance. Keep existing keys unchanged.',
        409,
        'LOCAL_KEY_MISSING',
      );
    }
    current();
    final fields = {
      'device_challenge_id': challenge['challenge_id'] as String,
      'device_signature': signature,
    };
    if (!preflight) {
      _proofs[cacheKey] = {
        'fields': fields,
        'fingerprint': fingerprint,
        'expires_at': challenge['expires_at'],
        'challenge': challenge,
      };
    }
    return _withWifi(attendanceId, fields, challenge, preflight: preflight);
  }

  Future<Map<String, String>> _withWifi(
    String attempt,
    Map<String, String> fields,
    Map challenge, {
    required bool preflight,
  }) async {
    if (challenge['classroom_wifi_required'] != true) return fields;
    final classroom = challenge['classroom_id'];
    if (classroom is! String || classroom.isEmpty) {
      throw const ApiException(
        'The required classroom is unavailable. Enter the PIN again.',
        409,
        'CLASSROOM_REQUIREMENT_INVALID',
      );
    }
    final result = await _wifi.attendance(
      classroom,
      attempt,
      fields['device_challenge_id']!,
      preflight: preflight,
    );
    if (result['result'] != 'PASS') {
      throw ApiException(
        result['message'] as String,
        403,
        result['reason_code'] as String,
      );
    }
    return {
      ...fields,
      'classroom_wifi_proof_id': result['classroom_wifi_proof_id'] as String,
    };
  }

  void completed(String attendanceId) {
    _proofs.removeWhere((key, value) => key.endsWith(':$attendanceId'));
  }
}
