import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/devices/services/attendance_device_authorization.dart';
import 'package:frontend/modules/devices/services/authorized_attendance_biometric_api.dart';
import 'package:frontend/modules/networks/services/classroom_wifi_api.dart';
import 'package:frontend/modules/networks/services/classroom_ble_api.dart';
import 'package:frontend/screens/attendance_flow_screen.dart';
import 'package:frontend/services/api_client.dart';
import 'attendance_authorization_test.dart' show AttendanceFixture;
import 'attendance_preflight_test.dart' show enterPin;

class PendingBle extends ClassroomBleApi {
  final result = Completer<Map<String, dynamic>>();
  int calls = 0;
  int cancellations = 0;

  @override
  Future<Map<String, dynamic>> verifyAttendance(
    String classroom,
    String attempt,
    String preflightProof,
  ) {
    expect(classroom, 'A');
    expect(attempt, 'attempt');
    expect(preflightProof, isNotEmpty);
    calls++;
    return result.future;
  }

  @override
  Future<void> cancel() async => cancellations++;
}

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
  for (final (code, verdict, label) in [
    ('BLE_APPROVED', 'PASS', 'BLE verified'),
    ('BLE_BEACON_NOT_FOUND', 'FAIL', 'BLE not detected'),
    ('BLUETOOTH_OFF', 'UNCERTAIN', 'BLE unavailable'),
    ('INVALID_DEVICE_SIGNATURE', 'FAIL', 'BLE verification error'),
    ('timeout', '', 'BLE unavailable'),
    ('NO_ENABLED_BLE_POLICY', '', 'BLE not configured for this classroom'),
  ]) {
    testWidgets('Shadow BLE $code never waits before opening camera', (
      tester,
    ) async {
      final f = AttendanceFixture()..classroomRequired = true;
      await f.login();
      final ble = PendingBle();
      final devices = AttendanceDeviceAuthorization(
        client: f.client,
        keys: f.keys,
        now: () => f.now,
        classroomWifi: AttendanceWifi(),
      );
      var recorded = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttendanceFlowScreen(
              client: f.client,
              authorization: devices,
              classroomBle: ble,
              onRecorded: () => recorded++,
              cameraBuilder: (_) => Builder(
                builder: (context) => Scaffold(
                  body: TextButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Finish camera fixture'),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await enterPin(tester);
      expect(find.text('Finish camera fixture'), findsOneWidget);
      expect(find.text('Checking classroom BLE…'), findsOneWidget);
      expect(ble.calls, 1);
      if (code == 'timeout') {
        await tester.pump(const Duration(seconds: 18));
      } else if (code == 'NO_ENABLED_BLE_POLICY') {
        ble.result.completeError(
          const ApiException('No BLE policy', 409, 'NO_ENABLED_BLE_POLICY'),
        );
      } else {
        ble.result.complete({'result': verdict, 'reason_code': code});
      }
      await tester.pumpAndSettle();
      expect(find.text(label), findsOneWidget);
      await tester.tap(find.text('Finish camera fixture'));
      await tester.pumpAndSettle();
      expect(recorded, 1);
      expect(ble.calls, 1);
      expect(ble.cancellations, 1);
    });
  }
  testWidgets('No classroom Wi-Fi policy stops preflight before optional BLE', (
    tester,
  ) async {
    final f = AttendanceFixture()..classroomRequired = true;
    await f.login();
    final ble = PendingBle();
    final devices = AttendanceDeviceAuthorization(
      client: f.client,
      keys: f.keys,
      now: () => f.now,
      classroomWifi: AttendanceWifi()..code = 'NO_ENABLED_CLASSROOM_POLICY',
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AttendanceFlowScreen(
            client: f.client,
            authorization: devices,
            classroomBle: ble,
            cameraBuilder: (_) => const Text('Camera fixture opened'),
          ),
        ),
      ),
    );
    await enterPin(tester);
    expect(ble.calls, 0);
    expect(find.text('Camera fixture opened'), findsNothing);
    expect(find.text('Verification result'), findsOneWidget);
  });
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
