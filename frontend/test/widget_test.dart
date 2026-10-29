import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/main.dart';
import 'package:frontend/screens/attendance_flow_screen.dart';
import 'package:frontend/screens/history_screen.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/theme.dart';
import 'package:frontend/screens/camera_screen.dart';

void main() {
  testWidgets(
    'Missing front camera blocks capture and gives an actionable error',
    (tester) async {
      ApiClient.instance = ApiClient();
      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme(),
          home: CameraScreen(enrollment: true, cameraLoader: () async => []),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('CAMERA UNAVAILABLE'), findsOneWidget);
      expect(
        find.text(
          'A front-facing camera is required. Enable it on your phone or emulator.',
        ),
        findsOneWidget,
      );
      expect(find.text('Capture & register face'), findsNothing);
      expect(
        find.text('Give consent below to start your automatic face scan.'),
        findsOneWidget,
      );
    },
  );
  setUp(() {
    ApiClient.instance = ApiClient(
      client: MockClient((request) async {
        if (request.url.path == '/config') {
          return http.Response(
            jsonEncode({
              'demo_mode': true,
              'server_time': '2026-10-20T12:00:00+08:00',
            }),
            200,
          );
        }
        if (request.url.path == '/groups') {
          return http.Response(
            '[{"group_id":1,"group_name":"DEMO-A","programme_code":"DEMO"}]',
            200,
          );
        }
        return http.Response('[]', 200);
      }),
    );
  });

  testWidgets(
    'Sign in validates fields and offers clearly marked demo signup',
    (tester) async {
      await tester.pumpWidget(const MyApp());
      await tester.pumpAndSettle();
      expect(find.text('Welcome back.'), findsOneWidget);
      expect(find.textContaining('Demo environment'), findsOneWidget);
      await tester.ensureVisible(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pumpAndSettle();
      expect(
        find.text('Enter a student ID with 3–11 letters or digits.'),
        findsOneWidget,
      );
      expect(find.text('Enter your password.'), findsOneWidget);
      await tester.ensureVisible(find.text('New here? Create a demo account'));
      await tester.tap(find.text('New here? Create a demo account'));
      await tester.pumpAndSettle();
      expect(find.text('Full name'), findsOneWidget);
      expect(find.text('Demo student group'), findsOneWidget);
    },
  );

  testWidgets('PIN keypad requires six digits and supports delete and clear', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2200);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    ApiClient.instance.config = {'demo_mode': true};
    ApiClient.instance.student = {'group_id': 1};
    await tester.pumpWidget(
      MaterialApp(
        theme: appTheme(),
        home: const Scaffold(body: AttendanceFlowScreen()),
      ),
    );
    final button = find.byKey(const ValueKey('submit-attendance'));
    expect(tester.widget<IconButton>(button).onPressed, isNull);
    for (final digit in ['1', '2', '3', '4', '5', '6']) {
      await tester.tap(find.text(digit).last);
      await tester.pump();
    }
    expect(tester.widget<IconButton>(button).onPressed, isNotNull);
    await tester.tap(find.byIcon(Icons.backspace_outlined));
    await tester.pump();
    expect(tester.widget<IconButton>(button).onPressed, isNull);
    await tester.longPress(find.byIcon(Icons.backspace_outlined));
    await tester.pump();
    expect(find.text(''), findsNWidgets(6));
    expect(
      find.textContaining('Use the PIN provided for your class'),
      findsOneWidget,
    );
  });

  testWidgets('PIN failure is displayed without navigating to camera', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    ApiClient.instance = ApiClient(
      client: MockClient(
        (request) async => http.Response(
          '{"message":"The PIN does not match an active class for your group."}',
          400,
        ),
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: appTheme(),
        home: const Scaffold(body: AttendanceFlowScreen()),
      ),
    );
    for (final digit in ['1', '2', '3', '4', '5', '6']) {
      await tester.tap(find.text(digit).last);
      await tester.pump();
    }
    await tester.ensureVisible(find.byKey(const ValueKey('submit-attendance')));
    await tester.tap(find.byKey(const ValueKey('submit-attendance')));
    await tester.pumpAndSettle();
    expect(
      find.text('The PIN does not match an active class for your group.'),
      findsOneWidget,
    );
    expect(find.text('Checking class…'), findsNothing);
  });

  testWidgets(
    'History renders real empty states instead of sample percentages',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme(),
          home: const Scaffold(body: HistoryScreen()),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('No attendance recorded yet.'), findsOneWidget);
      await tester.tap(find.text('By course'));
      await tester.pumpAndSettle();
      expect(
        find.text('Course summaries appear after classes finish.'),
        findsOneWidget,
      );
      expect(find.text('75%'), findsNothing);
    },
  );
}
