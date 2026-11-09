import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/devices/services/attendance_device_authorization.dart';
import 'package:frontend/modules/devices/services/authorized_attendance_biometric_api.dart';
import 'package:frontend/modules/networks/services/classroom_wifi_api.dart';
import 'package:frontend/services/api_client.dart';
import 'attendance_authorization_test.dart' show AttendanceFixture;

class AttendanceWifi extends ClassroomWifiApi {
  final calls = <String>[];
  String code = 'CLASSROOM_WIFI_APPROVED';
  Object? error;
  @override
  Future<Map<String, dynamic>> attendance(
    String classroom,
    String attempt,
    String deviceChallenge, {
    required bool preflight,
  }) async {
    calls.add('$classroom:$attempt:$deviceChallenge:$preflight');
    if (error != null) throw error!;
    return {
      'result': code == 'CLASSROOM_WIFI_APPROVED' ? 'PASS' : 'FAIL',
      'reason_code': code,
      'message': 'Server: $code',
      'classroom_wifi_proof_id': 'fresh-${calls.length}',
    };
  }
}

void main() {
  test(
    'required preflight and each liveness frame get distinct fresh Wi-Fi receipts',
    () async {
      final f = AttendanceFixture()..classroomRequired = true;
      await f.client.login('TEST001', 'test-password');
      final wifi = AttendanceWifi();
      final devices = AttendanceDeviceAuthorization(
        client: f.client,
        keys: f.keys,
        now: () => f.now,
        classroomWifi: wifi,
      );
      await devices.preflight('attempt');
      final a = await devices.proof('attempt');
      final b = await devices.proof('attempt');
      expect(wifi.calls.length, 3);
      expect(wifi.calls.first.endsWith(':true'), true);
      expect(a['device_challenge_id'], b['device_challenge_id']);
      expect(a['classroom_wifi_proof_id'], isNot(b['classroom_wifi_proof_id']));
      expect(f.keys.creates, 0);
    },
  );
  for (final code in [
    'WIFI_BSSID_MISMATCH',
    'WIFI_PERMISSION_REQUIRED',
    'WIFI_UNAVAILABLE',
    'WIFI_EVIDENCE_STALE',
    'NO_ENABLED_CLASSROOM_POLICY',
    'WIFI_EVIDENCE_REPLAYED',
  ]) {
    test('required Wi-Fi $code stops liveness upload and preflight', () async {
      final f = AttendanceFixture()..classroomRequired = true;
      await f.client.login('TEST001', 'test-password');
      final wifi = AttendanceWifi()..code = code;
      final devices = AttendanceDeviceAuthorization(
        client: f.client,
        keys: f.keys,
        now: () => f.now,
        classroomWifi: wifi,
      );
      await expectLater(
        devices.preflight('attempt'),
        throwsA(isA<ApiException>().having((e) => e.code, 'reason', code)),
      );
      final api = AuthorizedAttendanceBiometricApi(
        client: f.client,
        devices: devices,
      );
      await expectLater(
        api.submitLivenessFrame('attempt', Uint8List.fromList([1, 2])),
        throwsA(isA<ApiException>().having((e) => e.code, 'reason', code)),
      );
      expect(f.frames, 0);
    });
  }
  test(
    'unreachable Wi-Fi service stops upload without claiming mismatch',
    () async {
      final f = AttendanceFixture()..classroomRequired = true;
      await f.client.login('TEST001', 'test-password');
      final wifi = AttendanceWifi()
        ..error = const ApiException('unreachable', 0, 'NETWORK_ERROR');
      final devices = AttendanceDeviceAuthorization(
        client: f.client,
        keys: f.keys,
        now: () => f.now,
        classroomWifi: wifi,
      );
      await expectLater(
        devices.proof('attempt'),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'NETWORK_ERROR'),
        ),
      );
      expect(f.frames, 0);
    },
  );
  test(
    'unconfigured historical session never requires location permission or Wi-Fi API',
    () async {
      final f = AttendanceFixture();
      await f.client.login('TEST001', 'test-password');
      final wifi = AttendanceWifi();
      final devices = AttendanceDeviceAuthorization(
        client: f.client,
        keys: f.keys,
        now: () => f.now,
        classroomWifi: wifi,
      );
      await devices.preflight('attempt');
      await devices.proof('attempt');
      expect(wifi.calls, isEmpty);
    },
  );
}
