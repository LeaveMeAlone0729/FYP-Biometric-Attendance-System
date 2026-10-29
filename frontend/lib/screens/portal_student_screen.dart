import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'camera_screen.dart';
import 'history_screen.dart';
import 'portal_attendance_screen.dart';
import 'portal_services.dart';

class PortalStudentScreen extends StatefulWidget {
  const PortalStudentScreen({super.key});
  @override
  State<PortalStudentScreen> createState() => _PortalStudentScreenState();
}

class _PortalStudentScreenState extends State<PortalStudentScreen> {
  final _api = ApiClient.instance;
  int? _todayCount;
  String? _error;
  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final data = await Future.wait([
        _api.get('/attendance/history'),
        _api.loadConfig(),
        _api.refreshStudent(),
      ]);
      final day = (_api.config['server_time'] as String?)?.substring(0, 10);
      if (mounted) {
        setState(() {
          _todayCount = (data.first as List)
              .where((row) => row['session_date'] == day)
              .length;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _attendance() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => const PortalAttendanceScreen()),
    );
    if (mounted) _refresh();
  }

  Future<void> _face() async {
    if (_api.student?['biometric_status'] == 'active') {
      openAccountSettings(context);
      return;
    }
    await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const CameraScreen(enrollment: true)),
    );
    if (mounted) _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final student = _api.student ?? {};
    final name = student['name'] as String? ?? 'Student';
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          SizedBox(
            height: 265,
            child: Stack(
              children: [
                Container(
                  height: 205,
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.bottomLeft,
                      end: Alignment.topRight,
                      colors: [Color(0xFF1550A7), Color(0xFF001021)],
                    ),
                  ),
                ),
                Positioned(
                  left: 20,
                  right: 18,
                  top: 24,
                  child: InkWell(
                    onTap: () => openAccountSettings(context),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 76,
                          height: 76,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: const Color(0xFFBAC8CE),
                              width: 2,
                            ),
                          ),
                          child: const Icon(
                            Icons.person,
                            size: 57,
                            color: Color(0xFF8298AD),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                name.toUpperCase(),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 21,
                                  height: 1.15,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                student['student_id'] as String? ?? '',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 16,
                                ),
                              ),
                              Text(
                                student['email'] as String? ?? '',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 15,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  left: 20,
                  right: 20,
                  top: 157,
                  child: IntrinsicHeight(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(
                          child: _summary(
                            Icons.check_box_outlined,
                            'Attendance',
                            'Today Attendance',
                            _todayCount?.toString() ?? '–',
                            _attendance,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _summary(
                            Icons.attach_money,
                            'Billing',
                            'Pending Payment',
                            '–',
                            () => showUniversityService(
                              context,
                              'Billing',
                              'View your current fees and payment records in the university student intranet.',
                              icon: Icons.payments_outlined,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: InfoNotice(_error!, warning: true),
            ),
          _menu(
            Icons.notifications,
            'Announcement',
            () => openUniversityLink(context, universityNews),
          ),
          _menu(
            Icons.calendar_month,
            'Class Timetable',
            () => Navigator.push<void>(
              context,
              MaterialPageRoute(builder: (_) => const TimetableScreen()),
            ),
          ),
          _menu(
            Icons.event_note,
            'Examination Timetable',
            () => showUniversityService(
              context,
              'Examination Timetable',
              'View your examination dates and venues through the university examination services.',
              url: 'https://examination.tarc.edu.my/',
              icon: Icons.event_note,
            ),
          ),
          _menu(
            Icons.assignment_outlined,
            'Examination Result',
            () => showUniversityService(
              context,
              'Examination Result',
              'Sign in to the university student intranet to view your examination results.',
              icon: Icons.assignment_outlined,
            ),
          ),
          _menu(
            Icons.g_mobiledata,
            'Google Classroom',
            () => openUniversityLink(context, 'https://classroom.google.com/'),
            iconSize: 38,
          ),
          _menu(
            Icons.event_available_outlined,
            'Facility Booking',
            () => showUniversityService(
              context,
              'Facility Booking',
              'Sign in to the university student intranet to access facility bookings.',
              icon: Icons.event_available_outlined,
            ),
          ),
          _menu(
            Icons.sports_basketball,
            'Sports Facilities Booking',
            () => showUniversityService(
              context,
              'Sports Facilities Booking',
              'Access the university student intranet to check sports facilities and booking availability.',
              icon: Icons.sports_basketball,
            ),
          ),
          _menu(
            Icons.account_balance_wallet_outlined,
            'Financial Support',
            () => openUniversityLink(
              context,
              'https://www.tarc.edu.my/dsa/financial-aid/financial-aid/',
            ),
          ),
          _menu(
            Icons.phone,
            'Helpline',
            () => openUniversityLink(context, universityContact),
          ),
          _menu(
            Icons.favorite_border,
            'Intellect',
            () => showUniversityService(
              context,
              'Intellect',
              'Explore student support and wellbeing services through the university portal.',
              icon: Icons.favorite_border,
            ),
          ),
          const Divider(height: 16, thickness: .6),
          _menu(Icons.face_retouching_natural, 'Register Face', _face),
          _menu(
            Icons.fact_check_outlined,
            'Verification Activity',
            () => Navigator.push<void>(
              context,
              MaterialPageRoute(
                builder: (_) => Scaffold(
                  appBar: universityAppBar('Attendance History'),
                  body: const HistoryScreen(),
                ),
              ),
            ),
          ),
          _menu(
            Icons.manage_accounts_outlined,
            'Account & Sign Out',
            () => openAccountSettings(context),
          ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _summary(
    IconData icon,
    String title,
    String caption,
    String value,
    VoidCallback action,
  ) => Material(
    color: Colors.white,
    borderRadius: BorderRadius.circular(12),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: action,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 15, 10, 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 30, color: universityBlue),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(title, style: const TextStyle(fontSize: 17)),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(caption, style: const TextStyle(fontSize: 15)),
            Text(
              value,
              style: const TextStyle(
                color: Color(0xFFDB6C7B),
                fontFamily: 'Roboto',
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    ),
  );

  Widget _menu(
    IconData icon,
    String title,
    VoidCallback action, {
    double iconSize = 27,
  }) => ListTile(
    minLeadingWidth: 38,
    contentPadding: const EdgeInsets.symmetric(horizontal: 28),
    leading: Icon(icon, color: universityBlue, size: iconSize),
    title: Text(title, style: const TextStyle(fontSize: 21)),
    trailing: const Icon(Icons.arrow_right, color: Colors.black, size: 26),
    onTap: action,
  );
}
