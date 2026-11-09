import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import '../../devices/services/device_key_store.dart';
import 'wifi_diagnostics.dart';

/// Explicit diagnostic only. The backend decides; no cached authorization.
class ClassroomWifiApi {
  ClassroomWifiApi({
    ApiClient? client,
    DeviceKeyStore? keys,
    WifiDiagnostics? wifi,
  }) : _client = client ?? ApiClient.instance,
       _keys = keys ?? const DeviceKeyStore(),
       _wifi = wifi ?? const WifiDiagnostics();
  final ApiClient _client;
  final DeviceKeyStore _keys;
  final WifiDiagnostics _wifi;
  static const path = '/api/v1/classroom-wifi';
  static const operation = 'classroom_wifi_verification';

  void requireSession(String? student, int revision) {
    if (student == null ||
        !_client.authenticated.value ||
        _client.student?['student_id'] != student ||
        _client.sessionRevision != revision) {
      throw const ApiException(
        'Sign in again before checking classroom Wi-Fi.',
        401,
        'SESSION_CHANGED',
      );
    }
  }

  Future<List<Map<String, dynamic>>> classrooms() async {
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    requireSession(student, revision);
    final raw = await _client
        .get('$path/classrooms')
        .timeout(const Duration(seconds: 15));
    requireSession(student, revision);
    if (raw is! Map ||
        raw['success'] != true ||
        raw['simulation_only'] != true ||
        raw['classrooms'] is! List) {
      throw const FormatException('Invalid classroom list.');
    }
    return (raw['classrooms'] as List).map((r) {
      if (r is! Map || r['classroom_id'] is! String || r['name'] is! String) {
        throw const FormatException('Invalid classroom.');
      }
      return Map<String, dynamic>.from(r);
    }).toList();
  }

  Future<Map<String, dynamic>> verify(String classroom) => _verify(classroom);

  Future<Map<String, dynamic>> attendance(
    String classroom,
    String attempt,
    String deviceChallenge, {
    required bool preflight,
  }) => _verify(
    classroom,
    attempt: attempt,
    deviceChallenge: deviceChallenge,
    preflight: preflight,
  );

  Future<Map<String, dynamic>> _verify(
    String classroom, {
    String? attempt,
    String? deviceChallenge,
    bool preflight = false,
  }) async {
    final expectedOperation = attempt == null
        ? operation
        : preflight
        ? 'attendance_classroom_preflight'
        : 'attendance_classroom_final';
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    requireSession(student, revision);
    try {
      // Never create, replace or delete an existing Keystore key here.
      final local = await _keys
          .getPublicKey(student!)
          .timeout(const Duration(seconds: 8));
      requireSession(student, revision);
      if (local == null) {
        throw const ApiException(
          'This installation has no registered private key. Open My Device.',
          0,
          'LOCAL_KEY_MISSING',
        );
      }
      final raw = await _client
          .post(
            attempt == null
                ? '$path/challenges'
                : '$path/attendance-challenges',
            attempt == null
                ? {
                    'classroom_id': classroom,
                    'public_key_fingerprint': local['public_key_fingerprint'],
                  }
                : {
                    'attendance_challenge_id': attempt,
                    'device_challenge_id': deviceChallenge,
                    'preflight': preflight,
                  },
          )
          .timeout(const Duration(seconds: 15));
      requireSession(student, revision);
      if (raw is! Map ||
          raw['success'] != true ||
          raw['operation'] != expectedOperation ||
          raw['classroom_id'] != classroom ||
          raw['public_key_fingerprint'] != local['public_key_fingerprint'] ||
          raw['challenge_id'] is! String ||
          raw['signing_payload'] is! String ||
          raw['device_id'] is! String ||
          raw['expires_at'] is! String ||
          DateTime.tryParse(raw['expires_at']) == null ||
          !DateTime.parse(raw['expires_at']).isAfter(DateTime.now())) {
        throw const FormatException('Invalid or expired classroom challenge.');
      }
      // Take a new Android snapshot AFTER the nonce. Never sign Phase 1's cached reading.
      final reading = await _wifi.read();
      requireSession(student, revision);
      final evidence = utf8.encode(jsonEncode(reading.toEvidenceMap()));
      final bytes = [...base64Decode(raw['signing_payload']), 10, ...evidence];
      final signature = await _keys
          .sign(student, base64Encode(bytes))
          .timeout(const Duration(seconds: 8));
      requireSession(student, revision);
      final response = await _client
          .post('$path/verifications', {
            'challenge_id': raw['challenge_id'],
            'evidence_payload': base64Encode(evidence),
            'signature': signature,
          })
          .timeout(const Duration(seconds: 15));
      requireSession(student, revision);
      if (response is! Map ||
          response['success'] != true ||
          !['PASS', 'FAIL'].contains(response['result']) ||
          response['operation'] != expectedOperation ||
          response['attendance_authorized'] != false ||
          response['evidence_source'] != 'CLIENT_REPORTED_ANDROID_WIFI' ||
          response['classroom_id'] != classroom ||
          response['device_id'] != raw['device_id'] ||
          response['reason_code'] is! String ||
          response['message'] is! String ||
          response['verification_id'] is! int ||
          response['verification_id'] <= 0 ||
          response['verified_at'] is! String ||
          DateTime.tryParse(response['verified_at']) == null ||
          (response['result'] == 'PASS' &&
              (response['reason_code'] != 'CLASSROOM_WIFI_APPROVED' ||
                  response['matched_policy_id'] is! String)) ||
          (response['result'] == 'FAIL' &&
              response['matched_policy_id'] != null)) {
        throw const FormatException('Invalid classroom verification response.');
      }
      return {
        ...Map<String, dynamic>.from(response),
        'classroom_wifi_proof_id': raw['challenge_id'],
      };
    } on TimeoutException {
      throw const ApiException(
        'Classroom verification timed out. No classroom policy result was confirmed. Check the backend connection and refresh.',
        0,
        'CLASSROOM_CHECK_TIMEOUT',
      );
    } on PlatformException {
      throw const ApiException(
        'Android could not read Wi-Fi details or sign this check. Check permissions and My Device, then refresh.',
        0,
        'ANDROID_EVIDENCE_UNAVAILABLE',
      );
    }
  }
}
