import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/networks/services/ble_diagnostics.dart';
import 'package:frontend/modules/networks/services/classroom_ble_api.dart';
import 'package:frontend/modules/networks/widgets/classroom_ble_card.dart';

const uuid = '7d9a6c10-326a-4c60-9e01-1ef000000001';
const unrelated = '7d9a6c10-326a-4c60-9e01-1ef000000099';
Map<String, dynamic> policy() => {
  'policy_id': 'beacon',
  'classroom_id': 'A',
  'service_uuid': uuid,
  'label': 'Test beacon',
  'enabled': true,
  'simulation_only': true,
  'minimum_samples': 5,
  'rssi_threshold': -65,
  'max_age_seconds': 15,
};
Map<String, dynamic> result(String code) => {
  'success': true,
  'result': code == 'BLE_APPROVED'
      ? 'PASS'
      : code == 'BLE_INSUFFICIENT_SAMPLES' || code == 'BLUETOOTH_OFF'
      ? 'UNCERTAIN'
      : 'FAIL',
  'reason_code': code,
  'message': 'Server: $code',
  'operation': ClassroomBleApi.operation,
  'challenge_id': 'c' * 43,
  'classroom_id': 'A',
  'device_id': 'device',
  'verification_id': 1,
  'evidence_source': 'CLIENT_REPORTED_ANDROID_BLE',
  'attendance_authorized': false,
  'matched_policy_id': code == 'BLE_APPROVED' ? 'beacon' : null,
  'sample_count': 5,
  'median_rssi_dbm': -55.0,
  'rssi_threshold': -65,
};

class Keys extends DeviceKeyStore {
  String? signed;
  bool missing = false;
  @override
  Future<Map<String, dynamic>?> getPublicKey(String student) async =>
      missing ? null : {'public_key_fingerprint': 'a' * 64};
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String student) =>
      throw StateError('Never create a key');
  @override
  Future<String> sign(String student, String payload) async {
    signed = payload;
    return 'fixture-signature';
  }
}

class Scanner extends BleDiagnostics {
  bool enabled = true;
  int scans = 0, cancels = 0;
  String? owner;
  Completer<BleSnapshot>? waiting;
  Map<String, dynamic> metadata() => {
    'status': enabled ? 'READY' : 'BLUETOOTH_OFF',
    'supported': true,
    'bluetooth_enabled': enabled,
    'scan_permission': 'GRANTED',
    'connect_permission': 'GRANTED',
    'location_permission': 'PRECISE_GRANTED',
    'location_enabled': true,
  };
  @override
  Future<BleSnapshot> status() async => BleSnapshot.fromMap(metadata());
  @override
  Future<BleSnapshot> scan({String? requestId}) async {
    scans++;
    owner = requestId;
    if (waiting != null) return waiting!.future;
    final start = DateTime.now().millisecondsSinceEpoch;
    Map<String, dynamic> advertiser(String id) => {
      'scan_id': id == uuid ? 1 : 2,
      'name': 'private-advertised-name',
      'service_uuids': [id],
      'service_data': [],
      'manufacturer_data': [],
      'rssi_dbm': -55,
      'rssi_samples': [-55, -55, -55, -55, -55],
      'advertisement_count': 5,
      'last_seen_age_ms': 100,
      'last_seen_at_ms': start + 7900,
      'beacon_observations': [
        {
          'service_uuid': id,
          'samples': List.generate(
            5,
            (i) => {'offset_us': i * 1000000 + 100000, 'rssi_dbm': -55},
          ),
        },
      ],
    };
    return BleSnapshot.fromMap({
      ...metadata(),
      'status': 'COMPLETE',
      'scan_started_at_ms': start,
      'completed_at_ms': start + 8000,
      'scan_duration_ms': 8000,
      'devices': [advertiser(uuid), advertiser(unrelated)],
    });
  }

  @override
  Future<void> cancel({String? requestId}) async {
    cancels++;
    expect(requestId, owner);
  }
}

class Fixture {
  final keys = Keys();
  final scanner = Scanner();
  String code = 'BLE_APPROVED';
  Object? error;
  int confirms = 0;
  late final client = ApiClient(
    client: MockClient((r) async {
      http.Response answer(Object data, [int status = 200]) =>
          http.Response(jsonEncode(data), status);
      if (r.url.path == '/login') {
        return answer({
          'access_token': 'fixture',
          'student': {'student_id': 'TEST001'},
        });
      }
      if (error != null) throw error!;
      expect(r.headers['Authorization'], 'Bearer fixture');
      if (r.url.path.endsWith('/classrooms')) {
        return answer({
          'success': true,
          'simulation_only': true,
          'classrooms': [
            {
              'classroom_id': 'A',
              'name': 'Classroom A',
              'policies': [policy()],
            },
          ],
        });
      }
      if (r.url.path.endsWith('/challenges')) {
        expect(scanner.scans, 0);
        return answer({
          'success': true,
          'operation': ClassroomBleApi.operation,
          'challenge_id': 'c' * 43,
          'classroom_id': 'A',
          'device_id': 'device',
          'public_key_fingerprint': 'a' * 64,
          'signing_payload': base64Encode(utf8.encode('server-nonce')),
          'approved_policies': [policy()],
          'scan_window_ms': 8000,
          'expires_at': DateTime.now()
              .add(const Duration(seconds: 45))
              .toUtc()
              .toIso8601String(),
        }, 201);
      }
      confirms++;
      final body = jsonDecode(r.body) as Map;
      expect(body.keys.toSet(), {
        'challenge_id',
        'evidence_payload',
        'signature',
      });
      final raw = utf8.decode(base64Decode(body['evidence_payload']));
      expect(utf8.decode(base64Decode(keys.signed!)), 'server-nonce\n$raw');
      final evidence = jsonDecode(raw) as Map;
      expect(raw, isNot(contains('private-advertised-name')));
      expect(raw, isNot(contains(unrelated)));
      expect(evidence, isNot(contains('median_rssi_dbm')));
      if (scanner.enabled) {
        expect((evidence['beacons'] as List).single['samples'].length, 5);
      } else {
        expect(evidence['beacons'], isEmpty);
      }
      return answer(result(code));
    }),
  );
  late final api = ClassroomBleApi(
    client: client,
    keys: keys,
    scanner: scanner,
  );
  Future<void> login() => client.login('TEST001', 'fixture');
}

class ScreenApi extends ClassroomBleApi {
  String code = 'BLE_APPROVED';
  Object? error;
  int verifies = 0;
  @override
  Future<List<Map<String, dynamic>>> classrooms() async => [
    {
      'classroom_id': 'A',
      'name': 'Classroom A',
      'policies': [policy()],
    },
  ];
  @override
  Future<Map<String, dynamic>> verify(String classroom) async {
    verifies++;
    if (error != null) throw error!;
    return result(code);
  }

  @override
  Future<void> cancel() async {}
}

void main() {
  test(
    'nonce precedes scan, existing key signs exact filtered timestamped observations',
    () async {
      final f = Fixture();
      await f.login();
      final r = await f.api.verify('A');
      expect(r['result'], 'PASS');
      expect(f.scanner.owner, 'c' * 43);
      expect(f.scanner.scans, 1);
      expect(f.confirms, 1);
    },
  );
  test(
    'Bluetooth OFF uses signed unavailability report and never scans/enables',
    () async {
      final f = Fixture()..code = 'BLUETOOTH_OFF';
      f.scanner.enabled = false;
      await f.login();
      final r = await f.api.verify('A');
      expect(r['result'], 'UNCERTAIN');
      expect(f.scanner.scans, 0);
    },
  );
  for (final code in [
    'BLE_BEACON_NOT_FOUND',
    'BLE_SIGNAL_WEAK',
    'BLE_INSUFFICIENT_SAMPLES',
    'BLE_EVIDENCE_STALE',
    'BLE_POLICY_CHANGED',
  ]) {
    test('actual backend decision preserved: $code', () async {
      final f = Fixture()..code = code;
      await f.login();
      expect((await f.api.verify('A'))['reason_code'], code);
    });
  }
  test(
    'missing key and unreachable server cannot claim beacon rejection',
    () async {
      final f = Fixture();
      await f.login();
      f.keys.missing = true;
      await expectLater(
        f.api.verify('A'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'LOCAL_KEY_MISSING',
          ),
        ),
      );
      f.keys.missing = false;
      f.error = http.ClientException('unreachable');
      await expectLater(
        f.api.verify('A'),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'NETWORK_ERROR'),
        ),
      );
      expect(f.scanner.scans, 0);
    },
  );
  test(
    'overlap rejects and cancellation targets only the verification-owned native scan',
    () async {
      final f = Fixture();
      await f.login();
      f.scanner.waiting = Completer<BleSnapshot>();
      final first = f.api.verify('A');
      await Future<void>.delayed(const Duration(milliseconds: 10));
      await expectLater(
        f.api.verify('A'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'BLE_CHECK_IN_PROGRESS',
          ),
        ),
      );
      final expected = expectLater(
        first,
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'BLE_CHECK_CANCELLED',
          ),
        ),
      );
      await f.api.cancel();
      expect(f.scanner.cancels, 1);
      f.scanner.waiting!.complete(await Scanner().scan(requestId: 'fixture'));
      await expected;
      expect(f.confirms, 0);
    },
  );
  for (final size in [const Size(390, 844), const Size(1024, 600)]) {
    testWidgets('PASS FAIL UNCERTAIN and transport display at $size', (
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
            body: SingleChildScrollView(child: ClassroomBleCard(api: api)),
          ),
        ),
      );
      await tester.pumpAndSettle();
      for (final code in [
        'BLE_APPROVED',
        'BLE_SIGNAL_WEAK',
        'BLE_INSUFFICIENT_SAMPLES',
      ]) {
        api.code = code;
        await tester.ensureVisible(find.text('Verify classroom BLE'));
        await tester.tap(find.text('Verify classroom BLE'));
        await tester.pumpAndSettle();
        expect(
          find.text('Classroom BLE verification: ${result(code)['result']}'),
          findsOneWidget,
        );
        expect(find.text('Reason: $code'), findsOneWidget);
      }
      api.error = const ApiException('disabled', 409, 'NO_ENABLED_BLE_POLICY');
      await tester.ensureVisible(find.text('Verify classroom BLE'));
      await tester.tap(find.text('Verify classroom BLE'));
      await tester.pumpAndSettle();
      expect(find.text('Classroom BLE verification: FAIL'), findsOneWidget);
      api.error = const ApiException('unreachable', 0, 'NETWORK_ERROR');
      await tester.ensureVisible(find.text('Verify classroom BLE'));
      await tester.tap(find.text('Verify classroom BLE'));
      await tester.pumpAndSettle();
      expect(
        find.text('Classroom BLE verification: UNCERTAIN'),
        findsOneWidget,
      );
      expect(
        find.textContaining('No BLE policy decision was confirmed'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });
  }
}
