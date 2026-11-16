import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import '../../devices/services/device_key_store.dart';
import 'ble_diagnostics.dart';
import 'classroom_ble_observation.dart';

/// Standalone and attendance shadow checks. No receipt authorizes attendance.
class ClassroomBleApi {
  ClassroomBleApi({
    ApiClient? client,
    DeviceKeyStore? keys,
    BleDiagnostics? scanner,
  }) : _client = client ?? ApiClient.instance,
       _keys = keys ?? const DeviceKeyStore(),
       _scanner = scanner ?? const BleDiagnostics();
  final ApiClient _client;
  final DeviceKeyStore _keys;
  final BleDiagnostics _scanner;
  static const path = '/api/v1/classroom-ble',
      operation = 'classroom_ble_verification',
      shadowOperation = 'attendance_ble_shadow';
  bool _inFlight = false, _scanning = false;
  String? _scanOwner;
  int _generation = 0;
  Future<void> cancel() async {
    _generation++;
    if (_scanning) await _scanner.cancel(requestId: _scanOwner);
  }

  Future<BleSnapshot> _freshScan(String owner, void Function() current) async {
    final status = await _scanner.status();
    current();
    if (!status.ready) return status;
    _scanning = true;
    _scanOwner = owner;
    try {
      final scan = await _scanner.scan(requestId: owner);
      current();
      return scan;
    } finally {
      _scanning = false;
      _scanOwner = null;
    }
  }

  Future<ClassroomBleObservation> observe(Map<String, int> thresholds) async {
    if (_inFlight || thresholds.isEmpty) {
      return ClassroomBleObservation(
        BleObservationStatus.unavailable,
        _inFlight ? 'BLE_CHECK_IN_PROGRESS' : 'NO_ENABLED_BLE_POLICY',
      );
    }
    _inFlight = true;
    final gen = ++_generation;
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    void current() {
      session(student, revision);
      if (gen != _generation) {
        throw const ApiException('Scan cancelled.', 0, 'BLE_CHECK_CANCELLED');
      }
    }

    try {
      current();
      final started = DateTime.now().millisecondsSinceEpoch;
      final scan = await _freshScan(
        'observe-${identityHashCode(this)}-$gen',
        current,
      );
      return ClassroomBleObservation.fromScan(
        scan,
        thresholds,
        requestedAtMs: started,
        nowMs: DateTime.now().millisecondsSinceEpoch,
      );
    } on TimeoutException {
      return const ClassroomBleObservation(
        BleObservationStatus.unavailable,
        'BLE_SCAN_TIMEOUT',
      );
    } on PlatformException {
      return const ClassroomBleObservation(
        BleObservationStatus.unavailable,
        'BLE_UNAVAILABLE',
      );
    } on MissingPluginException {
      return const ClassroomBleObservation(
        BleObservationStatus.unavailable,
        'BLE_UNSUPPORTED',
      );
    } finally {
      _inFlight = false;
    }
  }

  void session(String? student, int revision) {
    if (student == null ||
        !_client.authenticated.value ||
        _client.student?['student_id'] != student ||
        _client.sessionRevision != revision) {
      throw const ApiException(
        'Sign in again before verifying a classroom beacon.',
        401,
        'SESSION_CHANGED',
      );
    }
  }

  Future<List<Map<String, dynamic>>> classrooms() async {
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    session(student, revision);
    final raw = await _client
        .get('$path/classrooms')
        .timeout(const Duration(seconds: 15));
    session(student, revision);
    if (raw is! Map ||
        raw['success'] != true ||
        raw['simulation_only'] != true ||
        raw['classrooms'] is! List) {
      throw const FormatException('Invalid BLE classroom list.');
    }
    return (raw['classrooms'] as List).map((r) {
      if (r is! Map ||
          r['classroom_id'] is! String ||
          r['name'] is! String ||
          r['policies'] is! List) {
        throw const FormatException('Invalid BLE classroom.');
      }
      return Map<String, dynamic>.from(r);
    }).toList();
  }

  /// Only approved UUID observations are sent; names, addresses, service data
  /// and unrelated advertisers never enter the signed/uploaded report.
  static Map<String, dynamic> evidence(
    BleSnapshot scan,
    Set<String> approved, {
    int? nowMs,
  }) {
    final completed =
        scan.completedAtMs ?? nowMs ?? DateTime.now().millisecondsSinceEpoch;
    final started = scan.startedAtMs ?? completed;
    if (scan.status == 'COMPLETE' &&
        (scan.startedAtMs == null || scan.completedAtMs == null)) {
      throw const ApiException(
        'Update the tablet app: timestamped BLE observations are unavailable.',
        0,
        'BLE_SCANNER_UPDATE_REQUIRED',
      );
    }
    final found = <String, Map<int, int>>{};
    for (final group in matchingBleSamples(scan, approved)) {
      (found[group.uuid] ??= <int, int>{}).addAll(group.samples);
    }
    final flattened = <Map<String, dynamic>>[];
    for (final entry in found.entries) {
      for (final sample in entry.value.entries) {
        flattened.add({
          'uuid': entry.key,
          'offset': sample.key,
          'rssi': sample.value,
        });
      }
    }
    flattened.sort(
      (a, b) => (b['offset'] as int).compareTo(a['offset'] as int),
    );
    final selected = <String, List<Map<String, int>>>{};
    for (final s in flattened.take(50)) {
      (selected[s['uuid'] as String] ??= <Map<String, int>>[]).add({
        'offset_us': s['offset'] as int,
        'rssi_dbm': s['rssi'] as int,
      });
    }
    final beacons = <Map<String, dynamic>>[];
    for (final uuid in selected.keys.toList()..sort()) {
      final samples = selected[uuid]!
        ..sort((a, b) => a['offset_us']!.compareTo(b['offset_us']!));
      beacons.add({'service_uuid': uuid, 'samples': samples});
    }
    return {
      'scan_status': scan.status,
      'bluetooth_enabled': scan.bluetoothEnabled,
      'scan_permission': scan.scanPermission,
      'connect_permission': scan.connectPermission,
      'location_permission': scan.locationPermission,
      'location_enabled': scan.locationEnabled,
      'scan_started_at_ms': started,
      'scan_completed_at_ms': completed,
      'scan_duration_ms': scan.scanDurationMs,
      'beacons': beacons,
    };
  }

  Future<Map<String, dynamic>> verify(String classroom) => _verify(classroom);

  Future<Map<String, dynamic>> verifyAttendance(
    String classroom,
    String attempt,
    String preflightProof,
  ) => _verify(classroom, attempt: attempt, preflightProof: preflightProof);

  Future<Map<String, dynamic>> _verify(
    String classroom, {
    String? attempt,
    String? preflightProof,
  }) async {
    if (_inFlight) {
      throw const ApiException(
        'A BLE check is already finishing. Wait before retrying.',
        0,
        'BLE_CHECK_IN_PROGRESS',
      );
    }
    _inFlight = true;
    final gen = ++_generation;
    final student = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    final shadow = attempt != null;
    final expectedOperation = shadow ? shadowOperation : operation;
    final post = shadow ? _client.postDiagnostic : _client.post;
    final requestTimeout = Duration(seconds: shadow ? 4 : 15);
    void current() {
      session(student, revision);
      if (gen != _generation) {
        throw const ApiException(
          'BLE check cancelled. Start a fresh check.',
          0,
          'BLE_CHECK_CANCELLED',
        );
      }
    }

    try {
      current();
      final key = await _keys
          .getPublicKey(student!)
          .timeout(const Duration(seconds: 5));
      current();
      if (key == null) {
        throw const ApiException(
          'This installation has no registered private key. Open My Device.',
          0,
          'LOCAL_KEY_MISSING',
        );
      }
      final ch = await post('$path/challenges', {
        'classroom_id': classroom,
        'public_key_fingerprint': key['public_key_fingerprint'],
        if (shadow) 'attendance_attempt_id': attempt,
        if (shadow) 'preflight_proof_id': preflightProof,
      }).timeout(requestTimeout);
      current();
      if (ch is! Map ||
          ch['success'] != true ||
          ch['operation'] != expectedOperation ||
          (shadow &&
              (ch['attendance_attempt_id'] != attempt ||
                  ch['preflight_proof_id'] != preflightProof ||
                  ch['attendance_session_id'] is! int)) ||
          ch['classroom_id'] != classroom ||
          ch['public_key_fingerprint'] != key['public_key_fingerprint'] ||
          ch['device_id'] is! String ||
          ch['challenge_id'] is! String ||
          ch['signing_payload'] is! String ||
          ch['approved_policies'] is! List ||
          ch['scan_window_ms'] != 8000 ||
          ch['expires_at'] is! String ||
          DateTime.tryParse(ch['expires_at']) == null ||
          !DateTime.parse(ch['expires_at']).isAfter(DateTime.now())) {
        throw const FormatException('Invalid BLE challenge.');
      }
      final approved = <String>{};
      for (final p in ch['approved_policies'] as List) {
        if (p is! Map ||
            p['enabled'] != true ||
            p['simulation_only'] != true ||
            p['classroom_id'] != classroom ||
            p['service_uuid'] is! String) {
          throw const FormatException('Invalid approved beacon policy.');
        }
        approved.add((p['service_uuid'] as String).toLowerCase());
      }
      if (approved.isEmpty || approved.length > 4) {
        throw const FormatException('Invalid beacon policy count.');
      }
      final scan = await _freshScan(ch['challenge_id'] as String, current);
      final raw = utf8.encode(jsonEncode(evidence(scan, approved)));
      final bytes = [...base64Decode(ch['signing_payload']), 10, ...raw];
      final payload = base64Encode(bytes);
      if (raw.length > 4500 || payload.length > 8192) {
        throw const ApiException(
          'BLE report exceeds the safe signing bound. Repeat the scan.',
          0,
          'BLE_EVIDENCE_TOO_LARGE',
        );
      }
      final signature = await _keys
          .sign(student, payload)
          .timeout(const Duration(seconds: 8));
      current();
      final result = await post('$path/verifications', {
        'challenge_id': ch['challenge_id'],
        'evidence_payload': base64Encode(raw),
        'signature': signature,
      }).timeout(requestTimeout);
      current();
      if (result is! Map ||
          result['success'] != true ||
          !['PASS', 'FAIL', 'UNCERTAIN'].contains(result['result']) ||
          result['operation'] != expectedOperation ||
          (shadow &&
              (result['attendance_attempt_id'] != attempt ||
                  result['preflight_proof_id'] != preflightProof ||
                  result['attendance_session_id'] !=
                      ch['attendance_session_id'])) ||
          result['classroom_id'] != classroom ||
          result['device_id'] != ch['device_id'] ||
          result['challenge_id'] != ch['challenge_id'] ||
          result['attendance_authorized'] != false ||
          result['evidence_source'] != 'CLIENT_REPORTED_ANDROID_BLE' ||
          result['reason_code'] is! String ||
          result['message'] is! String ||
          result['sample_count'] is! int ||
          result['sample_count'] < 0 ||
          result['sample_count'] > 50 ||
          result['verification_id'] is! int ||
          result['verification_id'] <= 0 ||
          (result['result'] == 'PASS' &&
              (result['reason_code'] != 'BLE_APPROVED' ||
                  result['matched_policy_id'] is! String ||
                  result['median_rssi_dbm'] is! num ||
                  result['rssi_threshold'] is! int))) {
        throw const FormatException('Invalid BLE verification response.');
      }
      if (result['result'] == 'PASS') {
        final policy = (ch['approved_policies'] as List)
            .where((p) => p['policy_id'] == result['matched_policy_id'])
            .firstOrNull;
        if (policy == null ||
            policy['minimum_samples'] is! int ||
            result['sample_count'] < policy['minimum_samples'] ||
            result['rssi_threshold'] != policy['rssi_threshold'] ||
            !(result['median_rssi_dbm'] as num).isFinite ||
            result['median_rssi_dbm'] < result['rssi_threshold']) {
          throw const FormatException(
            'BLE PASS does not match the issued policy.',
          );
        }
      }
      return Map<String, dynamic>.from(result);
    } on TimeoutException {
      throw const ApiException(
        'The BLE check timed out. No server result was confirmed. Check the connection and retry.',
        0,
        'BLE_CHECK_TIMEOUT',
      );
    } on PlatformException {
      throw const ApiException(
        'Android could not scan or sign this check. Check Bluetooth, Nearby Devices and My Device.',
        0,
        'BLE_ANDROID_UNAVAILABLE',
      );
    } finally {
      _inFlight = false;
    }
  }
}
