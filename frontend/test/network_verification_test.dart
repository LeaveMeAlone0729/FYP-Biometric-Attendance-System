import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/theme.dart' show InfoNotice;
import 'package:frontend/modules/networks/services/network_verification_api.dart';
import 'package:frontend/modules/networks/screens/network_verification_screen.dart';
import 'package:frontend/modules/networks/services/network_verification_failure.dart';

Map<String, dynamic> result([String code = 'NETWORK_AUTHORIZED']) => {
  'success': true,
  'verification_id': 1,
  'result': code == 'NETWORK_AUTHORIZED' ? 'PASS' : 'FAIL',
  'reason_code': code,
  'message': code == 'NETWORK_AUTHORIZED'
      ? 'Matches the controlled simulation policy.'
      : 'Network check failed. Check the simulation connection.',
  'source_ip': '192.0.2.10',
  'matched_policy_id': code == 'NETWORK_AUTHORIZED' ? 'sim-v4' : null,
  'matched_policy_name': code == 'NETWORK_AUTHORIZED'
      ? 'Simulation policy'
      : null,
  'verified_at': DateTime.now().toUtc().toIso8601String(),
  'operation': 'network_diagnostic',
  'attendance_authorized': false,
};

class Fixture {
  dynamic response = result();
  int calls = 0, status = 200;
  bool offline = false;
  Object? transportError;
  Completer<http.Response>? waiting;
  late final client = ApiClient(
    client: MockClient((request) async {
      if (request.url.path == '/login') {
        return http.Response(
          jsonEncode({
            'access_token': 'fixture-token',
            'student': {'student_id': 'TEST001'},
          }),
          200,
        );
      }
      calls++;
      if (request.url.path != '/api/v1/networks/verifications' ||
          (jsonDecode(request.body) as Map).isNotEmpty ||
          request.headers['Authorization'] != 'Bearer fixture-token' ||
          request.headers.containsKey('X-Forwarded-For')) {
        throw StateError(
          'Invalid diagnostic authentication or request contract',
        );
      }
      if (transportError != null) throw transportError!;
      if (offline) {
        throw http.ClientException('offline');
      }
      if (waiting != null) {
        return waiting!.future;
      }
      return http.Response(jsonEncode(response), status);
    }),
  );
  Future<void> login() => client.login('TEST001', 'password');
  late final service = NetworkVerificationApi(client);
}

class ScreenApi extends NetworkVerificationApi {
  String code = 'NETWORK_AUTHORIZED';
  int calls = 0;
  Object? error;
  Completer<Map<String, dynamic>>? wait;
  @override
  Future<Map<String, dynamic>> check() async {
    calls++;
    if (error != null) {
      throw error!;
    }
    return wait?.future ?? result(code);
  }
}

void main() {
  test(
    'Sends empty authenticated request and displays server decision only',
    () async {
      final f = Fixture();
      await f.login();
      expect((await f.service.check())['result'], 'PASS');
      f.response = result('NETWORK_NOT_AUTHORIZED');
      expect((await f.service.check())['result'], 'FAIL');
      expect(f.calls, 2);
    },
  );
  test(
    'Incompatible or unbound PASS cannot be displayed as authorization',
    () async {
      final f = Fixture();
      await f.login();
      for (final mutation in [
        {'matched_policy_id': null},
        {'attendance_authorized': true},
        {'operation': 'attendance_authorization'},
        {'reason_code': 'NETWORK_NOT_AUTHORIZED'},
      ]) {
        f.response = {...result(), ...mutation};
        await expectLater(f.service.check(), throwsA(isA<ApiException>()));
      }
    },
  );
  test('No login or network/API failure never yields PASS', () async {
    final f = Fixture();
    await expectLater(f.service.check(), throwsA(isA<ApiException>()));
    expect(f.calls, 0);
    await f.login();
    f.offline = true;
    await expectLater(f.service.check(), throwsA(isA<ApiException>()));
  });
  test('Changed login during request discards old response', () async {
    final f = Fixture();
    await f.login();
    f.waiting = Completer<http.Response>();
    final expectation = expectLater(
      f.service.check(),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'SESSION_CHANGED'),
      ),
    );
    await Future<void>.delayed(Duration.zero);
    await f.login();
    f.waiting!.complete(http.Response(jsonEncode(result()), 200));
    await expectation;
  });
  testWidgets('Bounded timeout stops waiting and never accepts PASS', (
    tester,
  ) async {
    final f = Fixture();
    await f.login();
    f.waiting = Completer<http.Response>();
    final checked = expectLater(
      f.service.check(),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          'NETWORK_CHECK_TIMEOUT',
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 16));
    await checked;
    f.waiting!.complete(http.Response(jsonEncode(result()), 200));
    await tester.pump();
  });
  for (final size in [const Size(390, 844), const Size(1280, 800)]) {
    testWidgets('Server PASS/FAIL and guidance fit $size', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ScreenApi();
      await tester.pumpWidget(
        MaterialApp(home: NetworkVerificationScreen(api: api)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Network verification: PASS'), findsOneWidget);
      expect(
        tester
            .widgetList<InfoNotice>(find.byType(InfoNotice))
            .where((notice) => !notice.warning),
        isEmpty,
      );
      expect(
        find.textContaining('Backend-observed source IP: 192.0.2.10'),
        findsOneWidget,
      );
      api.code = 'LOOPBACK_SOURCE_NOT_AUTHORIZED';
      await tester.scrollUntilVisible(
        find.text('Check current connection'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Check current connection'));
      await tester.pumpAndSettle();
      // The new classroom card extends the scrollable page. Inspect the CIDR
      // result at the top rather than assuming it remains in the lazy viewport.
      await tester.drag(find.byType(ListView), const Offset(0, 1000));
      await tester.pumpAndSettle();
      expect(find.text('Network verification: PASS'), findsNothing);
      expect(find.text('Network verification: FAIL'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('Failure stops spinner and remains retryable', (tester) async {
    final api = ScreenApi()
      ..error = const ApiException('Network API unavailable.', 503);
    await tester.pumpWidget(
      MaterialApp(home: NetworkVerificationScreen(api: api)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Network API unavailable.'), findsOneWidget);
    expect(find.text('Network verification: FAIL'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.text('Network verification: PASS'), findsNothing);
  });
  for (final error in [
    const SocketException('Connection refused'),
    const SocketException('Failed host lookup'),
    http.ClientException('Server unreachable'),
    TimeoutException('No response'),
  ]) {
    testWidgets('Transport $error displays FAIL without a CIDR decision', (
      tester,
    ) async {
      final f = Fixture();
      await f.login();
      f.transportError = error;
      await tester.pumpWidget(
        MaterialApp(home: NetworkVerificationScreen(api: f.service)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Network verification: FAIL'), findsOneWidget);
      expect(
        find.text(NetworkVerificationFailure.unreachableMessage),
        findsOneWidget,
      );
      expect(
        find.text('Reason: VERIFICATION_SERVER_UNREACHABLE'),
        findsOneWidget,
      );
      expect(find.text('Reason: NETWORK_NOT_AUTHORIZED'), findsNothing);
      expect(find.textContaining('Backend-observed source IP:'), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  }
  testWidgets('Actual bounded timeout becomes FAIL; late PASS is discarded', (
    tester,
  ) async {
    final f = Fixture();
    await f.login();
    f.waiting = Completer<http.Response>();
    await tester.pumpWidget(
      MaterialApp(home: NetworkVerificationScreen(api: f.service)),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 16));
    await tester.pump();
    expect(find.text('Network verification: FAIL'), findsOneWidget);
    expect(
      find.text(NetworkVerificationFailure.unreachableMessage),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsNothing);
    f.waiting!.complete(http.Response(jsonEncode(result()), 200));
    await tester.pumpAndSettle();
    expect(find.text('Network verification: PASS'), findsNothing);
    expect(find.text('Network verification: FAIL'), findsOneWidget);
  });
  testWidgets('HTTP rejection preserves actual backend code and message', (
    tester,
  ) async {
    final f = Fixture();
    await f.login();
    f.status = 403;
    f.response = {
      'success': false,
      'code': 'NETWORK_NOT_AUTHORIZED',
      'message': 'Outside the enabled school CIDR policy.',
    };
    await tester.pumpWidget(
      MaterialApp(home: NetworkVerificationScreen(api: f.service)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Network verification: FAIL'), findsOneWidget);
    expect(find.text('Reason: NETWORK_NOT_AUTHORIZED'), findsOneWidget);
    expect(
      find.text('Outside the enabled school CIDR policy.'),
      findsOneWidget,
    );
    expect(
      find.text(NetworkVerificationFailure.unreachableMessage),
      findsNothing,
    );
  });
  testWidgets('Resume discards stale PASS and performs fresh request', (
    tester,
  ) async {
    final api = ScreenApi();
    await tester.pumpWidget(
      MaterialApp(home: NetworkVerificationScreen(api: api)),
    );
    await tester.pumpAndSettle();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    api.wait = Completer<Map<String, dynamic>>();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(find.text('Network verification: PASS'), findsNothing);
    expect(find.byKey(const ValueKey('cidr-progress')), findsOneWidget);
    api.wait!.complete(result('NETWORK_NOT_AUTHORIZED'));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView), const Offset(0, 1000));
    await tester.pumpAndSettle();
    expect(api.calls, 2);
    expect(find.text('Network verification: FAIL'), findsOneWidget);
  });
}
