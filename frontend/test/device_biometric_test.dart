import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/device_biometric_api.dart';
import 'package:frontend/modules/devices/screens/device_biometric_approval_screen.dart';
import 'package:frontend/modules/devices/widgets/device_biometric_completion.dart';
import 'package:frontend/modules/devices/widgets/device_biometric_feedback.dart';
import 'package:frontend/modules/devices/services/device_activation_service.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'device_activation_service_test.dart' show ActivationFixture;
import 'auto_scan_test.dart' show TestCamera, TestStopwatch, frontCamera;

http.Response jsonResponse(String body, int status) => http.Response(
  body,
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

Map<String, dynamic> result(String stage, {int valid = 0}) => {
  'success': true,
  'approval_id': 'bio-test',
  'pending_registration_id': 'pending-test',
  'candidate_device_id': 'tablet-test',
  'public_key_fingerprint': 'fingerprint',
  'operation': 'enroll_second_device',
  'slot_number': 2,
  'stage': stage,
  'face_verified': stage != 'FACE',
  'liveness_verified': stage == 'COMPLETED_UNTRUSTED',
  'complete': stage == 'COMPLETED_UNTRUSTED',
  'ready': stage != 'FACE',
  'fingers': stage == 'FACE' ? null : 3,
  'valid_frames': valid,
  'required_frames': 3,
  'expires_in': 90,
  'expires_at': DateTime.now()
      .toUtc()
      .add(const Duration(seconds: 90))
      .toIso8601String(),
  'result_classification': 'UNTRUSTED_TEST_RESULT',
  'trusted': false,
  'consumable': false,
  'activation_eligible': false,
  'activation_enabled': false,
  'message': stage == 'COMPLETED_UNTRUSTED'
      ? 'Biometric checks completed — awaiting trusted biometric approval'
      : stage == 'FACE'
      ? 'Center your face.'
      : 'Show three fingers with your face visible.',
};

class BioActivationKeys extends DeviceKeyStore {
  @override
  Future<Map<String, dynamic>?> getPublicKey(String id) async => {
    'public_key_fingerprint': 'fingerprint',
  };
  @override
  Future<String> sign(String id, String payload) async =>
      throw StateError('Unavailable approval must not sign');
}

class BioFixture {
  int faces = 0, live = 0, begins = 0, reads = 0;
  bool wrongFace = false,
      expired = false,
      forgedTrust = false,
      lostFaceResponse = false;
  bool networkFailure = false;
  String? faceFeedback, livenessFeedback;
  Completer<http.Response>? delayedFace, delayedLiveness;
  final paths = <String>[];
  final uploads = <List<int>>[];
  Map<String, dynamic> state = result('FACE');
  late final client = ApiClient(
    client: MockClient((request) async {
      final path = request.url.path;
      if (path == '/login') {
        return jsonResponse(
          jsonEncode({
            'access_token': 'token',
            'student': {'student_id': 'TEST001'},
          }),
          200,
        );
      }
      paths.add(path);
      if (path.endsWith('/activation-status')) {
        return jsonResponse(
          jsonEncode({
            'success': true,
            'status': 'NOT_ACTIVE',
            'pending_registration_id': 'pending-test',
            'candidate_device_id': 'tablet-test',
            'public_key_fingerprint': 'fingerprint',
            'operation': 'enroll_second_device',
            'slot_number': 2,
            'attendance_authorized': false,
            'maximum_active_devices': 2,
            'active_count': 1,
            'device': null,
          }),
          200,
        );
      }
      if (path.endsWith('/activation-readiness')) {
        return jsonResponse(
          jsonEncode({
            'success': false,
            'code': 'APPROVAL_UNAVAILABLE',
            'message':
                'Institutional biometric trust is unavailable. Device remains inactive.',
          }),
          503,
        );
      }
      expect(
        request.headers['X-Request-ID'],
        matches(RegExp(r'^b3-[a-f0-9]+-[0-9]+$')),
      );
      expect(request.headers['Authorization'], 'Bearer token');
      if (path == '/api/v1/device-approvals') {
        begins++;
        expect(jsonDecode(request.body), {
          'pending_registration_id': 'pending-test',
        });
        state = result('FACE');
        return jsonResponse(
          jsonEncode({...state, if (forgedTrust) 'trusted': true}),
          201,
        );
      }
      if (path == '/api/v1/device-approvals/bio-test') {
        reads++;
        return jsonResponse(jsonEncode(state), 200);
      }
      expect(
        request.headers['Content-Type'],
        startsWith('multipart/form-data'),
      );
      uploads.add(List<int>.from(request.bodyBytes));
      if (expired) {
        return jsonResponse(
          jsonEncode({
            'code': 'BIOMETRIC_EXPIRED',
            'message': 'Biometric test expired.',
          }),
          410,
        );
      }
      if (path.endsWith('/face')) {
        faces++;
        if (wrongFace) {
          return jsonResponse(
            jsonEncode({
              'code': 'FACE_NOT_MATCHED',
              'message': 'Face not matched.',
            }),
            403,
          );
        }
        if (networkFailure) throw http.ClientException('Connection lost');
        if (delayedFace != null) return delayedFace!.future;
        if (faceFeedback != null) {
          state = {
            ...result('FACE'),
            'feedback_code': faceFeedback,
            'message': faceFeedback == 'FACE_TOO_SMALL'
                ? 'Move closer and fill the oval.'
                : 'Keep exactly one face visible.',
          };
          return jsonResponse(jsonEncode(state), 200);
        }
        state = result('LIVENESS');
        if (lostFaceResponse) {
          lostFaceResponse = false;
          throw http.ClientException('Response lost');
        }
        return jsonResponse(jsonEncode(state), 200);
      }
      if (path.endsWith('/liveness/frame')) {
        live++;
        if (delayedLiveness != null) return delayedLiveness!.future;
        if (livenessFeedback != null) {
          state = {
            ...result('LIVENESS'),
            'ready': false,
            'message': livenessFeedback,
          };
          return jsonResponse(jsonEncode(state), 200);
        }
        state = result(
          live == 3 ? 'COMPLETED_UNTRUSTED' : 'LIVENESS',
          valid: live,
        );
        return jsonResponse(jsonEncode(state), 200);
      }
      throw StateError('Forbidden endpoint: $path');
    }),
  );
  late final api = DeviceBiometricApi(client);
  Future<void> login() => client.login('TEST001', 'password');
}

class DeniedCamera extends TestCamera {
  @override
  Future<void> initialize() async =>
      throw CameraException('CameraAccessDenied', 'Camera permission denied');
}

class NeverCaptureCamera extends TestCamera {
  final gate = Completer<XFile>();
  @override
  Future<XFile> takePicture() {
    captures++;
    return gate.future;
  }
}

class NeverBeginApi extends DeviceBiometricApi {
  final gate = Completer<Map<String, dynamic>>();
  @override
  Future<Map<String, dynamic>> begin(String pendingId) => gate.future;
}

class CompletedSessionApi extends DeviceBiometricApi {
  @override
  Future<Map<String, dynamic>> begin(String pendingId) async =>
      result('COMPLETED_UNTRUSTED', valid: 3);
}

class ShortSessionApi extends DeviceBiometricApi {
  @override
  Future<Map<String, dynamic>> begin(String pendingId) async => {
    ...result('FACE'),
    'expires_in': 2,
  };
}

Future<void> mountBio(
  WidgetTester tester,
  BioFixture fixture, {
  Future<List<CameraDescription>> Function()? loader,
  CameraController Function(CameraDescription)? factory,
  DeviceBiometricApi? api,
}) async {
  tester.view.physicalSize = const Size(448, 1300);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await fixture.login();
  await tester.pumpWidget(
    MaterialApp(
      home: DeviceBiometricApprovalScreen(
        pendingRegistrationId: 'pending-test',
        expiresAt: 'pending expiry',
        api: api ?? fixture.api,
        activationService: DeviceActivationService(
          client: fixture.client,
          keys: BioActivationKeys(),
        ),
        cameraLoader: loader ?? () async => [frontCamera],
        cameraFactory: factory ?? (_) => TestCamera(),
        stopwatchFactory: () => TestStopwatch(tester.binding.clock.now),
      ),
    ),
  );
  await tester.pump();
  addTearDown(() async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });
}

Future<void> start(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('Start facial verification'),
    160,
    scrollable: find.byType(Scrollable).first,
  );
  await Scrollable.ensureVisible(
    tester.element(find.text('Start facial verification')),
    alignment: 0.5,
  );
  await tester.pump();
  await tester.tap(find.text('Start facial verification'));
  await tester.pump();
  await tester.pump();
}

Future<void> tick(WidgetTester tester, [int milliseconds = 1000]) async {
  await tester.pump(Duration(milliseconds: milliseconds));
  await tester.pump();
  await tester.pump();
}

Color guideColor(WidgetTester tester, {bool liveness = false}) {
  final guide = tester.widget<AnimatedContainer>(
    find.byKey(
      ValueKey(liveness ? 'device-liveness-guide' : 'device-face-guide'),
    ),
  );
  return ((guide.decoration! as BoxDecoration).border! as Border).top.color;
}

void main() {
  testWidgets(
    'Biometric completion automatically activates and returns after server ACTIVE',
    (tester) async {
      final bio = BioFixture();
      await bio.login();
      final activation = ActivationFixture()
        ..pendingId = 'pending-test'
        ..candidateId = 'tablet-test'
        ..fingerprint = 'fingerprint';
      activation.keys.fingerprint = 'fingerprint';
      await activation.login();
      final camera = TestCamera();
      bool? returned;
      tester.view.physicalSize = const Size(448, 1300);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () async {
                  returned = await Navigator.push<bool>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => DeviceBiometricApprovalScreen(
                        pendingRegistrationId: 'pending-test',
                        expiresAt: 'pending',
                        api: bio.api,
                        activationService: activation.service,
                        cameraLoader: () async => [frontCamera],
                        cameraFactory: (_) => camera,
                        stopwatchFactory: () =>
                            TestStopwatch(tester.binding.clock.now),
                      ),
                    ),
                  );
                },
                child: const Text('My Device host'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('My Device host'));
      await tester.pumpAndSettle();
      await start(tester);
      for (var i = 0; i < 4; i++) {
        await tick(tester);
      }
      await tester.pumpAndSettle();
      expect(returned, isTrue);
      expect(find.text('My Device host'), findsOneWidget);
      expect(activation.confirms, 1);
      expect(activation.keys.signs, 1);
      expect(activation.keys.created, 0);
      expect(camera.releases, 1);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets('Guide stays white until a genuine server face match', (
    tester,
  ) async {
    final f = BioFixture()..delayedFace = Completer<http.Response>();
    await mountBio(tester, f);
    await start(tester);
    expect(
      guideColor(tester),
      Colors.white,
    ); // Camera initialization is not proof.
    await tick(tester);
    await tick(tester, 3000);
    expect(guideColor(tester), Colors.white); // A timer cannot turn it green.
    expect(find.text('Step 2: Liveness challenge'), findsNothing);
    f.delayedFace!.complete(jsonResponse(jsonEncode(result('LIVENESS')), 200));
    await tester.pump();
    await tester.pump();
    expect(guideColor(tester, liveness: true), const Color(0xFF35D596));
    expect(find.text('FACE VERIFIED · SHOW YOUR GESTURE'), findsOneWidget);
    expect(find.text('Show 3 fingers'), findsOneWidget);
  });
  testWidgets(
    'New liveness request clears earlier green while awaiting the server',
    (tester) async {
      final f = BioFixture();
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      expect(guideColor(tester, liveness: true), const Color(0xFF35D596));
      f.delayedLiveness = Completer<http.Response>();
      await tick(tester);
      expect(guideColor(tester, liveness: true), Colors.white);
      await tick(tester, 3000);
      expect(guideColor(tester, liveness: true), Colors.white);
      f.delayedLiveness!.complete(
        jsonResponse(jsonEncode(result('LIVENESS', valid: 1)), 200),
      );
      await tester.pump();
      await tester.pump();
      expect(guideColor(tester, liveness: true), const Color(0xFF35D596));
      expect(find.text('1/3 consecutive checks accepted'), findsOneWidget);
    },
  );
  for (final code in [
    'FACE_TOO_SMALL',
    'FACE_COUNT_INVALID',
    'FACE_NOT_CENTERED',
  ]) {
    testWidgets('Server $code makes the face guide red', (tester) async {
      final f = BioFixture()..faceFeedback = code;
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      expect(guideColor(tester), const Color(0xFFEF5350));
      expect(find.text('ADJUST YOUR POSITION'), findsOneWidget);
      expect(f.live, 0);
    });
  }
  testWidgets(
    'Server liveness progress shows green 1/3 and 2/3 then clean completion',
    (tester) async {
      final f = BioFixture();
      await mountBio(tester, f);
      await start(tester);
      await tick(tester); // Genuine face match.
      for (var accepted = 1; accepted <= 2; accepted++) {
        await tick(tester);
        expect(
          find.text('$accepted/3 consecutive checks accepted'),
          findsOneWidget,
        );
        final progress = tester.widget<LinearProgressIndicator>(
          find.byKey(const ValueKey('device-liveness-progress')),
        );
        expect(progress.value, accepted / 3);
        if (accepted < 3) {
          expect(guideColor(tester, liveness: true), const Color(0xFF35D596));
          expect(find.text('GESTURE ACCEPTED · HOLD STEADY'), findsOneWidget);
        }
      }
      await tick(tester); // Third accepted frame ends scanning.
      expect(find.byType(DeviceBiometricCompletion), findsOneWidget);
      expect(find.byType(DeviceLivenessPanel), findsNothing);
      expect(find.byType(CameraPreview), findsNothing);
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.text('Liveness detection: PASS'), findsOneWidget);
      expect(find.textContaining('Slot 2 remains inactive'), findsOneWidget);
      expect(
        f.paths.every(
          (p) =>
              (p.startsWith('/api/v1/device-approvals') ||
              p.startsWith('/api/v1/devices/pending-registrations/')),
        ),
        isTrue,
      );
    },
  );
  testWidgets(
    'Incorrect gesture makes the guide red and resets accepted progress',
    (tester) async {
      final f = BioFixture();
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      await tick(tester);
      expect(find.text('1/3 consecutive checks accepted'), findsOneWidget);
      f.livenessFeedback =
          'Show 3 fingers on one hand, palm toward the camera.';
      await tick(tester);
      expect(guideColor(tester, liveness: true), const Color(0xFFEF5350));
      expect(find.text('ADJUST YOUR GESTURE'), findsOneWidget);
      expect(find.text('0/3 consecutive checks accepted'), findsOneWidget);
      expect(find.text(f.livenessFeedback!), findsOneWidget);
    },
  );
  test(
    'Device biometric adapter only uses dedicated bearer-authenticated endpoints',
    () async {
      final f = BioFixture();
      await f.login();
      await f.api.begin('pending-test');
      await f.api.frame(Uint8List.fromList([1]), liveness: false);
      for (var i = 0; i < 3; i++) {
        await f.api.frame(Uint8List.fromList([i + 2]), liveness: true);
      }
      final completed = await f.api.status();
      expect(completed['stage'], 'COMPLETED_UNTRUSTED');
      expect(completed['activation_enabled'], false);
      expect(
        f.paths.every(
          (p) =>
              (p.startsWith('/api/v1/device-approvals') ||
              p.startsWith('/api/v1/devices/pending-registrations/')),
        ),
        true,
      );
    },
  );
  test('Adapter rejects a response claiming trusted approval', () async {
    final f = BioFixture();
    await f.login();
    f.forgedTrust = true;
    await expectLater(
      f.api.begin('pending-test'),
      throwsA(isA<ApiException>()),
    );
  });
  test('Adapter rejects a changed login before uploading frames', () async {
    final f = BioFixture();
    await f.login();
    await f.api.begin('pending-test');
    await f.login();
    await expectLater(
      f.api.frame(Uint8List(1), liveness: false),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'SESSION_CHANGED'),
      ),
    );
    expect(f.faces, 0);
  });
  testWidgets(
    'Explicit start runs face and liveness then releases camera without activation',
    (tester) async {
      final f = BioFixture();
      final camera = TestCamera();
      await mountBio(tester, f, factory: (_) => camera);
      expect(f.begins, 0);
      expect(camera.captures, 0);
      await start(tester);
      for (var i = 0; i < 5; i++) {
        await tick(tester);
      }
      expect(f.faces, 1);
      expect(f.live, 3);
      expect(
        latin1.decode(f.uploads.first),
        contains('\r\n\r\n\u0001\r\n'),
      ); // Original camera bytes, no preview transform applied to upload.
      expect(
        find.text(
          'Biometric checks completed — awaiting trusted biometric approval',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('Slot 2 remains inactive'), findsOneWidget);
      expect(camera.releases, 1);
      expect(
        f.paths.every(
          (p) =>
              (p.startsWith('/api/v1/device-approvals') ||
              p.startsWith('/api/v1/devices/pending-registrations/')),
        ),
        true,
      );
    },
  );
  testWidgets(
    'Permission denial is actionable and retry uses a new camera controller',
    (tester) async {
      final f = BioFixture();
      final denied = DeniedCamera();
      var opened = 0;
      await mountBio(
        tester,
        f,
        factory: (_) => opened++ == 0 ? denied : TestCamera(),
      );
      await start(tester);
      await tester.pump();
      expect(find.textContaining('Enable camera permission'), findsOneWidget);
      expect(denied.releases, 1);
      await tester.ensureVisible(find.text('Retry camera'));
      await tester.tap(find.text('Retry camera'));
      await tester.pump();
      await tester.pump();
      expect(opened, 2);
      expect(f.begins, 1);
    },
  );
  testWidgets(
    'Missing emulator front camera shows guidance without frame upload',
    (tester) async {
      final f = BioFixture();
      await mountBio(tester, f, loader: () async => []);
      await start(tester);
      expect(
        find.textContaining('front-facing camera is required'),
        findsOneWidget,
      );
      expect(f.faces, 0);
    },
  );
  testWidgets('Wrong face releases camera and never advances to liveness', (
    tester,
  ) async {
    final f = BioFixture()..wrongFace = true;
    final camera = TestCamera();
    await mountBio(tester, f, factory: (_) => camera);
    await start(tester);
    await tick(tester);
    expect(find.text('Face not matched.'), findsOneWidget);
    expect(f.live, 0);
    expect(camera.releases, 1);
  });
  testWidgets('Expired server session cannot complete biometric checks', (
    tester,
  ) async {
    final f = BioFixture()..expired = true;
    final camera = TestCamera();
    await mountBio(tester, f, factory: (_) => camera);
    await start(tester);
    await tick(tester);
    expect(find.text('Session expired'), findsOneWidget);
    expect(find.textContaining('Restart the scan'), findsOneWidget);
    expect(camera.releases, 1);
    expect(f.live, 0);
  });
  testWidgets(
    'Pause releases camera and resume recreates it for the same session',
    (tester) async {
      final f = BioFixture();
      final cameras = <TestCamera>[];
      await mountBio(
        tester,
        f,
        factory: (_) {
          final c = TestCamera();
          cameras.add(c);
          return c;
        },
      );
      await start(tester);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      await tester.pump();
      expect(cameras.single.releases, 1);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      await tester.pump();
      expect(cameras.length, 2);
      expect(f.begins, 1);
    },
  );
  testWidgets('Leaving during initialization disposes the late camera', (
    tester,
  ) async {
    final f = BioFixture();
    final gate = Completer<void>();
    final camera = TestCamera(initialization: gate);
    await mountBio(tester, f, factory: (_) => camera);
    await start(tester);
    await tester.pumpWidget(const SizedBox());
    gate.complete();
    await tester.pump();
    await tester.pump();
    expect(camera.releases, 1);
    expect(f.faces, 0);
  });
  testWidgets(
    'Lost face response reads server state instead of replaying the frame',
    (tester) async {
      final f = BioFixture()..lostFaceResponse = true;
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      expect(f.faces, 1);
      expect(f.reads, 1);
      expect(find.text('Step 2: Liveness challenge'), findsOneWidget);
    },
  );
  testWidgets('No single face produces visible feedback above the camera', (
    tester,
  ) async {
    final f = BioFixture()..faceFeedback = 'FACE_COUNT_INVALID';
    await mountBio(tester, f);
    await start(tester);
    await tick(tester);
    expect(find.text('No single face detected'), findsOneWidget);
    expect(find.text('Keep exactly one face visible.'), findsOneWidget);
    expect(
      tester.getTopLeft(find.byKey(const ValueKey('device-scan-status'))).dy,
      lessThan(
        tester
            .getTopLeft(find.byKey(const ValueKey('device-camera-preview')))
            .dy,
      ),
    );
    expect(f.live, 0);
  });
  testWidgets(
    'Small-face retries stop after eight attempts instead of loading forever',
    (tester) async {
      final f = BioFixture()..faceFeedback = 'FACE_TOO_SMALL';
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      expect(find.text('Face too small — move closer'), findsOneWidget);
      for (var i = 1; i < 8; i++) {
        await tick(tester, 2000);
      }
      expect(f.faces, 8);
      expect(find.text('Scan paused'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      await tick(tester, 20000);
      expect(f.faces, 8);
      expect(f.live, 0);
    },
  );
  testWidgets(
    'Only a server face match advances to liveness with visible confirmation',
    (tester) async {
      final f = BioFixture();
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      expect(find.text('Face verified'), findsOneWidget);
      expect(find.text('Step 2: Liveness challenge'), findsOneWidget);
      expect(f.faces, 1);
      expect(f.live, 0);
    },
  );
  testWidgets('Network error is not swallowed by an unchanged FACE status', (
    tester,
  ) async {
    final f = BioFixture()..networkFailure = true;
    await mountBio(tester, f);
    await start(tester);
    await tick(tester);
    expect(find.text('Network error'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(f.faces, 1);
    expect(f.reads, 1);
    expect(f.live, 0);
    await tick(tester, 5000);
    expect(f.faces, 1);
  });
  testWidgets(
    'A hung HTTP frame times out visibly and never overlaps another frame',
    (tester) async {
      final f = BioFixture()..delayedFace = Completer<http.Response>();
      final camera = TestCamera();
      await mountBio(tester, f, factory: (_) => camera);
      await start(tester);
      await tick(tester);
      await tick(tester, 16000);
      expect(find.text('Request timed out'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(f.faces, 1);
      expect(camera.captures, 1);
      f.delayedFace!.complete(
        jsonResponse(jsonEncode(result('LIVENESS')), 200),
      );
      await tester.pump();
      await tester.pump();
      expect(find.text('Step 2: Liveness challenge'), findsNothing);
    },
  );
  testWidgets(
    'A hung native capture stops after eight seconds with no upload',
    (tester) async {
      final f = BioFixture();
      final camera = NeverCaptureCamera();
      await mountBio(tester, f, factory: (_) => camera);
      await start(tester);
      await tick(tester);
      await tick(tester, 9000);
      expect(find.text('Camera capture timed out'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(f.faces, 0);
      expect(camera.captures, 1);
      camera.gate.complete(XFile.fromData(Uint8List.fromList([1])));
      await tester.pump();
      await tester.pump();
      expect(f.faces, 0);
    },
  );
  testWidgets('Overall expiry stops a busy native capture immediately', (
    tester,
  ) async {
    final f = BioFixture();
    final camera = NeverCaptureCamera();
    await mountBio(tester, f, factory: (_) => camera, api: ShortSessionApi());
    await start(tester);
    await tick(tester);
    await tick(tester, 2000);
    expect(find.text('Session expired'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(f.faces, 0);
    camera.gate.complete(XFile.fromData(Uint8List.fromList([1])));
    await tester.pump();
    await tester.pump();
  });
  testWidgets(
    'A hung create request stops with a request timeout before camera opens',
    (tester) async {
      final f = BioFixture();
      final api = NeverBeginApi();
      var cameraOpens = 0;
      await mountBio(
        tester,
        f,
        api: api,
        factory: (_) {
          cameraOpens++;
          return TestCamera();
        },
      );
      await start(tester);
      await tick(tester, 17000);
      expect(find.text('Request timed out'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(cameraOpens, 0);
      api.gate.complete(result('FACE'));
      await tester.pump();
      expect(cameraOpens, 0);
    },
  );
  testWidgets(
    'Reopened completed session shows result without opening camera',
    (tester) async {
      final f = BioFixture();
      var opens = 0;
      await mountBio(
        tester,
        f,
        api: CompletedSessionApi(),
        factory: (_) {
          opens++;
          return TestCamera();
        },
      );
      await start(tester);
      expect(find.byType(DeviceBiometricCompletion), findsOneWidget);
      expect(opens, 0);
      expect(f.faces, 0);
      expect(f.live, 0);
      expect(find.byType(DeviceLivenessPanel), findsNothing);
    },
  );
  testWidgets(
    'Completion stops capture, hides controls and releases camera once',
    (tester) async {
      final f = BioFixture();
      final camera = TestCamera();
      await mountBio(tester, f, factory: (_) => camera);
      await start(tester);
      for (var i = 0; i < 4; i++) {
        await tick(tester);
      }
      expect(find.byType(DeviceBiometricCompletion), findsOneWidget);
      for (final text in [
        'Face recognition: PASS',
        'Liveness detection: PASS',
        'Device key verification: PASS',
        'Registration status: NOT ACTIVE',
        'Trusted biometric approval: NOT YET AVAILABLE',
      ]) {
        expect(find.text(text), findsOneWidget);
      }
      expect(find.byType(CameraPreview), findsNothing);
      expect(find.byType(DeviceLivenessPanel), findsNothing);
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('Start facial verification'), findsNothing);
      expect(camera.releases, 1);
      final captures = camera.captures;
      await tick(tester, 10000);
      expect(camera.captures, captures);
      expect(camera.releases, 1);
      expect(f.live, 3);
      expect(find.text('Back to My Device'), findsOneWidget);
    },
  );
  for (final failure in ['expired', 'wrong-face']) {
    testWidgets('$failure never displays successful completion', (
      tester,
    ) async {
      final f = BioFixture();
      if (failure == 'expired') {
        f.expired = true;
      } else {
        f.wrongFace = true;
      }
      await mountBio(tester, f);
      await start(tester);
      await tick(tester);
      expect(find.byType(DeviceBiometricCompletion), findsNothing);
      expect(find.text('Face recognition: PASS'), findsNothing);
      expect(
        find.text(failure == 'expired' ? 'Session expired' : 'Face mismatch'),
        findsOneWidget,
      );
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  }
  for (final landscape in [false, true]) {
    testWidgets(
      'Responsive face guide fits the real tablet ${landscape ? 'landscape' : 'portrait'} viewport',
      (tester) async {
        final f = BioFixture();
        await mountBio(tester, f);
        tester.view.physicalSize = landscape
            ? const Size(1164, 777)
            : const Size(777, 1164);
        await tester.pump();
        await start(tester);
        await tester.scrollUntilVisible(
          find.byKey(const ValueKey('device-camera-preview')),
          -160,
          scrollable: find.byType(Scrollable).first,
        );
        final guide = tester.getSize(
          find.byKey(const ValueKey('device-face-guide')),
        );
        final preview = tester.getSize(find.byType(CameraPreview));
        expect(guide.width, greaterThan(preview.width * 0.24));
        expect(guide.height, lessThanOrEqualTo(preview.height * 0.66 + 24));
        expect(tester.takeException(), isNull);
      },
    );
  }
  test(
    'Device HTTP diagnostic logs redact tokens, identifiers and frame bodies',
    () async {
      final messages = <String>[];
      final original = debugPrint;
      debugPrint = (String? message, {int? wrapWidth}) {
        if (message != null) messages.add(message);
      };
      try {
        final f = BioFixture();
        await f.login();
        await f.api.begin('pending-test');
        await f.api.frame(
          Uint8List.fromList(utf8.encode('PRIVATE_BYTES_FRAME')),
          liveness: false,
        );
        final logs = messages.join(' ');
        expect(logs, contains('request_id=b3-'));
        expect(logs, contains('status=200'));
        for (final secret in [
          'Bearer token',
          'PRIVATE_BYTES_FRAME',
          'bio-test',
          'pending-test',
          'fingerprint',
        ]) {
          expect(logs, isNot(contains(secret)));
        }
      } finally {
        debugPrint = original;
      }
    },
  );
}
