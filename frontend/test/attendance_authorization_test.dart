import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/devices/services/attendance_device_authorization.dart';
import 'package:frontend/modules/devices/services/authorized_attendance_biometric_api.dart';
import 'package:frontend/modules/biometrics/screens/camera_screen.dart';
import 'auto_scan_test.dart' show TestCamera, frontCamera, TestStopwatch;

class AttendanceKeys extends DeviceKeyStore {
  bool missing = false;
  int signs = 0, creates = 0;
  Completer<String>? wait;
  @override
  Future<Map<String, dynamic>?> getPublicKey(String student) async =>
      missing ? null : {'public_key_fingerprint': 'a' * 64};
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String student) async {
    creates++;
    throw StateError('Attendance must never create or rotate a key');
  }

  @override
  Future<String> sign(String student, String payload) async {
    signs++;
    return wait?.future ?? 'fixture-DER-signature';
  }
}

class AttendanceFixture {
  final keys = AttendanceKeys();
  DateTime now = DateTime.now();
  int issued = 0, frames = 0;
  bool wrongBinding = false, expired = false;
  String? denial, preflightFailure;
  bool preflightOffline = false;
  Object? preflightTransportError;
  late final client = ApiClient(
    client: MockClient((request) async {
      http.Response response(Object data, int status) =>
          http.Response(jsonEncode(data), status);
      final path = request.url.path;
      if (path == '/login') {
        return response({
          'access_token': 'test-token',
          'student': {'student_id': 'TEST001'},
        }, 200);
      }
      if (request.headers['Authorization'] != 'Bearer test-token') {
        throw StateError('Missing auth');
      }
      if (path == '/api/v1/attendance/device-challenges' ||
          path == '/api/v1/attendance/preflight-challenges') {
        if (path.contains('preflight') && preflightTransportError != null) {
          throw preflightTransportError!;
        }
        if (path.contains('preflight') && preflightOffline) {
          throw const ApiException(
            'The backend is unavailable.',
            0,
            'NETWORK_ERROR',
          );
        }
        if (path.contains('preflight') && preflightFailure != null) {
          return response({
            'success': false,
            'code': preflightFailure,
            'message': 'Early verification rejected.',
          }, 403);
        }
        final operation = path.contains('preflight')
            ? 'attendance_preflight'
            : 'attendance_authorization';
        issued++;
        final requested = jsonDecode(request.body) as Map;
        if (requested.keys.length != 2 ||
            requested['public_key_fingerprint'] != 'a' * 64) {
          throw StateError('Invalid proof selector contract');
        }
        final expiry = now
            .add(Duration(seconds: expired ? -1 : 60))
            .toUtc()
            .toIso8601String();
        final binding = {
          'challenge_id': 'nonce-$issued',
          'attendance_challenge_id': wrongBinding
              ? 'different'
              : requested['attendance_challenge_id'],
          'attendance_session_id': 12,
          'device_id': 'registered-fixture',
          'slot_number': 2,
          'public_key_fingerprint': 'a' * 64,
          'operation': operation,
          'expires_at': expiry,
        };
        final payload = {
          ...binding,
          'version': 1,
          'purpose': operation,
          'student_id': 'TEST001',
          'auth_session_hash': 'session-hash',
          'biometric_verification_id': 4,
          'nonce': 'server-random',
        };
        return response({
          'success': true,
          ...binding,
          'algorithm': 'ECDSA_P256_SHA256',
          'signature_encoding': 'base64-DER',
          'signing_payload': base64Encode(utf8.encode(jsonEncode(payload))),
        }, 201);
      }
      if (path == '/attendance/start') {
        return response({
          'challenge_id': 'attempt',
          'course_name': 'Test course',
          'expires_in': 90,
        }, 200);
      }
      if (path == '/api/v1/attendance/preflight') {
        if (denial != null) {
          return response({
            'success': false,
            'code': denial,
            'message': 'The network policy is disabled.',
          }, 403);
        }
        return response({
          'success': true,
          'result': 'PASS',
          'attendance_authorized': false,
          'attendance_challenge_id': 'attempt',
        }, 200);
      }
      if (path == '/verify-face') {
        final preview = request.body.contains(
          'name="preview_only"\r\n\r\ntrue',
        );
        return response(
          preview
              ? {
                  'ready': true,
                  'preview_only': true,
                  'message': 'Face guide ready',
                }
              : {'ready': true, 'face_verified': true, 'fingers': 3},
          200,
        );
      }
      if (path == '/liveness/frame') {
        if (!request.body.contains('name="device_challenge_id"') ||
            !request.body.contains('name="device_signature"') ||
            !request.body.contains('fixture-DER-signature')) {
          throw StateError('Unsigned attendance frame');
        }
        frames++;
        if (denial != null) {
          return response({
            'success': false,
            'code': denial,
            'message': 'The final attendance network is not authorised.',
          }, 403);
        }
        return response({
          'success': true,
          'complete': frames >= 3,
          'valid_frames': frames,
          'message': 'Accepted gesture',
          'recorded_at': now.toUtc().toIso8601String(),
        }, 200);
      }
      if (path.startsWith('/attendance/cancel/')) {
        return response({'success': true}, 200);
      }
      throw StateError('Unexpected route $path');
    }),
  );
  late final signing = AttendanceDeviceAuthorization(
    client: client,
    keys: keys,
    now: () => now,
  );
  late final api = AuthorizedAttendanceBiometricApi(
    client: client,
    devices: signing,
  );
  Future<void> login() => client.login('TEST001', 'password');
}

void main() {
  test(
    'Attendance uses retained key, caches only its own unconsumed nonce and refreshes expiry',
    () async {
      final f = AttendanceFixture();
      await f.login();
      final first = await f.signing.proof('attempt-1');
      expect(first['device_challenge_id'], 'nonce-1');
      expect(await f.signing.proof('attempt-1'), first);
      expect(f.issued, 1);
      expect(f.keys.signs, 1);
      f.now = f.now.add(const Duration(seconds: 61));
      await f.signing.proof('attempt-1');
      expect(f.issued, 2);
      await f.signing.proof('attempt-2');
      expect(f.issued, 3);
      expect(f.keys.creates, 0);
    },
  );
  test(
    'Concurrent proof preparation coalesces without duplicate native signatures',
    () async {
      final f = AttendanceFixture();
      await f.login();
      final values = await Future.wait([
        f.signing.proof('one'),
        f.signing.proof('one'),
      ]);
      expect(values[0], values[1]);
      expect(f.issued, 1);
      expect(f.keys.signs, 1);
    },
  );
  test(
    'Missing key, incompatible binding and expired challenge never submit attendance',
    () async {
      final f = AttendanceFixture();
      await f.login();
      f.keys.missing = true;
      await expectLater(
        f.api.submitLivenessFrame('one', Uint8List(1)),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'LOCAL_KEY_MISSING',
          ),
        ),
      );
      expect(f.issued, 0);
      expect(f.frames, 0);
      f.keys.missing = false;
      f.wrongBinding = true;
      await expectLater(f.signing.proof('one'), throwsA(isA<ApiException>()));
      expect(f.keys.signs, 0);
      f.wrongBinding = false;
      f.expired = true;
      await expectLater(f.signing.proof('one'), throwsA(isA<ApiException>()));
      expect(f.keys.signs, 0);
    },
  );
  test(
    'Login change while signing prevents submitting proof under a new session',
    () async {
      final f = AttendanceFixture();
      await f.login();
      f.keys.wait = Completer<String>();
      final expectation = expectLater(
        f.api.submitLivenessFrame('one', Uint8List(1)),
        throwsA(isA<ApiException>()),
      );
      for (var i = 0; i < 20 && f.keys.signs == 0; i++) {
        await Future<void>.delayed(Duration.zero);
      }
      await f.login();
      f.keys.wait!.complete('signature');
      await expectation;
      expect(f.frames, 0);
    },
  );
  test('Transport adds proof fields and does not submit PASS flags', () async {
    final f = AttendanceFixture();
    await f.login();
    for (var i = 0; i < 3; i++) {
      await f.api.submitLivenessFrame('one', Uint8List.fromList([i]));
    }
    expect(f.frames, 3);
    expect(f.keys.signs, 1);
    expect(f.keys.creates, 0);
    await f.signing.proof('one');
    expect(f.issued, 2);
  });
  for (final failure in [false, true]) {
    testWidgets(
      'Partner camera automatically signs attendance and displays final result failure=$failure',
      (tester) async {
        final f = AttendanceFixture();
        if (failure) {
          f.denial = 'NETWORK_NOT_AUTHORIZED';
        }
        await f.login();
        final old = ApiClient.instance;
        ApiClient.instance = f.client;
        addTearDown(() => ApiClient.instance = old);
        tester.view.physicalSize = const Size(800, 1200);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(
          MaterialApp(
            home: CameraScreen(
              challenge: const {
                'challenge_id': 'one',
                'course_name': 'Isolated attendance integration',
                'expires_in': 90,
              },
              api: f.api,
              cameraLoader: () async => [frontCamera],
              cameraFactory: (_) => TestCamera(),
              stopwatchFactory: () => TestStopwatch(tester.binding.clock.now),
            ),
          ),
        );
        for (var i = 0; i < 18; i++) {
          await tester.pump(const Duration(seconds: 1));
          await tester.pump();
        }
        expect(f.keys.signs, 1);
        expect(f.keys.creates, 0);
        if (failure) {
          expect(
            find.text('The final attendance network is not authorised.'),
            findsOneWidget,
          );
          expect(find.text('Attendance accepted'), findsNothing);
        } else {
          expect(find.text('Attendance accepted'), findsOneWidget);
          expect(f.frames, 3);
        }
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox());
        await tester.pump();
      },
    );
  }
}
