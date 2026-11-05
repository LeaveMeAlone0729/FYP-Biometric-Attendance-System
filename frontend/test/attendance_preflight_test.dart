import 'dart:typed_data';
import 'dart:async';
import 'dart:io';
import 'package:frontend/modules/networks/services/network_verification_failure.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/screens/attendance_flow_screen.dart';
import 'package:frontend/modules/biometrics/screens/camera_screen.dart';
import 'attendance_authorization_test.dart' show AttendanceFixture;

Future<void> enterPin(WidgetTester tester) async {
  for (final digit in ['1', '2', '3', '4', '5', '6']) {
    await tester.tap(find.text(digit));
    await tester.pump();
  }
  await tester.ensureVisible(find.byKey(const ValueKey('submit-attendance')));
  await tester.tap(find.byKey(const ValueKey('submit-attendance')));
  await tester.pumpAndSettle();
}

void main() {
  test(
    'Preflight signs retained key but requires separate final nonce and signature',
    () async {
      final f = AttendanceFixture();
      await f.login();
      await f.signing.preflight('attempt');
      await f.signing.proof('attempt');
      expect(f.keys.signs, 2);
      expect(f.keys.creates, 0);
      expect(f.issued, 2);
      expect(f.frames, 0);
    },
  );
  test(
    'Final server network rejection is surfaced after successful preflight',
    () async {
      final f = AttendanceFixture();
      await f.login();
      await f.signing.preflight('attempt');
      f.denial = 'NETWORK_NOT_AUTHORIZED';
      await expectLater(
        f.api.submitLivenessFrame('attempt', Uint8List.fromList([1])),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'NETWORK_NOT_AUTHORIZED',
          ),
        ),
      );
      expect(f.issued, 2);
      expect(f.keys.signs, 2);
    },
  );
  test('Mismatched binding and missing key fail closed', () async {
    final f = AttendanceFixture();
    await f.login();
    f.wrongBinding = true;
    await expectLater(
      f.signing.preflight('attempt'),
      throwsA(isA<ApiException>()),
    );
    f.keys.missing = true;
    await expectLater(
      f.signing.preflight('attempt'),
      throwsA(isA<ApiException>()),
    );
    expect(f.keys.creates, 0);
  });
  for (final denied in [false, true]) {
    testWidgets('PIN preflight before camera denied=$denied', (tester) async {
      final f = AttendanceFixture();
      await f.login();
      if (denied) f.denial = 'NO_ENABLED_NETWORK_POLICY';
      final saved = ApiClient.instance;
      ApiClient.instance = f.client;
      addTearDown(() => ApiClient.instance = saved);
      var cameras = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttendanceFlowScreen(
              client: f.client,
              authorization: f.signing,
              cameraBuilder: (_) {
                cameras++;
                return const Scaffold(body: Text('Camera opened'));
              },
            ),
          ),
        ),
      );
      await enterPin(tester);
      expect(cameras, denied ? 0 : 1);
      expect(f.frames, 0);
      if (denied) {
        expect(find.text('Verification result'), findsOneWidget);
        expect(find.text('The network policy is disabled.'), findsOneWidget);
        await tester.ensureVisible(find.text('Back to attendance'));
        await tester.tap(find.text('Back to attendance'));
        await tester.pumpAndSettle();
      } else {
        expect(find.text('Camera opened'), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
    });
  }
  for (final reason in [
    'NO_ENABLED_NETWORK_POLICY',
    'ATTENDANCE_DEVICE_NOT_ACTIVE',
    'unavailable',
    'timeout',
    'dns',
    'refused',
  ]) {
    testWidgets('Early $reason prevents capture and signing', (tester) async {
      final f = AttendanceFixture();
      await f.login();
      f.preflightOffline = reason == 'unavailable';
      if (reason == 'timeout') {
        f.preflightTransportError = TimeoutException('No response');
      } else if (reason == 'dns' || reason == 'refused') {
        f.preflightTransportError = SocketException(reason);
      } else if (!f.preflightOffline) {
        f.preflightFailure = reason;
      }
      final saved = ApiClient.instance;
      ApiClient.instance = f.client;
      addTearDown(() => ApiClient.instance = saved);
      var cameras = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttendanceFlowScreen(
              client: f.client,
              authorization: f.signing,
              cameraBuilder: (_) {
                cameras++;
                return const SizedBox();
              },
            ),
          ),
        ),
      );
      await enterPin(tester);
      expect(cameras, 0);
      expect(f.keys.signs, 0);
      expect(f.frames, 0);
      expect(find.text('Verification result'), findsOneWidget);
      if (['unavailable', 'timeout', 'dns', 'refused'].contains(reason)) {
        expect(
          find.textContaining('Network verification: FAIL'),
          findsOneWidget,
        );
        expect(
          find.textContaining(NetworkVerificationFailure.unreachableMessage),
          findsOneWidget,
        );
        expect(find.textContaining('NETWORK_NOT_AUTHORIZED'), findsNothing);
      }
      await tester.ensureVisible(find.text('Back to attendance'));
      await tester.tap(find.text('Back to attendance'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('Failure result never initializes camera even on resume', (
    tester,
  ) async {
    var loads = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          initialFailure: 'Device revoked',
          challenge: const {'challenge_id': 'attempt', 'course_name': 'Test'},
          cameraLoader: () async {
            loads++;
            return [];
          },
        ),
      ),
    );
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(loads, 0);
    expect(find.text('Device revoked'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    expect(tester.takeException(), isNull);
  });
}
