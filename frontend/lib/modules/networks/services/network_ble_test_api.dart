import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import '../../devices/services/device_key_store.dart';
import 'ble_diagnostics.dart';
import 'classroom_ble_api.dart';
import 'classroom_wifi_api.dart';
import 'wifi_diagnostics.dart';

/// Temporary diagnostic only. Never creates or submits an attendance attempt.
class NetworkBleTestApi {
  NetworkBleTestApi({
    ApiClient? client,
    DeviceKeyStore? keys,
    WifiDiagnostics? wifi,
    BleDiagnostics? scanner,
  }) : _client = client ?? ApiClient.instance,
       _keys = keys ?? const DeviceKeyStore(),
       _wifi = wifi ?? const WifiDiagnostics(),
       _scanner = scanner ?? const BleDiagnostics();

  static const path = '/api/v1/network-ble-tests';
  final ApiClient _client;
  final DeviceKeyStore _keys;
  final WifiDiagnostics _wifi;
  final BleDiagnostics _scanner;
  String? _owner;
  bool _running = false;
  int _generation = 0;

  Future<void> cancel() async {
    _generation++;
    final owner = _owner;
    if (owner != null) await _scanner.cancel(requestId: owner);
  }

  Future<List<Map<String, dynamic>>> sessions() async {
    final response = await _client
        .get('$path/sessions')
        .timeout(const Duration(seconds: 10));
    if (response is! Map ||
        response['diagnostic_test'] != true ||
        response['sessions'] is! List) {
      throw const FormatException('Invalid diagnostic session list.');
    }
    return (response['sessions'] as List)
        .map((row) => Map<String, dynamic>.from(row as Map))
        .toList();
  }

  Future<Map<String, dynamic>> run(int sessionId, String pin) async {
    if (_running) {
      throw const ApiException(
        'A test is already running.',
        409,
        'TEST_IN_PROGRESS',
      );
    }
    _running = true;
    final revision = _client.sessionRevision;
    final student = _client.student?['student_id'] as String?;
    final generation = ++_generation;
    void current() {
      if (student == null ||
          !_client.authenticated.value ||
          revision != _client.sessionRevision ||
          generation != _generation ||
          student != _client.student?['student_id']) {
        throw const ApiException(
          'Restart this diagnostic after signing in.',
          401,
          'TEST_CANCELLED',
        );
      }
    }

    Future<Map<String, dynamic>> sign(Map challenge, List<int> evidence) async {
      current();
      final payload = [
        ...base64Decode(challenge['signing_payload'] as String),
        10,
        ...evidence,
      ];
      final signature = await _keys
          .sign(student!, base64Encode(payload))
          .timeout(const Duration(seconds: 8));
      current();
      return {
        'challenge_id': challenge['challenge_id'],
        'evidence_payload': base64Encode(evidence),
        'signature': signature,
      };
    }

    try {
      current();
      final key = await _keys
          .getPublicKey(student!)
          .timeout(const Duration(seconds: 5));
      current();
      if (key == null) {
        throw const ApiException(
          'Register this installation first.',
          409,
          'LOCAL_KEY_MISSING',
        );
      }
      final start = await _client
          .postDiagnostic('$path/start', {
            'session_id': sessionId,
            'pin': pin,
            'public_key_fingerprint': key['public_key_fingerprint'],
          })
          .timeout(const Duration(seconds: 10));
      current();
      if (start is! Map ||
          start['success'] != true ||
          start['diagnostic_test'] != true ||
          start['attendance_authorized'] != false ||
          start['test_id'] is! String) {
        throw const FormatException('Invalid diagnostic start.');
      }
      final testId = start['test_id'] as String;
      Map<String, dynamic> validateResult(dynamic value) {
        if (value is! Map ||
            value['success'] != true ||
            value['diagnostic_test'] != true ||
            value['attendance_authorized'] != false ||
            value['test_id'] != testId ||
            value['session_id'] != sessionId ||
            !['PASS', 'FAIL'].contains(value['test_result']) ||
            value['reason_code'] is! String) {
          throw const FormatException('Invalid diagnostic result.');
        }
        if (value['test_result'] == 'PASS' &&
            (value['reason_code'] != 'NETWORK_BLE_TEST_PASS' ||
                ['network', 'wifi', 'ble'].any(
                  (stage) =>
                      value[stage] is! Map || value[stage]['result'] != 'PASS',
                ))) {
          throw const FormatException('Incomplete diagnostic PASS.');
        }
        return Map<String, dynamic>.from(value);
      }

      if (start['test_result'] != null) return validateResult(start);
      final wifiChallenge = start['wifi'], bleChallenge = start['ble'];
      for (final (challenge, operation) in [
        (wifiChallenge, ClassroomWifiApi.operation),
        (bleChallenge, ClassroomBleApi.operation),
      ]) {
        if (challenge is! Map ||
            challenge['operation'] != operation ||
            challenge['public_key_fingerprint'] !=
                key['public_key_fingerprint'] ||
            challenge['classroom_id'] != start['classroom_id'] ||
            challenge['challenge_id'] is! String ||
            challenge['signing_payload'] is! String) {
          throw const FormatException('Invalid diagnostic challenge.');
        }
        final binding =
            jsonDecode(
                  utf8.decode(
                    base64Decode(challenge['signing_payload'] as String),
                  ),
                )
                as Map;
        if (binding['diagnostic_test'] != true ||
            binding['test_id'] != testId ||
            binding['test_session_id'] != sessionId) {
          throw const FormatException('Diagnostic challenge binding changed.');
        }
      }
      final policies = bleChallenge['approved_policies'];
      if (policies is! List || policies.isEmpty || policies.length > 4) {
        throw const FormatException('No diagnostic BLE policies.');
      }
      final approved = <String>{};
      for (final policy in policies) {
        if (policy is! Map ||
            policy['enabled'] != true ||
            policy['simulation_only'] != true ||
            policy['classroom_id'] != start['classroom_id'] ||
            policy['service_uuid'] is! String) {
          throw const FormatException('Invalid diagnostic BLE policy.');
        }
        approved.add((policy['service_uuid'] as String).toLowerCase());
      }
      final wifi = await _wifi.read();
      final wifiProof = await sign(
        wifiChallenge as Map,
        utf8.encode(jsonEncode(wifi.toEvidenceMap())),
      );
      current();
      final status = await _scanner.status();
      current();
      _owner = testId;
      final scan = status.ready
          ? await _scanner.scan(requestId: testId)
          : status;
      _owner = null;
      current();
      final bleProof = await sign(
        bleChallenge as Map,
        utf8.encode(jsonEncode(ClassroomBleApi.evidence(scan, approved))),
      );
      final response = await _client
          .postDiagnostic('$path/finish', {
            'test_id': testId,
            'wifi': wifiProof,
            'ble': bleProof,
          })
          .timeout(const Duration(seconds: 10));
      current();
      return validateResult(response);
    } on TimeoutException {
      throw const ApiException(
        'The test timed out. No complete server result was confirmed.',
        0,
        'TEST_TIMEOUT',
      );
    } on PlatformException {
      throw const ApiException(
        'Android diagnostic evidence is unavailable.',
        0,
        'ANDROID_EVIDENCE_UNAVAILABLE',
      );
    } finally {
      final owner = _owner;
      _owner = null;
      _running = false;
      if (owner != null) {
        unawaited(_scanner.cancel(requestId: owner).catchError((Object _) {}));
      }
    }
  }
}
