import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/networks/services/wifi_diagnostics.dart';
import 'package:frontend/modules/networks/services/classroom_wifi_api.dart';
import 'package:frontend/modules/networks/widgets/classroom_wifi_card.dart';

class Keys extends DeviceKeyStore {
  String? signed;
  bool missing = false;
  @override
  Future<Map<String, dynamic>?> getPublicKey(String studentId) async =>
      missing ? null : {'public_key_fingerprint': 'a' * 64};
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String studentId) =>
      throw StateError('Must never generate a key');
  @override
  Future<String> sign(String studentId, String payload) async {
    signed = payload;
    return 'fixture-signature';
  }
}

class Wifi extends WifiDiagnostics {
  int reads = 0;
  String permission = 'PRECISE_GRANTED';
  @override
  Future<WifiReading> read() async {
    reads++;
    return WifiReading.fromMap({
      'status': 'AVAILABLE',
      'connection_type': 'WIFI',
      'permission_status': permission,
      'wifi_enabled': true,
      'wifi_connected': true,
      'location_enabled': true,
      'ssid': 'Home',
      'bssid': 'd8:42:a1:9e:de:2f',
      'rssi_dbm': -46,
      'observed_at_ms': DateTime.now().millisecondsSinceEpoch,
    });
  }
}

class Fixture {
  final keys = Keys();
  final wifi = Wifi();
  String code = 'CLASSROOM_WIFI_APPROVED';
  Object? error;
  bool mismatch = false, expire = false;
  bool attendanceMode = false;
  int confirmations = 0;
  late final client = ApiClient(
    client: MockClient((r) async {
      if (r.url.path == '/login') {
        return http.Response(
          jsonEncode({
            'access_token': 'fixture',
            'student': {'student_id': 'TEST001'},
          }),
          200,
        );
      }
      if (r.url.path == '/logout') return http.Response('{}', 200);
      if (error != null) throw error!;
      expect(r.headers['Authorization'], 'Bearer fixture');
      if (r.url.path.endsWith('/classrooms')) {
        return http.Response(
          jsonEncode({
            'success': true,
            'simulation_only': true,
            'classrooms': [
              {'classroom_id': 'A', 'name': 'Classroom A'},
              {'classroom_id': 'B', 'name': 'Classroom B'},
            ],
          }),
          200,
        );
      }
      if (r.url.path.endsWith('/challenges') ||
          r.url.path.endsWith('/attendance-challenges')) {
        expect(wifi.reads, 0);
        if (attendanceMode) {
          expect(jsonDecode(r.body), {
            'attendance_challenge_id': 'attempt',
            'device_challenge_id': 'device-nonce',
            'preflight': false,
          });
        }
        return http.Response(
          jsonEncode({
            'success': true,
            'challenge_id': 'c' * 43,
            'operation': attendanceMode
                ? 'attendance_classroom_final'
                : ClassroomWifiApi.operation,
            'classroom_id': 'A',
            'device_id': 'device',
            'public_key_fingerprint': (mismatch ? 'b' : 'a') * 64,
            'signing_payload': base64Encode(utf8.encode('server-nonce')),
            'expires_at': DateTime.now()
                .add(Duration(seconds: expire ? -1 : 45))
                .toUtc()
                .toIso8601String(),
          }),
          201,
        );
      }
      confirmations++;
      final body = jsonDecode(r.body) as Map;
      final evidenceText = utf8.decode(
        base64Decode(body['evidence_payload'] as String),
      );
      expect(
        utf8.decode(base64Decode(keys.signed!)),
        'server-nonce\n$evidenceText',
      );
      expect(
        (jsonDecode(evidenceText) as Map)['permission_status'],
        wifi.permission,
      );
      expect(body.keys.toSet(), {
        'challenge_id',
        'evidence_payload',
        'signature',
      });
      return http.Response(
        jsonEncode({
          ...verdict(code),
          if (attendanceMode) 'operation': 'attendance_classroom_final',
        }),
        200,
      );
    }),
  );
  late final api = ClassroomWifiApi(client: client, keys: keys, wifi: wifi);
  Future<void> login() => client.login('TEST001', 'fixture-only');
}

Map<String, dynamic> verdict(String code) => {
  'success': true,
  'result': code == 'CLASSROOM_WIFI_APPROVED' ? 'PASS' : 'FAIL',
  'reason_code': code,
  'message': 'Server reason: $code',
  'verification_id': 1,
  'operation': ClassroomWifiApi.operation,
  'device_id': 'device',
  'classroom_id': 'A',
  'matched_policy_id': code == 'CLASSROOM_WIFI_APPROVED' ? 'home' : null,
  'verified_at': DateTime.now().toUtc().toIso8601String(),
  'evidence_source': 'CLIENT_REPORTED_ANDROID_WIFI',
  'attendance_authorized': false,
};

class ScreenApi extends ClassroomWifiApi {
  String code = 'CLASSROOM_WIFI_APPROVED';
  Object? error;
  final calls = <String>[];
  @override
  Future<List<Map<String, dynamic>>> classrooms() async => [
    {'classroom_id': 'A', 'name': 'Classroom A'},
    {'classroom_id': 'B', 'name': 'Classroom B'},
  ];
  @override
  Future<Map<String, dynamic>> verify(String classroom) async {
    calls.add(classroom);
    if (error != null) throw error!;
    return verdict(code);
  }
}

void main() {
  test(
    'attendance protocol binds actual nonce endpoint and returns proof ID',
    () async {
      final f = Fixture()..attendanceMode = true;
      await f.login();
      final response = await f.api.attendance(
        'A',
        'attempt',
        'device-nonce',
        preflight: false,
      );
      expect(response['result'], 'PASS');
      expect(response['classroom_wifi_proof_id'], 'c' * 43);
      expect(f.wifi.reads, 1);
      expect(f.confirmations, 1);
    },
  );
  test(
    'fresh reading follows nonce, exact signed bytes and no key generation',
    () async {
      final f = Fixture();
      await f.login();
      final r = await f.api.verify('A');
      expect(r['result'], 'PASS');
      expect(r['attendance_authorized'], false);
      expect(f.wifi.reads, 1);
      expect(f.confirmations, 1);
    },
  );
  for (final code in [
    'WIFI_BSSID_MISMATCH',
    'WIFI_SSID_MISMATCH',
    'WIFI_PERMISSION_REQUIRED',
    'WIFI_EVIDENCE_STALE',
    'NO_ENABLED_CLASSROOM_POLICY',
    'WIFI_UNAVAILABLE',
  ]) {
    test('backend reason preserved: $code', () async {
      final f = Fixture()..code = code;
      await f.login();
      final r = await f.api.verify('A');
      expect(r['result'], 'FAIL');
      expect(r['reason_code'], code);
    });
  }
  test(
    'missing key, wrong fingerprint and expired challenge never submit evidence',
    () async {
      for (final mode in ['missing', 'mismatch', 'expired']) {
        final f = Fixture();
        f.keys.missing = mode == 'missing';
        f.mismatch = mode == 'mismatch';
        f.expire = mode == 'expired';
        await f.login();
        await expectLater(f.api.verify('A'), throwsA(anything));
        expect(f.confirmations, 0);
        expect(f.wifi.reads, 0);
      }
    },
  );
  test('timeout and offline are not classroom mismatch', () async {
    for (final error in [
      TimeoutException('fixture'),
      http.ClientException('fixture'),
    ]) {
      final f = Fixture()..error = error;
      await f.login();
      await expectLater(
        f.api.verify('A'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            isNot('WIFI_BSSID_MISMATCH'),
          ),
        ),
      );
      expect(f.confirmations, 0);
    }
  });
  test('changed session fails closed before signing', () async {
    final f = Fixture();
    await f.login();
    await f.client.logout();
    await expectLater(
      f.api.verify('A'),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'SESSION_CHANGED'),
      ),
    );
    expect(f.keys.signed, isNull);
  });
  for (final size in [const Size(390, 844), const Size(1024, 600)]) {
    testWidgets('PASS, FAIL, transport failure and selection at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ScreenApi();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(child: ClassroomWifiCard(api: api)),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Refresh / Verify classroom'));
      await tester.tap(find.text('Refresh / Verify classroom'));
      await tester.pumpAndSettle();
      expect(find.text('Classroom Wi-Fi verification: PASS'), findsOneWidget);
      api.code = 'WIFI_BSSID_MISMATCH';
      await tester.ensureVisible(find.text('Refresh / Verify classroom'));
      await tester.tap(find.text('Refresh / Verify classroom'));
      await tester.pumpAndSettle();
      expect(find.text('Classroom Wi-Fi verification: FAIL'), findsOneWidget);
      expect(find.text('Reason: WIFI_BSSID_MISMATCH'), findsOneWidget);
      api.error = const ApiException('unreachable', 0, 'NETWORK_ERROR');
      await tester.ensureVisible(find.text('Refresh / Verify classroom'));
      await tester.tap(find.text('Refresh / Verify classroom'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('No classroom policy result was confirmed'),
        findsOneWidget,
      );
      await tester.ensureVisible(find.byType(DropdownButtonFormField<String>));
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Classroom B').last);
      await tester.pumpAndSettle();
      expect(find.text('Classroom Wi-Fi verification: FAIL'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }
}
