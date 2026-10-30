import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/modules/devices/services/device_api.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/devices/services/device_verification_service.dart';
import 'package:frontend/modules/devices/screens/my_device_screen.dart';
import 'package:frontend/services/api_client.dart';

class VerificationKeys extends DeviceKeyStore {
  int created = 0, signed = 0;
  bool missing = false, mismatch = false, unavailable = false;
  Completer<String>? pending;
  final started = Completer<void>();
  @override
  Future<Map<String, dynamic>?> getPublicKey(String studentId) async => missing
      ? null
      : {'public_key_fingerprint': mismatch ? 'wrong' : 'fingerprint'};
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String studentId) async {
    created++;
    throw StateError('Verification must never generate keys');
  }

  @override
  Future<String> sign(String studentId, String payload) async {
    signed++;
    if (!started.isCompleted) started.complete();
    if (unavailable) {
      throw PlatformException(
        code: 'KEYSTORE_UNAVAILABLE',
        message: 'Keystore unavailable',
      );
    }
    return pending == null ? 'signature' : pending!.future;
  }
}

class VerificationFixture {
  int issued = 0, confirmed = 0, reported = 0;
  int? denialStatus;
  String denialCode = 'INVALID_DEVICE_SIGNATURE';
  bool unreachable = false, reportFails = false, badResponse = false;
  final keys = VerificationKeys();
  late final ApiClient client = ApiClient(
    client: MockClient((request) async {
      if (request.url.path == '/login') {
        final id = (jsonDecode(request.body) as Map)['student_id'];
        return http.Response(
          jsonEncode({
            'access_token': 'token-$id',
            'student': {'student_id': id},
          }),
          200,
        );
      }
      expect(request.headers['Authorization'], startsWith('Bearer token-'));
      final body = jsonDecode(request.body) as Map;
      if (request.url.path.endsWith('verification-challenges')) {
        issued++;
        if (unreachable) throw http.ClientException('Offline');
        expect(body, {'operation': 'device_status'});
        return http.Response(
          jsonEncode({
            'success': true,
            'challenge_id': 'challenge-$issued',
            'device_id': 'device-1',
            'operation': 'device_status',
            'public_key_fingerprint': 'fingerprint',
            'algorithm': 'ECDSA_P256_SHA256',
            'signature_encoding': 'base64-DER',
            'signing_payload': 'payload',
          }),
          201,
        );
      }
      if (request.url.path.endsWith('verification-failures')) {
        reported++;
        expect(
          body['reason_code'],
          isIn([
            'LOCAL_KEY_MISSING',
            'LOCAL_KEY_MISMATCH',
            'KEYSTORE_UNAVAILABLE',
          ]),
        );
        if (reportFails) throw http.ClientException('Offline');
        return http.Response('{"success":true,"result":"FAIL"}', 200);
      }
      confirmed++;
      expect(body.keys.toSet(), {'challenge_id', 'operation', 'signature'});
      expect(body['signature'], 'signature');
      if (denialStatus != null) {
        return http.Response(
          jsonEncode({
            'success': false,
            'code': denialCode,
            'message': 'Device check denied',
          }),
          denialStatus!,
        );
      }
      return http.Response(
        jsonEncode({
          'success': true,
          'result': badResponse ? 'FAIL' : 'PASS',
          'verification_id': confirmed,
          'challenge_id': body['challenge_id'],
          'device_id': 'device-1',
          'operation': 'device_status',
          'verified_at': '2026-10-30T12:00:00+08:00',
          'attendance_authorized': false,
        }),
        200,
      );
    }),
  );
  DeviceVerificationService get service =>
      DeviceVerificationService(client: client, keys: keys);
  Future<void> login([String id = 'TEST001']) => client.login(id, 'password');
}

class StatusDevices extends DeviceApi {
  bool registered = true;
  @override
  Future<Map<String, dynamic>?> current() async => registered
      ? {
          'device_id': 'device-1',
          'device_name': 'Samsung',
          'device_model': 'SM-A346E',
          'status': 'ACTIVE',
          'registered_at': '2026-10-30T12:00:00+08:00',
        }
      : null;
}

class StatusVerification extends DeviceVerificationService {
  int calls = 0;
  bool fail = false;
  @override
  Future<DeviceVerificationResult> verify({
    String operation = 'device_status',
  }) async {
    calls++;
    if (fail) {
      throw const DeviceVerificationException(
        'LOCAL_KEY_MISSING',
        'Registered key is missing',
      );
    }
    return DeviceVerificationResult(
      verificationId: calls,
      challengeId: 'challenge-$calls',
      deviceId: 'device-1',
      operation: operation,
      verifiedAt: DateTime.parse('2026-10-30T12:00:00+08:00'),
    );
  }
}

Matcher failureCode(String code) => isA<DeviceVerificationException>().having(
  (error) => error.code,
  'code',
  code,
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'Automatic service signs a new challenge each time with the existing key',
    () async {
      final fixture = VerificationFixture();
      await fixture.login();
      final service = fixture.service;
      final first = await service.verify();
      final second = await service.verify();
      expect(first.challengeId, isNot(second.challengeId));
      expect(fixture.issued, 2);
      expect(fixture.confirmed, 2);
      expect(fixture.keys.signed, 2);
      expect(fixture.keys.created, 0);
    },
  );

  test('Concurrent calls each use fresh proof and never cache PASS', () async {
    final fixture = VerificationFixture();
    await fixture.login();
    final result = await Future.wait([
      fixture.service.verify(),
      fixture.service.verify(),
    ]);
    expect(fixture.issued, 2);
    expect(fixture.confirmed, 2);
    expect(result.length, 2);
    expect(fixture.keys.created, 0);
  });

  test(
    'Missing local key reports FAIL without signing or generating a key',
    () async {
      final fixture = VerificationFixture();
      await fixture.login();
      fixture.keys.missing = true;
      await expectLater(
        fixture.service.verify(),
        throwsA(failureCode('LOCAL_KEY_MISSING')),
      );
      expect(fixture.reported, 1);
      expect(fixture.confirmed, 0);
      expect(fixture.keys.created, 0);
      expect(fixture.keys.signed, 0);
    },
  );

  test('Wrong local key reports a mismatch without replacement', () async {
    final fixture = VerificationFixture();
    await fixture.login();
    fixture.keys.mismatch = true;
    await expectLater(
      fixture.service.verify(),
      throwsA(failureCode('LOCAL_KEY_MISMATCH')),
    );
    expect(fixture.reported, 1);
    expect(fixture.keys.created, 0);
    expect(fixture.confirmed, 0);
  });

  test(
    'Keystore failures preserve diagnostics if reporting is offline',
    () async {
      final fixture = VerificationFixture();
      await fixture.login();
      fixture.keys.unavailable = true;
      fixture.reportFails = true;
      await expectLater(
        fixture.service.verify(),
        throwsA(failureCode('KEYSTORE_UNAVAILABLE')),
      );
      expect(fixture.reported, 1);
      expect(fixture.confirmed, 0);
    },
  );

  test(
    'Backend invalid signature and expiry are not retried or converted to PASS',
    () async {
      for (final denial in [
        (403, 'INVALID_DEVICE_SIGNATURE'),
        (410, 'VERIFICATION_EXPIRED'),
        (409, 'VERIFICATION_REPLAYED'),
      ]) {
        final fixture = VerificationFixture();
        await fixture.login();
        fixture.denialStatus = denial.$1;
        fixture.denialCode = denial.$2;
        await expectLater(
          fixture.service.verify(),
          throwsA(failureCode(denial.$2)),
        );
        expect(fixture.issued, 1);
        expect(fixture.confirmed, 1);
      }
    },
  );

  test('Offline challenge fails clearly and never produces PASS', () async {
    final fixture = VerificationFixture();
    await fixture.login();
    fixture.unreachable = true;
    await expectLater(
      fixture.service.verify(),
      throwsA(failureCode('API_FAILURE')),
    );
    expect(fixture.confirmed, 0);
    expect(fixture.keys.signed, 0);
  });

  test('No login means no challenge or native calls', () async {
    final fixture = VerificationFixture();
    await expectLater(
      fixture.service.verify(),
      throwsA(failureCode('SIGN_IN_REQUIRED')),
    );
    expect(fixture.issued, 0);
    expect(fixture.keys.created, 0);
  });

  test(
    'Changing login while signing cannot submit proof under a new session',
    () async {
      final fixture = VerificationFixture();
      await fixture.login();
      fixture.keys.pending = Completer<String>();
      final future = fixture.service.verify();
      final assertion = expectLater(
        future,
        throwsA(failureCode('SESSION_CHANGED')),
      );
      await fixture.keys.started.future;
      await fixture.login(
        'TEST001',
      ); // Even a new login for the same account is different.
      fixture.keys.pending!.complete('signature');
      await assertion;
      expect(fixture.confirmed, 0);
      expect(fixture.reported, 0);
    },
  );

  test('A response without server PASS cannot be accepted', () async {
    final fixture = VerificationFixture();
    await fixture.login();
    fixture.badResponse = true;
    await expectLater(
      fixture.service.verify(),
      throwsA(failureCode('INVALID_RESPONSE')),
    );
  });

  testWidgets('My Device verifies on opening and has no manual verify button', (
    tester,
  ) async {
    final service = StatusVerification();
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(
          api: StatusDevices(),
          verificationService: service,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(service.calls, 1);
    expect(
      find.textContaining('Automatic device verification: PASS'),
      findsOneWidget,
    );
    expect(find.text('Status: ACTIVE'), findsOneWidget);
    expect(find.byType(FilledButton), findsNothing);
    expect(find.byType(OutlinedButton), findsNothing);
    expect(find.textContaining('Verify This Device'), findsNothing);
  });

  testWidgets('Resuming requests fresh verification automatically', (
    tester,
  ) async {
    final service = StatusVerification();
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(
          api: StatusDevices(),
          verificationService: service,
        ),
      ),
    );
    await tester.pumpAndSettle();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(service.calls, 2);
  });

  testWidgets('Failures are visible without generating a verification button', (
    tester,
  ) async {
    final service = StatusVerification()..fail = true;
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(
          api: StatusDevices(),
          verificationService: service,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Registered key is missing'), findsOneWidget);
    expect(find.textContaining('verification: PASS'), findsNothing);
    expect(find.text('Verify This Device'), findsNothing);
  });

  testWidgets('Unregistered status offers enrollment navigation only', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(
          api: StatusDevices()..registered = false,
          verificationService: StatusVerification()..fail = true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Open device registration'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect(find.text('Register this device'), findsNothing);
  });
}
