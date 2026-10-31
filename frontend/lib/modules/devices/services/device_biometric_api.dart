import 'dart:typed_data';
import '../../../services/api_client.dart';

/// Only device-enrollment endpoints. Every response remains an untrusted test.
class DeviceBiometricApi {
  DeviceBiometricApi([ApiClient? client])
    : _client = client ?? ApiClient.instance;
  final ApiClient _client;
  int? _revision;
  String? _student, _pending, _approval, _fingerprint, _candidate;

  void _checkSession() {
    if (!_client.authenticated.value ||
        _student == null ||
        _revision != _client.sessionRevision ||
        _client.student?['student_id'] != _student) {
      throw const ApiException(
        'Your login changed. Restart device biometric checks.',
        401,
        'SESSION_CHANGED',
      );
    }
  }

  Map<String, dynamic> _result(dynamic raw) {
    final result = Map<String, dynamic>.from(raw as Map);
    const stages = {
      'FACE',
      'LIVENESS',
      'COMPLETED_UNTRUSTED',
      'FAILED',
      'EXPIRED',
    };
    if (result['pending_registration_id'] != _pending ||
        result['operation'] != 'enroll_second_device' ||
        result['slot_number'] != 2 ||
        result['result_classification'] != 'UNTRUSTED_TEST_RESULT' ||
        result['trusted'] != false ||
        result['consumable'] != false ||
        result['activation_eligible'] != false ||
        result['activation_enabled'] != false ||
        !stages.contains(result['stage']) ||
        result['complete'] != (result['stage'] == 'COMPLETED_UNTRUSTED') ||
        result['face_verified'] !=
            (result['stage'] == 'LIVENESS' ||
                result['stage'] == 'COMPLETED_UNTRUSTED') ||
        result['liveness_verified'] !=
            (result['stage'] == 'COMPLETED_UNTRUSTED') ||
        (_approval != null && result['approval_id'] != _approval) ||
        (_fingerprint != null &&
            result['public_key_fingerprint'] != _fingerprint) ||
        (_candidate != null && result['candidate_device_id'] != _candidate)) {
      throw const ApiException(
        'The server returned an incompatible device biometric result.',
        0,
        'INVALID_BIOMETRIC_RESPONSE',
      );
    }
    return result;
  }

  Future<Map<String, dynamic>> begin(String pendingId) async {
    _revision = _client.sessionRevision;
    _student = _client.student?['student_id'] as String?;
    _pending = pendingId;
    _approval = null;
    _fingerprint = null;
    _candidate = null;
    _checkSession();
    final raw = await _client
        .post('/api/v1/device-approvals', {
          'pending_registration_id': pendingId,
        })
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => throw const ApiException(
            'Device biometric request timed out. Check the server and restart.',
            0,
            'REQUEST_TIMEOUT',
          ),
        );
    _checkSession();
    final result = _result(raw);
    _approval = result['approval_id'] as String;
    _fingerprint = result['public_key_fingerprint'] as String;
    _candidate = result['candidate_device_id'] as String;
    return result;
  }

  Future<Map<String, dynamic>> status() async {
    _checkSession();
    if (_approval == null) {
      throw const ApiException('Start a biometric test first.');
    }
    final raw = await _client
        .get('/api/v1/device-approvals/${Uri.encodeComponent(_approval!)}')
        .timeout(
          const Duration(seconds: 5),
          onTimeout: () => throw const ApiException(
            'Could not confirm device biometric status in time. Restart the scan.',
            0,
            'REQUEST_TIMEOUT',
          ),
        );
    _checkSession();
    return _result(raw);
  }

  Future<Map<String, dynamic>> frame(
    Uint8List bytes, {
    required bool liveness,
  }) async {
    _checkSession();
    if (_approval == null) {
      throw const ApiException('Start a biometric test first.');
    }
    final stage = liveness ? 'liveness/frame' : 'face';
    final raw = await _client
        .image(
          '/api/v1/device-approvals/${Uri.encodeComponent(_approval!)}/$stage',
          bytes,
          {},
        )
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => throw const ApiException(
            'Device biometric frame timed out. Check the server and restart.',
            0,
            'REQUEST_TIMEOUT',
          ),
        );
    _checkSession();
    return _result(raw);
  }
}
