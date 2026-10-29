import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/screens/student_dashboard.dart';
import 'package:frontend/screens/portal_attendance_screen.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/theme.dart';

void main() {
  const student = {
    'name': 'Test Student',
    'student_id': 'TEST001',
    'email': 'test@example.test',
    'group_id': 1,
    'group_name': 'DEMO-A',
    'programme_code': 'DEMO',
    'biometric_status': 'not_registered',
  };
  setUp(() {
    ApiClient.instance = ApiClient(
      client: MockClient((request) async {
        dynamic data;
        switch (request.url.path) {
          case '/config':
            data = {
              'demo_mode': true,
              'server_time': '2026-10-20T12:00:00+08:00',
            };
          case '/me':
            data = student;
          case '/attendance/history':
            data = [
              {
                'course_code': 'CS101',
                'course_name': 'Today course',
                'session_date': '2026-10-20',
                'taken_at': '2026-10-20T10:00:00+08:00',
                'status': 'Present',
              },
              {
                'course_code': 'CS102',
                'course_name': 'Yesterday course',
                'session_date': '2026-10-19',
                'taken_at': '2026-10-19T10:00:00+08:00',
                'status': 'Present',
              },
            ];
          case '/attendance/summary':
            data = [
              {
                'course_name': 'Database course',
                'attended': 3,
                'total': 4,
                'percentage': 75.0,
              },
            ];
          default:
            data = [];
        }
        return http.Response(jsonEncode(data), 200);
      }),
    );
    ApiClient.instance.student = Map<String, dynamic>.from(student);
  });

  void phone(WidgetTester tester, double width) {
    tester.view.physicalSize = Size(width * 3, 2400);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  for (final width in [360.0, 448.0]) {
    testWidgets('Reference home and shortcut grid fit a $width pixel phone', (
      tester,
    ) async {
      phone(tester, width);
      await tester.pumpWidget(
        MaterialApp(theme: appTheme(), home: const StudentDashboard()),
      );
      await tester.pumpAndSettle();
      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Student'), findsOneWidget);
      expect(find.text('Staff'), findsOneWidget);
      expect(find.text('Alumni'), findsOneWidget);
      expect(find.text('20-10'), findsOneWidget);
      expect(find.text('Tuesday'), findsOneWidget);
      expect(find.text('Online\nApplication'), findsOneWidget);
      expect(find.text('KL Campus\nVirtual Tour'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets(
    'Student card opens the reference attendance tabs and uses the real daily count',
    (tester) async {
      phone(tester, 448);
      await tester.pumpWidget(
        MaterialApp(theme: appTheme(), home: const StudentDashboard()),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Student'));
      await tester.pumpAndSettle();
      expect(find.text('TEST STUDENT'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('Class Timetable'), findsOneWidget);
      await tester.tap(find.text('Attendance'));
      await tester.pumpAndSettle();
      expect(find.text('REGISTRATION'), findsOneWidget);
      expect(find.text('TODAY'), findsOneWidget);
      expect(find.text('OVERALL'), findsOneWidget);
      expect(find.byKey(const ValueKey('submit-attendance')), findsOneWidget);
    },
  );

  testWidgets(
    'Today filters by academic date and overall shows API percentages',
    (tester) async {
      phone(tester, 448);
      await tester.pumpWidget(
        MaterialApp(theme: appTheme(), home: const PortalAttendanceScreen()),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('TODAY'));
      await tester.pumpAndSettle();
      expect(find.text('Today course'), findsOneWidget);
      expect(find.text('Yesterday course'), findsNothing);
      await tester.tap(find.text('OVERALL'));
      await tester.pumpAndSettle();
      expect(find.text('Database course'), findsOneWidget);
      expect(find.text('75%'), findsOneWidget);
      expect(find.text('3 / 4 classes attended'), findsOneWidget);
    },
  );
}
