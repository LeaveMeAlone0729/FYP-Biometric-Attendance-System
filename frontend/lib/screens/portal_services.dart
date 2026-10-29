import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'student_profile_screen.dart';

const studentIntranet = 'https://web.tarc.edu.my';
const staffIntranet = 'https://portal.tarc.edu.my';
const universityNews =
    'https://www.tarc.edu.my/news_archive/highlights/highlights-news/subcontent/';
const universityAdmissions = 'https://www.tarc.edu.my/admissions/index.jsp';
const universityLibrary = 'https://library.tarc.edu.my/';
const universityContact = 'https://www.tarc.edu.my/contact-us/';

Future<void> openUniversityLink(BuildContext context, String address) async {
  try {
    if (!await launchUrl(
      Uri.parse(address),
      mode: LaunchMode.externalApplication,
    )) {
      throw Exception('Unable to open the university website.');
    }
  } catch (_) {
    if (!context.mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('University website'),
        content: SelectableText(
          'Open this address in your browser:\n\n$address',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

void openAccountSettings(BuildContext context) => Navigator.push<void>(
  context,
  MaterialPageRoute(
    builder: (_) => Scaffold(
      appBar: universityAppBar('Account & biometrics'),
      body: const StudentProfileScreen(),
    ),
  ),
);

AppBar universityAppBar(
  String title, {
  List<Widget>? actions,
  PreferredSizeWidget? bottom,
}) => AppBar(
  backgroundColor: universityBlue,
  foregroundColor: Colors.white,
  elevation: 2,
  title: Text(
    title,
    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.normal),
  ),
  actions: actions,
  bottom: bottom,
);

void showUniversityService(
  BuildContext context,
  String title,
  String description, {
  String url = studentIntranet,
  IconData icon = Icons.school_outlined,
}) {
  Navigator.push<void>(
    context,
    MaterialPageRoute(
      builder: (_) => Scaffold(
        appBar: universityAppBar(title),
        body: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 24),
              Icon(icon, size: 52, color: universityBlue),
              const SizedBox(height: 24),
              Text(title, style: const TextStyle(fontSize: 28)),
              const SizedBox(height: 14),
              Text(description, style: const TextStyle(fontSize: 19)),
              const SizedBox(height: 28),
              FilledButton.icon(
                onPressed: () => openUniversityLink(context, url),
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Open university portal'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class UniversityCrest extends StatelessWidget {
  const UniversityCrest({super.key, this.width = 38});
  final double width;
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'TAR UMT crest',
    image: true,
    child: ClipRect(
      child: SizedBox(
        width: width,
        height: width * 1.25,
        child: OverflowBox(
          alignment: Alignment.topLeft,
          minWidth: width * 4.78,
          maxWidth: width * 4.78,
          minHeight: width * 1.56,
          maxHeight: width * 1.56,
          child: Image.asset(
            'assets/portal/tarumt-logo.png',
            width: width * 4.78,
            height: width * 1.56,
            fit: BoxFit.fill,
          ),
        ),
      ),
    ),
  );
}

class TimetableScreen extends StatefulWidget {
  const TimetableScreen({super.key});
  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  late Future<dynamic> _classes;
  @override
  void initState() {
    super.initState();
    _classes = ApiClient.instance.get('/classes');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: universityAppBar('Class Timetable'),
    body: FutureBuilder<dynamic>(
      future: _classes,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: InfoNotice(snapshot.error.toString(), warning: true),
            ),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final rows = snapshot.data as List;
        if (rows.isEmpty) {
          return const Center(
            child: Text(
              'No classes scheduled.',
              style: TextStyle(fontSize: 22),
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: () async {
            setState(() => _classes = ApiClient.instance.get('/classes'));
            await _classes;
          },
          child: ListView.separated(
            padding: const EdgeInsets.all(18),
            itemCount: rows.length,
            separatorBuilder: (_, _) => const SizedBox(height: 14),
            itemBuilder: (_, index) {
              final row = rows[index] as Map;
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${row['course_code']} · ${row['course_name']}',
                        style: const TextStyle(
                          fontSize: 21,
                          color: universityBlue,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${row['date']}   ${(row['start_time'] as String).substring(0, 5)} – ${(row['end_time'] as String).substring(0, 5)}',
                      ),
                      Text('${row['class_type']} · ${row['venue']}'),
                      Text(row['lecturer'] as String),
                      if (row['attended'] == true)
                        const Padding(
                          padding: EdgeInsets.only(top: 8),
                          child: Text(
                            'Attendance recorded',
                            style: TextStyle(color: Color(0xFF16834E)),
                          ),
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        );
      },
    ),
  );
}

class UniversityAudienceScreen extends StatelessWidget {
  const UniversityAudienceScreen({super.key, required this.staff});
  final bool staff;
  @override
  Widget build(BuildContext context) => ListView(
    children: [
      Container(
        height: 190,
        padding: const EdgeInsets.all(24),
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF174C98), Color(0xFF00101F)],
          ),
        ),
        child: SafeArea(
          bottom: false,
          child: Row(
            children: [
              Icon(
                staff ? Icons.badge : Icons.school,
                size: 64,
                color: Colors.white,
              ),
              const SizedBox(width: 22),
              Text(
                staff ? 'Staff' : 'Alumni',
                style: const TextStyle(fontSize: 32, color: Colors.white),
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 14),
      ListTile(
        leading: Icon(
          staff ? Icons.account_circle : Icons.school,
          color: universityBlue,
        ),
        title: Text(
          staff ? 'Staff Intranet' : 'Alumni Relations',
          style: const TextStyle(fontSize: 22),
        ),
        trailing: const Icon(Icons.open_in_new, size: 20),
        onTap: () => openUniversityLink(
          context,
          staff ? staffIntranet : 'https://dar.tarc.edu.my/',
        ),
      ),
      ListTile(
        leading: const Icon(Icons.campaign, color: universityBlue),
        title: const Text('University News', style: TextStyle(fontSize: 22)),
        trailing: const Icon(Icons.arrow_right),
        onTap: () => openUniversityLink(context, universityNews),
      ),
      ListTile(
        leading: const Icon(Icons.phone, color: universityBlue),
        title: const Text('Contact Us', style: TextStyle(fontSize: 22)),
        trailing: const Icon(Icons.arrow_right),
        onTap: () => openUniversityLink(context, universityContact),
      ),
    ],
  );
}
