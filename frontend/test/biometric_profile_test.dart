// Module owner: Chew Zhexuan
// Module: Facial Recognition and Liveness Detection
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/student_profile_screen.dart';
import 'package:frontend/services/api_client.dart';

class ProfileApi extends ApiClient {
  ProfileApi(String status) {
    student = {
      'student_id': 'TEST001',
      'name': 'Test Student',
      'biometric_status': status,
    };
  }

  @override
  Future<void> refreshStudent() async {}
}

void main() {
  late ApiClient original;
  setUp(() => original = ApiClient.instance);
  tearDown(() => ApiClient.instance = original);

  Future<void> showProfile(WidgetTester tester, String status) async {
    ApiClient.instance = ProfileApi(status);
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: StudentProfileScreen())),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Registered students see department guidance without face actions',
    (tester) async {
      await showProfile(tester, 'active');
      expect(find.text('Face registered'), findsOneWidget);
      expect(find.text('Remove face registration'), findsNothing);
      expect(find.text('Register my face'), findsNothing);
      expect(find.byIcon(Icons.delete_outline), findsNothing);
      expect(
        find.textContaining('ask your lecturer to record attendance manually'),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.textContaining('facial data removal requests'),
        150,
      );
      expect(
        find.textContaining('facial data removal requests'),
        findsOneWidget,
      );
    },
  );

  testWidgets('First-time students retain face enrollment', (tester) async {
    await showProfile(tester, 'not_registered');
    expect(find.text('Register my face'), findsOneWidget);
    expect(find.textContaining('Register your own face once'), findsOneWidget);
    expect(find.text('Remove face registration'), findsNothing);
  });

  testWidgets('Inactive registration directs students to the department', (
    tester,
  ) async {
    await showProfile(tester, 'inactive');
    expect(find.text('Contact your department'), findsOneWidget);
    expect(find.text('Register my face'), findsNothing);
  });
}
