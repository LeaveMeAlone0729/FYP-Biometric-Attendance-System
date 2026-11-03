import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/pending_device_service.dart';
import 'package:frontend/modules/devices/services/device_activation_service.dart';
import 'package:frontend/modules/devices/screens/pending_device_screen.dart';
import 'package:frontend/modules/devices/screens/my_device_screen.dart';
import 'package:frontend/modules/devices/widgets/device_biometric_completion.dart';
import 'package:frontend/modules/devices/services/device_activation_state.dart';
import 'pending_device_test.dart' show CandidateKeys, candidate;
import 'device_activation_service_test.dart' show ActivationFixture;
import 'device_verification_test.dart'
    show TwoStatusDevices, StatusVerification;

const target = {
  'device_id': 'old-device',
  'public_key_fingerprint': 'old-fingerprint',
  'slot_number': 1,
  'device_name': 'Old phone',
};
Map<String, dynamic> replacement([String status = 'KEY_PROVEN']) => {
  ...candidate(status),
  'operation': 'replace_device',
  'slot_number': 1,
  'replaced_device_id': 'old-device',
  'replaced_device_fingerprint': 'old-fingerprint',
};

class ReplacementActivation extends ActivationFixture {
  @override
  Map<String, dynamic> get binding => {
    ...super.binding,
    'operation': 'replace_device',
    'slot_number': 1,
    'replaced_device_id': 'old-device',
    'replaced_device_fingerprint': 'old-fingerprint',
  };
  @override
  Map<String, dynamic> get device => {...super.device, 'slot_number': 1};
}

class ReplacementPreparation extends PendingDeviceService {
  Map<String, dynamic>? saved = replacement();
  int cancelled = 0;
  @override
  Future<Map<String, dynamic>?> current() async => saved;
  @override
  Future<Map<String, dynamic>> cancel(String id) async {
    cancelled++;
    return saved = replacement('CANCELLED');
  }
}

void main() {
  testWidgets(
    'Completed replacement checks show PASS while preserving old registration',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final state = DeviceActivationState.fromBiometricResult({
        'stage': 'COMPLETED_UNTRUSTED',
        'complete': true,
        'face_verified': true,
        'liveness_verified': true,
        'operation': 'replace_device',
        'slot_number': 1,
        'result_classification': 'UNTRUSTED_TEST_RESULT',
        'trusted': false,
        'consumable': false,
        'activation_eligible': false,
        'activation_enabled': false,
      });
      await tester.pumpWidget(
        MaterialApp(
          home: DeviceBiometricCompletion(
            replacement: true,
            activationState: state,
            onBack: () {},
          ),
        ),
      );
      expect(find.text('Face recognition: PASS'), findsOneWidget);
      expect(find.text('Liveness detection: PASS'), findsOneWidget);
      expect(find.text('Device key verification: PASS'), findsOneWidget);
      expect(find.textContaining('old device remains ACTIVE'), findsOneWidget);
      expect(find.text('Registration status: NOT ACTIVE'), findsOneWidget);
      expect(find.text('Device activation: UNAVAILABLE'), findsOneWidget);
      expect(find.text('Activate device'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  test(
    'Expired request for another operation does not block replacement after restart',
    () async {
      final keys = CandidateKeys()..exists = true;
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path == '/login') {
            return http.Response(
              jsonEncode({
                'access_token': 'token',
                'student': {'student_id': 'TEST001'},
              }),
              200,
            );
          }
          return http.Response(
            jsonEncode({'pending': candidate('EXPIRED')}),
            200,
          );
        }),
      );
      await client.login('TEST001', 'password');
      expect(
        await PendingDeviceService(
          client: client,
          keys: keys,
          replacementTarget: target,
        ).current(),
        isNull,
      );
      expect(keys.created, 0);
      expect(keys.signed, 0);
    },
  );

  test(
    'Replacement preparation recovers retained key without creating another key',
    () async {
      final keys = CandidateKeys()..exists = true;
      Map<String, dynamic>? pending;
      var creates = 0;
      final client = ApiClient(
        client: MockClient((request) async {
          http.Response response(Object data, int status) =>
              http.Response(jsonEncode(data), status);
          if (request.url.path == '/login') {
            return response({
              'access_token': 'token',
              'student': {'student_id': 'TEST001'},
            }, 200);
          }
          expect(request.headers['Authorization'], 'Bearer token');
          if (request.url.path == '/api/v1/devices') {
            return response({
              'devices': [target],
              'pending_enrollment_available': false,
            }, 200);
          }
          if (request.url.path.endsWith('/replacements')) {
            creates++;
            expect(jsonDecode(request.body)['old_device_id'], 'old-device');
            pending = replacement('CHALLENGE_ISSUED');
            return response(pending!, 201);
          }
          if (request.url.path.endsWith('/proof')) {
            pending = replacement();
            return response(pending!, 200);
          }
          if (request.url.path.endsWith('/current')) {
            return response({'pending': pending}, 200);
          }
          throw StateError('Unexpected endpoint');
        }),
      );
      await client.login('TEST001', 'password');
      final service = PendingDeviceService(
        client: client,
        keys: keys,
        replacementTarget: target,
      );
      expect(
        (await service.prepare('Replacement phone'))['status'],
        'KEY_PROVEN',
      );
      final restarted = PendingDeviceService(
        client: client,
        keys: keys,
        replacementTarget: target,
      );
      expect((await restarted.current())!['replaced_device_id'], 'old-device');
      expect(creates, 1);
      expect(keys.created, 0);
      expect(keys.signed, 1);
    },
  );
  test(
    'Replacement activation signs exact target and recovers lost confirmation',
    () async {
      final f = ReplacementActivation()..lostResponse = true;
      await f.login();
      final service = DeviceActivationService(
        client: f.client,
        keys: f.keys,
        operation: 'replace_device',
        slotNumber: 1,
        replacedDeviceId: 'old-device',
        replacedDeviceFingerprint: 'old-fingerprint',
      );
      expect((await service.activate('pending'))['status'], 'ACTIVE');
      expect(f.confirms, 1);
      expect(f.keys.signs, 1);
      expect(f.keys.created, 0);
    },
  );
  test('Replacement rejects changed target before signing', () async {
    final f = ReplacementActivation();
    await f.login();
    final service = DeviceActivationService(
      client: f.client,
      keys: f.keys,
      operation: 'replace_device',
      slotNumber: 1,
      replacedDeviceId: 'different-old-device',
      replacedDeviceFingerprint: 'old-fingerprint',
    );
    await expectLater(
      service.activate('pending'),
      throwsA(isA<ApiException>()),
    );
    expect(f.keys.signs, 0);
    expect(f.confirms, 0);
  });
  test(
    'Unavailable trusted replacement provider never signs activation',
    () async {
      final f = ReplacementActivation()..unavailable = true;
      await f.login();
      final service = DeviceActivationService(
        client: f.client,
        keys: f.keys,
        operation: 'replace_device',
        slotNumber: 1,
        replacedDeviceId: 'old-device',
        replacedDeviceFingerprint: 'old-fingerprint',
      );
      await expectLater(
        service.activate('pending'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'APPROVAL_UNAVAILABLE',
          ),
        ),
      );
      expect(f.keys.signs, 0);
      expect(f.confirms, 0);
    },
  );
  for (final size in [const Size(412, 915), const Size(1280, 800)]) {
    testWidgets('Replacement restart and cancellation layout $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final service = ReplacementPreparation();
      await tester.pumpWidget(
        MaterialApp(
          home: PendingDeviceScreen(
            service: service,
            replacementTarget: target,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Replace Slot 1 device'), findsOneWidget);
      expect(find.text('Device key verified successfully'), findsOneWidget);
      expect(find.textContaining('old device remains ACTIVE'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Cancel pending request'),
        200,
        scrollable: find
            .descendant(
              of: find.byType(ListView),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      await tester.tap(find.text('Cancel pending request'));
      await tester.pumpAndSettle();
      expect(service.cancelled, 1);
      await tester.scrollUntilVisible(
        find.text('Last server status: CANCELLED'),
        -100,
        scrollable: find
            .descendant(
              of: find.byType(ListView),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      expect(find.text('Last server status: CANCELLED'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets(
    'My Device offers replacement for either occupied slot without manual verification',
    (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: MyDeviceScreen(
            api: TwoStatusDevices(),
            verificationService: StatusVerification(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Replace Slot 1 device'), findsOneWidget);
      expect(find.text('Replace Slot 2 device'), findsOneWidget);
      expect(find.text('Verify This Device'), findsNothing);
    },
  );
}
