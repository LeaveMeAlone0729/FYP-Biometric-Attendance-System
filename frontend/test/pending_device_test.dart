import 'dart:async';
import 'dart:convert';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/devices/services/pending_device_service.dart';
import 'package:frontend/modules/devices/screens/pending_device_screen.dart';
import 'package:frontend/modules/devices/screens/device_biometric_approval_screen.dart';

Map<String, dynamic> candidate([String status = 'CHALLENGE_ISSUED']) => {
  'pending_registration_id': 'pending-1',
  'candidate_device_id': 'candidate-1',
  'public_key_fingerprint': 'candidate-fingerprint',
  'slot_number': 2,
  'operation': 'enroll_second_device',
  'status': status,
  'algorithm': 'ECDSA_P256_SHA256',
  'signature_encoding': 'base64-DER',
  'signing_payload': 'payload',
  'activation_enabled': false,
  'attendance_authorized': false,
  'expires_at': DateTime.now()
      .toUtc()
      .add(const Duration(minutes: 5))
      .toIso8601String(),
};

class CandidateKeys extends DeviceKeyStore {
  bool exists = false, registered = false;
  int created = 0, signed = 0;
  Completer<String>? waitForSignature;
  final signing = Completer<void>();
  Map<String, dynamic> get key => {
    'public_key_fingerprint': registered
        ? 'registered-fingerprint'
        : 'candidate-fingerprint',
    'public_key_spki': 'public-key',
    'device_model': 'Android tablet',
  };
  @override
  Future<Map<String, dynamic>?> getPublicKey(String id) async =>
      exists ? key : null;
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String id) async {
    created++;
    exists = true;
    return key;
  }

  @override
  Future<String> sign(String id, String payload) async {
    expect(payload, 'payload');
    signed++;
    if (!signing.isCompleted) signing.complete();
    return waitForSignature == null ? 'signature' : waitForSignature!.future;
  }
}

class PendingFixture {
  final keys = CandidateKeys();
  int begun = 0, proved = 0, approvalCalls = 0;
  bool lostResponse = false, blocked = false, expired = false;
  late final client = ApiClient(
    client: MockClient((request) async {
      final path = request.url.path;
      if (path == '/login') {
        return http.Response(
          jsonEncode({
            'access_token': 'token',
            'student': {'student_id': 'TEST001'},
          }),
          200,
        );
      }
      expect(request.headers['Authorization'], 'Bearer token');
      if (path == '/api/v1/devices') {
        return http.Response(
          jsonEncode({
            'pending_enrollment_available': !blocked,
            'devices': [
              {'public_key_fingerprint': 'registered-fingerprint'},
            ],
          }),
          200,
        );
      }
      if (path.endsWith('/pending-registrations')) {
        begun++;
        expect(jsonDecode(request.body), {
          'public_key_spki': 'public-key',
          'platform': 'android',
          'device_name': 'My tablet',
          'device_model': 'Android tablet',
        });
        return http.Response(jsonEncode(candidate()), 201);
      }
      if (path.endsWith('/proof')) {
        proved++;
        expect(jsonDecode(request.body), {'signature': 'signature'});
        if (expired) {
          return http.Response(
            jsonEncode({
              'message': 'Candidate challenge expired',
              'code': 'CHALLENGE_EXPIRED',
            }),
            410,
          );
        }
        if (lostResponse) throw http.ClientException('Response lost');
        return http.Response(jsonEncode(candidate('KEY_PROVEN')), 200);
      }
      if (path.endsWith('/pending-registrations/current')) {
        return http.Response(
          jsonEncode({'pending': candidate('KEY_PROVEN')}),
          200,
        );
      }
      if (path.endsWith('/pending-registrations/pending-1')) {
        return http.Response(
          jsonEncode(candidate(expired ? 'EXPIRED' : 'KEY_PROVEN')),
          200,
        );
      }
      if (path.endsWith('/device-approvals')) {
        approvalCalls++;
        expect(jsonDecode(request.body), {
          'pending_registration_id': 'pending-1',
        });
        return http.Response(
          jsonEncode({
            'code': 'APPROVAL_UNAVAILABLE',
            'message':
                'Trusted biometric approval is unavailable. Candidate remains inactive.',
          }),
          503,
        );
      }
      throw StateError('Unexpected endpoint: $path');
    }),
  );
  late final service = PendingDeviceService(client: client, keys: keys);
  Future<void> login() => client.login('TEST001', 'password');
}

class ScreenPreparation extends PendingDeviceService {
  int prepared = 0, approvals = 0;
  String? status;
  bool loadFails = false;
  Map<String, dynamic>? saved;
  @override
  Future<Map<String, dynamic>?> current() async {
    if (loadFails) {
      throw const ApiException('Cannot load pending registration.');
    }
    return saved ?? (status == null ? null : candidate(status!));
  }

  @override
  Future<Map<String, dynamic>> prepare(String name) async {
    prepared++;
    saved = candidate('KEY_PROVEN');
    return saved!;
  }

  @override
  Future<void> requestApproval(String id) async {
    approvals++;
    throw const ApiException(
      'Approval unavailable.',
      503,
      'APPROVAL_UNAVAILABLE',
    );
  }
}

void largeView(WidgetTester tester) {
  tester.view.physicalSize = const Size(800, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  test(
    'Preparation signs a fresh challenge and never activates or uploads frames',
    () async {
      final f = PendingFixture();
      await f.login();
      final result = await f.service.prepare('My tablet');
      expect(result['status'], 'KEY_PROVEN');
      expect(result['activation_enabled'], false);
      expect(f.keys.created, 1);
      expect(f.keys.signed, 1);
      expect(f.proved, 1);
      await expectLater(
        f.service.requestApproval('pending-1'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'APPROVAL_UNAVAILABLE',
          ),
        ),
      );
      expect(f.approvalCalls, 1);
    },
  );
  test('An existing candidate key is reused', () async {
    final f = PendingFixture();
    await f.login();
    f.keys.exists = true;
    await f.service.prepare('My tablet');
    expect(f.keys.created, 0);
    expect(f.keys.signed, 1);
  });
  test(
    'Registered Samsung key is never created or signed for enrollment',
    () async {
      final f = PendingFixture();
      await f.login();
      f.keys
        ..exists = true
        ..registered = true;
      await expectLater(
        f.service.prepare('My tablet'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'KEY_ALREADY_REGISTERED',
          ),
        ),
      );
      expect(f.keys.created, 0);
      expect(f.keys.signed, 0);
      expect(f.begun, 0);
    },
  );
  test(
    'Lost proof response recovers status without replay or key rotation',
    () async {
      final f = PendingFixture();
      await f.login();
      f.lostResponse = true;
      expect((await f.service.prepare('My tablet'))['status'], 'KEY_PROVEN');
      expect(f.proved, 1);
      expect(f.keys.created, 1);
    },
  );
  test(
    'Expiry has an actionable error and preserves the candidate key',
    () async {
      final f = PendingFixture();
      await f.login();
      f.expired = true;
      await expectLater(
        f.service.prepare('My tablet'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'CHALLENGE_EXPIRED',
          ),
        ),
      );
      expect(f.keys.exists, true);
      expect(f.proved, 1);
    },
  );
  test('Session change while signing prevents submission', () async {
    final f = PendingFixture();
    await f.login();
    f.keys.waitForSignature = Completer<String>();
    final action = f.service.prepare('My tablet');
    final assertion = expectLater(
      action,
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'SESSION_CHANGED'),
      ),
    );
    await f.keys.signing.future;
    await f.login();
    f.keys.waitForSignature!.complete('signature');
    await assertion;
    expect(f.proved, 0);
  });
  test('No session or full capacity cannot generate a key', () async {
    final f = PendingFixture();
    await expectLater(
      f.service.prepare('My tablet'),
      throwsA(isA<ApiException>()),
    );
    await f.login();
    f.blocked = true;
    await expectLater(
      f.service.prepare('My tablet'),
      throwsA(isA<ApiException>()),
    );
    expect(f.keys.created, 0);
  });
  test(
    'Reopening the service reads the retained key without generating or signing',
    () async {
      final f = PendingFixture();
      await f.login();
      f.keys.exists = true;
      for (var restart = 0; restart < 2; restart++) {
        final reopened = PendingDeviceService(client: f.client, keys: f.keys);
        expect((await reopened.current())?['status'], 'KEY_PROVEN');
      }
      expect(f.keys.created, 0);
      expect(f.keys.signed, 0);
      expect(f.begun, 0);
      expect(f.proved, 0);
    },
  );
  test(
    'Restored pending proof cannot be attributed to a different local key',
    () async {
      final f = PendingFixture();
      await f.login();
      f.keys
        ..exists = true
        ..registered = true;
      await expectLater(
        f.service.current(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'CANDIDATE_KEY_MISMATCH',
          ),
        ),
      );
      expect(f.keys.created, 0);
      expect(f.keys.signed, 0);
    },
  );
  testWidgets('Key proof succeeds once and preparation is hidden afterward', (
    tester,
  ) async {
    largeView(tester);
    final service = ScreenPreparation();
    await tester.pumpWidget(
      MaterialApp(home: PendingDeviceScreen(service: service)),
    );
    await tester.pumpAndSettle();
    expect(service.prepared, 0);
    await tester.enterText(find.byType(TextField), 'SH tablet');
    await tester.tap(find.text('Prepare and prove device key'));
    await tester.pumpAndSettle();
    expect(service.prepared, 1);
    expect(service.approvals, 0);
    expect(find.text('Device key verified successfully'), findsOneWidget);
    expect(
      find.textContaining('not yet an ACTIVE registration'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Pending registration expires:'),
      findsOneWidget,
    );
    expect(find.text('Prepare and prove device key'), findsNothing);
    expect(find.byType(TextField), findsNothing);
    expect(
      find.textContaining('Repeating it will not complete registration'),
      findsOneWidget,
    );
    expect(find.textContaining('attendance'), findsNothing);
    expect(find.textContaining('Verify This Device'), findsNothing);
  });
  testWidgets(
    'Reopened KEY_PROVEN screen restores success without preparing again',
    (tester) async {
      largeView(tester);
      final service = ScreenPreparation()..status = 'KEY_PROVEN';
      await tester.pumpWidget(
        MaterialApp(home: PendingDeviceScreen(service: service)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Device key verified successfully'), findsOneWidget);
      await tester.tap(find.text('Refresh pending status'));
      await tester.pumpAndSettle();
      expect(service.prepared, 0);
      expect(service.approvals, 0);
    },
  );
  testWidgets('Expired request offers a new request with the retained key', (
    tester,
  ) async {
    largeView(tester);
    final service = ScreenPreparation()..status = 'EXPIRED';
    await tester.pumpWidget(
      MaterialApp(home: PendingDeviceScreen(service: service)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pending registration expired'), findsOneWidget);
    expect(find.textContaining('Your local key is retained'), findsOneWidget);
    expect(find.text('Start a new pending request'), findsOneWidget);
    expect(find.text('Device key verified successfully'), findsNothing);
    expect(service.prepared, 0);
  });
  testWidgets(
    'Failed proof shows failure rather than key verification success',
    (tester) async {
      largeView(tester);
      final service = ScreenPreparation()..status = 'FAILED';
      await tester.pumpWidget(
        MaterialApp(home: PendingDeviceScreen(service: service)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Device key proof failed'), findsOneWidget);
      expect(find.text('Start a new pending request'), findsOneWidget);
      expect(find.text('Device key verified successfully'), findsNothing);
    },
  );
  testWidgets('Incomplete challenge offers only key preparation', (
    tester,
  ) async {
    largeView(tester);
    final service = ScreenPreparation()..status = 'CHALLENGE_ISSUED';
    await tester.pumpWidget(
      MaterialApp(home: PendingDeviceScreen(service: service)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Device key preparation is incomplete.'), findsOneWidget);
    expect(find.text('Prepare and prove device key'), findsOneWidget);
    expect(find.text('Open facial recognition and liveness'), findsNothing);
  });
  testWidgets(
    'Status failure offers refresh without enabling blind preparation',
    (tester) async {
      largeView(tester);
      final service = ScreenPreparation()..loadFails = true;
      await tester.pumpWidget(
        MaterialApp(home: PendingDeviceScreen(service: service)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Cannot load pending registration.'), findsOneWidget);
      expect(find.text('Prepare and prove device key'), findsNothing);
      service.loadFails = false;
      await tester.tap(find.text('Refresh pending status'));
      await tester.pumpAndSettle();
      expect(find.text('Prepare and prove device key'), findsOneWidget);
    },
  );
  testWidgets(
    'Biometric screen is separate and waits for explicit start before any camera or API',
    (tester) async {
      largeView(tester);
      final originalClient = ApiClient.instance;
      var requests = 0;
      ApiClient.instance = ApiClient(
        client: MockClient((request) async {
          requests++;
          throw StateError('Disabled approval screen must not call an API');
        }),
      );
      addTearDown(() => ApiClient.instance = originalClient);
      final service = ScreenPreparation()..status = 'KEY_PROVEN';
      await tester.pumpWidget(
        MaterialApp(home: PendingDeviceScreen(service: service)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Open facial recognition and liveness'));
      await tester.pumpAndSettle();
      expect(find.byType(DeviceBiometricApprovalScreen), findsOneWidget);
      expect(find.text('Start facial verification'), findsOneWidget);
      expect(find.byType(CameraPreview), findsNothing);
      final button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(button.onPressed, isNotNull);

      expect(requests, 0);
      expect(service.prepared, 0);
      expect(service.approvals, 0);
      expect(find.textContaining('attendance'), findsNothing);
    },
  );
  testWidgets('Completion return leaves preparation and returns to My Device', (
    tester,
  ) async {
    largeView(tester);
    final service = ScreenPreparation()..status = 'KEY_PROVEN';
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) => PendingDeviceScreen(service: service),
                ),
              ),
              child: const Text('My Device test route'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('My Device test route'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open facial recognition and liveness'));
    await tester.pumpAndSettle();
    expect(find.byType(DeviceBiometricApprovalScreen), findsOneWidget);
    // Exercise only the navigation result; no synthetic biometric success/API.
    Navigator.of(
      tester.element(find.byType(DeviceBiometricApprovalScreen)),
    ).pop(true);
    await tester.pumpAndSettle();
    expect(find.text('My Device test route'), findsOneWidget);
    expect(find.byType(PendingDeviceScreen), findsNothing);
  });
  testWidgets('Elapsed expiry is not displayed as a current successful proof', (
    tester,
  ) async {
    largeView(tester);
    final service = ScreenPreparation()
      ..saved = {
        ...candidate('KEY_PROVEN'),
        'expires_at': DateTime.now()
            .toUtc()
            .subtract(const Duration(minutes: 1))
            .toIso8601String(),
      };
    await tester.pumpWidget(
      MaterialApp(home: PendingDeviceScreen(service: service)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pending registration expired'), findsOneWidget);
    expect(find.text('Device key verified successfully'), findsNothing);
    expect(find.text('Open facial recognition and liveness'), findsNothing);
    expect(service.prepared, 0);
  });
  testWidgets('Preparation layout scrolls on a narrow phone without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: PendingDeviceScreen(
          service: ScreenPreparation()..status = 'KEY_PROVEN',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.scrollUntilVisible(find.text('Refresh pending status'), 200);
    expect(tester.takeException(), isNull);
  });
}
