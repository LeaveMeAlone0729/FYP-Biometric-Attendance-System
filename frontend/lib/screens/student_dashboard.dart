import 'package:flutter/material.dart';
import '../theme.dart';
import 'portal_home_screen.dart';
import 'portal_student_screen.dart';
import 'portal_services.dart';

class StudentDashboard extends StatefulWidget {
  const StudentDashboard({super.key});
  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  int _index = 0;
  void _select(int index) => setState(() => _index = index);
  @override
  Widget build(BuildContext context) => Scaffold(
    body: switch (_index) {
      0 => PortalHomeScreen(onStudent: () => _select(1)),
      1 => const PortalStudentScreen(),
      2 => const UniversityAudienceScreen(staff: true),
      _ => const UniversityAudienceScreen(staff: false),
    },
    bottomNavigationBar: DecoratedBox(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Color(0xFFE8E8E8), width: .7)),
      ),
      child: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        currentIndex: _index,
        onTap: _select,
        backgroundColor: Colors.white,
        elevation: 0,
        selectedItemColor: _index == 0 ? portalPurple : universityBlue,
        unselectedItemColor: const Color(0xFF777777),
        selectedLabelStyle: const TextStyle(
          fontFamily: 'PatrickHand',
          fontSize: 14,
        ),
        unselectedLabelStyle: const TextStyle(
          fontFamily: 'PatrickHand',
          fontSize: 14,
        ),
        items: [
          _item(Icons.home, 'Home', 0),
          _item(Icons.person, 'Student', 1),
          _item(Icons.badge, 'Staff', 2),
          _item(Icons.school, 'Alumni', 3),
        ],
      ),
    ),
  );

  BottomNavigationBarItem _item(IconData icon, String title, int index) =>
      BottomNavigationBarItem(
        label: title,
        icon: Icon(icon, size: 29),
        activeIcon: Container(
          width: 33,
          height: 33,
          decoration: BoxDecoration(
            color: index == 0 ? portalPurple : universityBlue,
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: Colors.white, size: 25),
        ),
      );
}
