import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/screens/attendance_flow_screen.dart';
import 'package:frontend/modules/networks/screens/network_ble_test_screen.dart';
import 'package:frontend/modules/networks/services/network_ble_test_api.dart';
import 'package:frontend/modules/networks/services/classroom_ble_api.dart';
import 'package:frontend/modules/networks/services/classroom_wifi_api.dart';
import 'package:frontend/modules/networks/services/wifi_diagnostics.dart';
import 'classroom_ble_test.dart' show Keys, Scanner, policy;

const testId = 'nbt.7.abcdefghijklmnopqrstuvwx';

class SigningKeys extends Keys {
  final payloads = <String>[];
  @override
  Future<String> sign(String student, String payload) async {
    payloads.add(utf8.decode(base64Decode(payload)));
    return super.sign(student, payload);
  }
}

class Wifi extends WifiDiagnostics {
  @override
  Future<WifiReading> read() async => WifiReading.fromMap({
    'status': 'AVAILABLE',
    'connection_type': 'WIFI',
    'permission_status': 'PRECISE_GRANTED',
    'wifi_enabled': true,
    'wifi_connected': true,
    'location_enabled': true,
    'ssid': 'Synthetic',
    'bssid': 'a8:42:a1:9e:de:2f',
    'rssi_dbm': -45,
    'observed_at_ms': DateTime.now().millisecondsSinceEpoch,
  });
}

class Fixture {
  final keys = SigningKeys();
  final scanner = Scanner();
  String reason = 'NETWORK_BLE_TEST_PASS';
  bool forgedPass = false;
  bool unreachable = false;
  final requests = <String>[];
  Map<String, dynamic> challenge(bool ble) => {
    'success': true,
    'challenge_id': (ble ? 'b' : 'w') * 43,
    'operation': ble ? ClassroomBleApi.operation : ClassroomWifiApi.operation,
    'classroom_id': 'A',
    'device_id': 'device',
    'public_key_fingerprint': 'a' * 64,
    'signing_payload': base64Encode(
      utf8.encode(
        jsonEncode({
          'diagnostic_test': true,
          'test_id': testId,
          'test_session_id': 7,
          'nonce': ble ? 'ble-nonce' : 'wifi-nonce',
        }),
      ),
    ),
    if (ble) 'approved_policies': [policy()],
  };
  Map<String, dynamic> outcome() {
    final passed = reason == 'NETWORK_BLE_TEST_PASS';
    return {
      'success': true,
      'diagnostic_test': true,
      'attendance_authorized': false,
      'test_id': testId,
      'session_id': 7,
      'classroom_id': 'A',
      'test_result': passed || forgedPass ? 'PASS' : 'FAIL',
      'reason_code': reason,
      'network': {'result': 'PASS', 'reason_code': 'NETWORK_AUTHORIZED'},
      'wifi': {
        'result': reason == 'WIFI_BSSID_MISMATCH' ? 'FAIL' : 'PASS',
        'reason_code': reason == 'WIFI_BSSID_MISMATCH'
            ? reason
            : 'CLASSROOM_WIFI_APPROVED',
      },
      'ble': {
        'result': passed ? 'PASS' : 'FAIL',
        'reason_code': passed ? 'BLE_APPROVED' : reason,
      },
    };
  }

  late final client = ApiClient(
    client: MockClient((request) async {
      requests.add(request.url.path);
      http.Response response(Object body) =>
          http.Response(jsonEncode(body), 200);
      if (request.url.path == '/login') {
        return response({
          'access_token': 'fixture',
          'student': {'student_id': 'TEST001'},
        });
      }
      expect(request.url.path.startsWith(NetworkBleTestApi.path), true);
      if (unreachable) throw http.ClientException('offline');
      if (request.url.path.endsWith('/sessions')) {
        return response({
          'success': true,
          'diagnostic_test': true,
          'sessions': [
            {'session_id': 7, 'classroom_id': 'A', 'venue': 'Test classroom'},
          ],
        });
      }
      if (request.url.path.endsWith('/start')) {
        expect(jsonDecode(request.body), {
          'session_id': 7,
          'pin': '123456',
          'public_key_fingerprint': 'a' * 64,
        });
        return response({
          'success': true,
          'diagnostic_test': true,
          'attendance_authorized': false,
          'test_id': testId,
          'session_id': 7,
          'classroom_id': 'A',
          'wifi': challenge(false),
          'ble': challenge(true),
        });
      }
      final body = jsonDecode(request.body) as Map;
      expect(body.keys.toSet(), {'test_id', 'wifi', 'ble'});
      for (final (stage, ble) in [('wifi', false), ('ble', true)]) {
        final evidence = utf8.decode(
          base64Decode(body[stage]['evidence_payload']),
        );
        final nonce = utf8.decode(
          base64Decode(challenge(ble)['signing_payload']),
        );
        expect(keys.payloads, contains('$nonce\n$evidence'));
      }
      return response(outcome());
    }),
  );
  late final api = NetworkBleTestApi(
    client: client,
    keys: keys,
    wifi: Wifi(),
    scanner: scanner,
  );
  Future<void> login() => client.login('TEST001', 'synthetic');
}

void main() {
  for (final reason in [
    'NETWORK_BLE_TEST_PASS',
    'BLE_BEACON_NOT_FOUND',
    'BLUETOOTH_OFF',
    'WIFI_BSSID_MISMATCH',
    'BLE_CHALLENGE_REPLAYED',
  ]) {
    test(
      'diagnostic preserves server result $reason and never calls attendance',
      () async {
        final f = Fixture()..reason = reason;
        await f.login();
        if (reason == 'BLUETOOTH_OFF') f.scanner.enabled = false;
        final result = await f.api.run(7, '123456');
        expect(
          result['test_result'],
          reason == 'NETWORK_BLE_TEST_PASS' ? 'PASS' : 'FAIL',
        );
        expect(result['attendance_authorized'], false);
        expect(f.keys.payloads.length, 2);
        expect(f.scanner.scans, reason == 'BLUETOOTH_OFF' ? 0 : 1);
        expect(
          f.requests.where((path) => path != '/login'),
          everyElement(startsWith(NetworkBleTestApi.path)),
        );
      },
    );
  }
  test('incomplete or forged aggregate PASS is rejected', () async {
    final f = Fixture()
      ..reason = 'BLE_BEACON_NOT_FOUND'
      ..forgedPass = true;
    await f.login();
    await expectLater(f.api.run(7, '123456'), throwsFormatException);
  });
  test('server unreachable never becomes a successful result', () async {
    final f = Fixture()..unreachable = true;
    await f.login();
    await expectLater(f.api.run(7, '123456'), throwsA(isA<ApiException>()));
    expect(f.scanner.scans, 0);
  });
  testWidgets(
    'entry is opt-in and opens a diagnostic screen without starting attendance',
    (tester) async {
      final f = Fixture();
      await f.login();
      Future<void> render() => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: AttendanceFlowScreen(client: f.client)),
        ),
      );
      await render();
      expect(find.text('Network + BLE Test'), findsNothing);
      f.client.config['network_ble_test_mode'] = true;
      await render();
      await tester.ensureVisible(find.text('Network + BLE Test'));
      await tester.tap(find.text('Network + BLE Test'));
      await tester.pumpAndSettle();
      expect(find.byType(NetworkBleTestScreen), findsOneWidget);
      expect(
        find.text(
          'Temporary diagnostic simulation. No attendance is recorded.',
        ),
        findsOneWidget,
      );
      expect(f.requests, ['/login', '${NetworkBleTestApi.path}/sessions']);
    },
  );
  for (final reason in [
    'NETWORK_BLE_TEST_PASS',
    'BLE_BEACON_NOT_FOUND',
    'BLUETOOTH_OFF',
  ]) {
    testWidgets('results screen displays server test outcome $reason', (
      tester,
    ) async {
      final f = Fixture()..reason = reason;
      await f.login();
      await tester.pumpWidget(
        MaterialApp(
          home: NetworkBleTestScreen(api: f.api, initialPin: '123456'),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Run diagnostic test'));
      await tester.pumpAndSettle();
      expect(
        find.text(
          reason == 'NETWORK_BLE_TEST_PASS' ? 'TEST PASS' : 'TEST FAIL',
        ),
        findsOneWidget,
      );
      expect(find.text('Reason: $reason'), findsOneWidget);
    });
  }
}
