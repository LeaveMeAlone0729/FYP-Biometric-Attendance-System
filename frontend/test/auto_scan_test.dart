// Module owner: Chew Zhexuan
// Module: Facial Recognition and Liveness Detection
import 'dart:async';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/camera_screen.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/theme.dart';

const frontCamera = CameraDescription(
  name: 'test-front',
  lensDirection: CameraLensDirection.front,
  sensorOrientation: 90,
);

class TestCamera extends CameraController {
  TestCamera({this.initialization, this.previewSize = const Size(640, 480)})
    : super(frontCamera, ResolutionPreset.medium, enableAudio: false);
  final Completer<void>? initialization;
  final Size previewSize;
  int captures = 0, releases = 0;
  @override
  Future<void> initialize() async {
    if (initialization != null) await initialization!.future;
    value = value.copyWith(isInitialized: true, previewSize: previewSize);
  }

  @override
  Future<XFile> takePicture() async =>
      XFile.fromData(Uint8List.fromList([++captures]), name: 'frame.jpg');
  @override
  Widget buildPreview() => const ColoredBox(color: Color(0xFF263238));
  @override
  Future<void> dispose() async {
    releases++;
    await super.dispose();
  }
}

class TestStopwatch implements Stopwatch {
  TestStopwatch(this.now);
  final DateTime Function() now;
  DateTime? _started;
  Duration _saved = Duration.zero;
  @override
  bool get isRunning => _started != null;
  @override
  Duration get elapsed =>
      _saved + (_started == null ? Duration.zero : now().difference(_started!));
  @override
  int get elapsedMicroseconds => elapsed.inMicroseconds;
  @override
  int get elapsedMilliseconds => elapsed.inMilliseconds;
  @override
  int get elapsedTicks => elapsedMicroseconds;
  @override
  int get frequency => 1000000;
  @override
  void start() {
    _started ??= now();
  }

  @override
  void stop() {
    _saved = elapsed;
    _started = null;
  }

  @override
  void reset() {
    _saved = Duration.zero;
    if (isRunning) _started = now();
  }
}

class ScanApi extends ApiClient {
  ScanApi(this.respond);
  final Future<Map<String, dynamic>> Function(String, Map<String, String>)
  respond;
  final calls = <Map<String, String>>[];
  int cancellations = 0, inFlight = 0, maximumInFlight = 0;
  @override
  Future<dynamic> image(
    String path,
    Uint8List bytes,
    Map<String, String> fields,
  ) async {
    calls.add({'path': path, ...fields});
    inFlight++;
    if (inFlight > maximumInFlight) maximumInFlight = inFlight;
    try {
      return await respond(path, fields);
    } finally {
      inFlight--;
    }
  }

  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    cancellations++;
    return {'success': true};
  }

  @override
  Future<void> refreshStudent() async {}
}

Future<void> mountScan(
  WidgetTester tester,
  ScanApi api, {
  bool enrollment = false,
  int seconds = 90,
  CameraController Function()? createCamera,
}) async {
  tester.view.physicalSize = const Size(448, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  ApiClient.instance = api;
  await tester.pumpWidget(
    MaterialApp(
      theme: appTheme(),
      home: CameraScreen(
        enrollment: enrollment,
        challenge: enrollment
            ? null
            : {
                'challenge_id': 'test-challenge',
                'course_name': 'Mobile Application Development',
                'expires_in': seconds,
              },
        cameraLoader: () async => [frontCamera],
        cameraFactory: (_) => createCamera?.call() ?? TestCamera(),
        stopwatchFactory: () => TestStopwatch(tester.binding.clock.now),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
  addTearDown(() async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });
}

Future<void> advance(WidgetTester tester, int milliseconds) async {
  await tester.pump(Duration(milliseconds: milliseconds));
  await tester.pump();
}

Color guideColor(WidgetTester tester, {String guide = 'face-guide'}) =>
    ((tester.widget<AnimatedContainer>(find.byKey(ValueKey(guide))).decoration
                    as BoxDecoration)
                .border
            as Border)
        .top
        .color;

void main() {
  testWidgets(
    'Automatic scan turns red, recovers green and advances without a capture tap',
    (tester) async {
      var faces = 0;
      final api = ScanApi((path, fields) async {
        if (path == '/liveness/frame') {
          return {
            'complete': false,
            'valid_frames': 0,
            'message': 'Show your hand.',
          };
        }
        faces++;
        if (faces == 1) return {'ready': false, 'message': 'Center your face.'};
        if (fields['preview_only'] == 'true') {
          return {
            'ready': true,
            'preview_only': true,
            'message': 'Hold still.',
          };
        }
        return {'ready': true, 'face_verified': true, 'fingers': 3};
      });
      await mountScan(tester, api);
      expect(find.text('Capture & verify face'), findsNothing);
      await advance(tester, 1200);
      expect(guideColor(tester), const Color(0xFFEF5350));
      await advance(tester, 900);
      expect(guideColor(tester), const Color(0xFF35D596));
      expect(api.calls.last['preview_only'], 'true');
      await advance(tester, 900);
      expect(api.calls.last['preview_only'], 'false');
      expect(find.text('Show 3 fingers'), findsOneWidget);
      expect(find.byKey(const ValueKey('face-guide')), findsNothing);
      expect(find.byKey(const ValueKey('gesture-guide')), findsOneWidget);
      expect(
        find.textContaining('Neither needs to be centered.'),
        findsOneWidget,
      );
      await advance(tester, 1600);
      expect(api.calls.last['path'], '/liveness/frame');
      expect(
        guideColor(tester, guide: 'gesture-guide'),
        const Color(0xFFEF5350),
      );
      expect(api.maximumInFlight, 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Gesture guide uses the full camera frame and recovers through three checks',
    (tester) async {
      var gestures = 0;
      final api = ScanApi((path, fields) async {
        if (path == '/liveness/frame') {
          gestures++;
          return {
            'complete': gestures == 3,
            'valid_frames': gestures,
            'message': 'Correct gesture. Hold steady.',
          };
        }
        if (fields['preview_only'] == 'true') {
          return {
            'ready': true,
            'preview_only': true,
            'message': 'Hold still.',
          };
        }
        return {'ready': true, 'face_verified': true, 'fingers': 2};
      });
      await mountScan(
        tester,
        api,
        createCamera: () => TestCamera(previewSize: const Size(1280, 720)),
      );
      final frame = find.byKey(const ValueKey('camera-frame'));
      expect(tester.widget<AspectRatio>(frame).aspectRatio, 720 / 1280);
      await advance(tester, 1200);
      await advance(tester, 900);
      expect(find.byKey(const ValueKey('face-guide')), findsNothing);
      tester.view.physicalSize = const Size(360, 800);
      await tester.pump();
      final frameSize = tester.getSize(frame);
      expect(frameSize.height, lessThanOrEqualTo(400));
      expect(tester.getBottomLeft(frame).dy, lessThan(800));
      final guideSize = tester.getSize(
        find.byKey(const ValueKey('gesture-guide')),
      );
      expect(guideSize.width, frameSize.width - 16);
      expect(guideSize.height, frameSize.height - 16);
      await advance(tester, 1600);
      expect(
        guideColor(tester, guide: 'gesture-guide'),
        const Color(0xFF35D596),
      );
      await advance(tester, 900);
      await advance(tester, 900);
      expect(find.text('Attendance accepted'), findsOneWidget);
      expect(api.cancellations, 0);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Enrollment captures nothing until consent and saves only after a ready preview',
    (tester) async {
      final api = ScanApi(
        (_, fields) async => fields['preview_only'] == 'true'
            ? {'ready': true, 'preview_only': true, 'message': 'Hold still.'}
            : {'ready': true, 'registered': true},
      );
      await mountScan(tester, api, enrollment: true);
      await advance(tester, 20000);
      expect(api.calls, isEmpty);
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      await advance(tester, 1200);
      expect(api.calls.single['consent'], 'true');
      expect(find.text('Face registered'), findsNothing);
      await advance(tester, 900);
      expect(find.text('Face registered'), findsOneWidget);
      expect(api.calls.length, 2);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Thirty-second face deadline stops automatic captures and cancels the challenge',
    (tester) async {
      final api = ScanApi(
        (_, _) async => {'ready': false, 'message': 'No face detected.'},
      );
      await mountScan(tester, api);
      await advance(tester, 1200);
      await advance(tester, 30000);
      expect(find.text('Verification incomplete'), findsOneWidget);
      expect(
        find.textContaining('No clear face was confirmed in time'),
        findsOneWidget,
      );
      final count = api.calls.length;
      await advance(tester, 10000);
      expect(api.calls.length, count);
      expect(api.cancellations, 1);
    },
  );

  testWidgets(
    'Slow face requests never overlap and timeout waits for their response',
    (tester) async {
      final pending = Completer<Map<String, dynamic>>();
      final api = ScanApi((_, _) => pending.future);
      await mountScan(tester, api);
      await advance(tester, 1200);
      await advance(tester, 30000);
      expect(api.calls.length, 1);
      expect(api.maximumInFlight, 1);
      expect(find.text('Verification incomplete'), findsNothing);
      expect(find.text('Waiting for the last server check…'), findsOneWidget);
      pending.complete({'ready': false, 'message': 'No face detected.'});
      await tester.pump();
      expect(find.text('Verification incomplete'), findsOneWidget);
      expect(api.cancellations, 1);
    },
  );

  testWidgets(
    'A committed attendance response remains successful when it arrives after the countdown',
    (tester) async {
      final pending = Completer<Map<String, dynamic>>();
      final api = ScanApi((path, fields) async {
        if (path == '/liveness/frame') return pending.future;
        if (fields['preview_only'] == 'true') {
          return {
            'ready': true,
            'preview_only': true,
            'message': 'Hold still.',
          };
        }
        return {'ready': true, 'face_verified': true, 'fingers': 2};
      });
      await mountScan(tester, api, seconds: 6);
      await advance(tester, 1200);
      await advance(tester, 900);
      await advance(tester, 1600);
      await advance(tester, 3000);
      expect(find.text('Waiting for the last server check…'), findsOneWidget);
      pending.complete({
        'complete': true,
        'recorded_at': '2026-10-29T10:00:00+08:00',
      });
      await tester.pump();
      expect(find.text('Attendance accepted'), findsOneWidget);
      expect(api.cancellations, 0);
    },
  );

  testWidgets(
    'Backgrounding stops capture and resuming starts a fresh preview',
    (tester) async {
      final api = ScanApi(
        (_, _) async => {
          'ready': true,
          'preview_only': true,
          'message': 'Hold still.',
        },
      );
      await mountScan(tester, api);
      await advance(tester, 1200);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      await advance(tester, 3000);
      expect(api.calls.length, 1);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      await advance(tester, 1200);
      expect(api.calls.length, 2);
      expect(api.calls.last['preview_only'], 'true');
      expect(tester.takeException(), isNull);
    },
  );
}
