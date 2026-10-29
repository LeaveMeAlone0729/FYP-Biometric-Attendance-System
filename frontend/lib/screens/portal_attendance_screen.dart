import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'attendance_flow_screen.dart';
import 'portal_services.dart';

class PortalAttendanceScreen extends StatefulWidget {
  const PortalAttendanceScreen({super.key});
  @override
  State<PortalAttendanceScreen> createState() => _PortalAttendanceScreenState();
}

class _PortalAttendanceScreenState extends State<PortalAttendanceScreen> {
  int _revision = 0;
  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 3,
    child: Scaffold(
      appBar: universityAppBar(
        'Attendance',
        actions: [
          IconButton(
            tooltip: 'Attendance information',
            icon: const Icon(Icons.info_outline),
            onPressed: () => showDialog<void>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Attendance Registration'),
                content: const Text(
                  'Enter the six-digit class code, verify your face, then complete the requested hand gesture. Attendance is recorded only after all checks pass.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('OK'),
                  ),
                ],
              ),
            ),
          ),
        ],
        bottom: const TabBar(
          indicatorColor: Colors.white,
          indicatorWeight: 2,
          labelColor: Colors.white,
          unselectedLabelColor: Color(0xFF9CA8BD),
          labelStyle: TextStyle(fontFamily: 'PatrickHand', fontSize: 15),
          tabs: [
            Tab(text: 'REGISTRATION'),
            Tab(text: 'TODAY'),
            Tab(text: 'OVERALL'),
          ],
        ),
      ),
      body: TabBarView(
        children: [
          AttendanceFlowScreen(onRecorded: () => setState(() => _revision++)),
          AttendanceTodayView(key: ValueKey('today-$_revision')),
          AttendanceOverallView(key: ValueKey('overall-$_revision')),
        ],
      ),
    ),
  );
}

class AttendanceTodayView extends StatefulWidget {
  const AttendanceTodayView({super.key});
  @override
  State<AttendanceTodayView> createState() => _AttendanceTodayViewState();
}

class _AttendanceTodayViewState extends State<AttendanceTodayView> {
  late Future<List<dynamic>> _records;
  @override
  void initState() {
    super.initState();
    _records = _load();
  }

  Future<List<dynamic>> _load() async {
    final api = ApiClient.instance;
    final data = await Future.wait([
      api.get('/attendance/history'),
      api.loadConfig(),
    ]);
    final day = (api.config['server_time'] as String?)?.substring(0, 10);
    return (data.first as List)
        .where((row) => row['session_date'] == day)
        .toList();
  }

  @override
  Widget build(BuildContext context) => _AttendanceDataList(
    future: _records,
    onRefresh: () async {
      setState(() => _records = _load());
      await _records;
    },
    empty: 'No Record Found!',
    builder: (row) => ListTile(
      contentPadding: const EdgeInsets.all(16),
      leading: const Icon(
        Icons.check_box_outlined,
        color: universityBlue,
        size: 32,
      ),
      title: Text(
        row['course_name'] as String,
        style: const TextStyle(fontSize: 21),
      ),
      subtitle: Text(
        '${row['course_code']}\n${friendlyTime(row['taken_at'] as String?)}',
        style: const TextStyle(fontSize: 16),
      ),
      trailing: Text(
        row['status'] as String,
        style: const TextStyle(color: Color(0xFF19834C), fontSize: 17),
      ),
    ),
  );
}

class AttendanceOverallView extends StatefulWidget {
  const AttendanceOverallView({super.key});
  @override
  State<AttendanceOverallView> createState() => _AttendanceOverallViewState();
}

class _AttendanceOverallViewState extends State<AttendanceOverallView> {
  late Future<List<dynamic>> _summary;
  Future<List<dynamic>> _load() async => List<dynamic>.from(
    await ApiClient.instance.get('/attendance/summary') as List,
  );
  @override
  void initState() {
    super.initState();
    _summary = _load();
  }

  @override
  Widget build(BuildContext context) => _AttendanceDataList(
    future: _summary,
    onRefresh: () async {
      setState(() => _summary = _load());
      await _summary;
    },
    empty: 'No completed class sessions yet.',
    builder: (row) {
      final percent = (row['percentage'] as num).toDouble();
      final color = percent >= 80
          ? const Color(0xFF19834C)
          : percent >= 50
          ? const Color(0xFFE19724)
          : const Color(0xFFD24D58);
      return Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    row['course_name'] as String,
                    style: const TextStyle(fontSize: 21, color: universityBlue),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '${row['attended']} / ${row['total']} classes attended',
                    style: const TextStyle(fontSize: 16),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            SizedBox(
              width: 58,
              height: 58,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 58,
                    height: 58,
                    child: CircularProgressIndicator(
                      value: percent / 100,
                      color: color,
                      backgroundColor: color.withValues(alpha: .12),
                      strokeWidth: 4,
                    ),
                  ),
                  Text(
                    '${percent.toStringAsFixed(percent == percent.roundToDouble() ? 0 : 1)}%',
                    style: TextStyle(fontSize: 17, color: color),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    },
  );
}

class _AttendanceDataList extends StatelessWidget {
  const _AttendanceDataList({
    required this.future,
    required this.onRefresh,
    required this.empty,
    required this.builder,
  });
  final Future<List<dynamic>> future;
  final Future<void> Function() onRefresh;
  final String empty;
  final Widget Function(dynamic) builder;
  @override
  Widget build(BuildContext context) => FutureBuilder<List<dynamic>>(
    future: future,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                InfoNotice(snapshot.error.toString(), warning: true),
                TextButton(onPressed: onRefresh, child: const Text('Retry')),
              ],
            ),
          ),
        );
      }
      if (!snapshot.hasData) {
        return const Center(child: CircularProgressIndicator());
      }
      final rows = snapshot.data!;
      return RefreshIndicator(
        onRefresh: onRefresh,
        child: rows.isEmpty
            ? LayoutBuilder(
                builder: (context, constraints) => ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  children: [
                    SizedBox(
                      height: constraints.maxHeight,
                      child: Center(
                        child: Text(
                          empty,
                          style: const TextStyle(fontSize: 23),
                        ),
                      ),
                    ),
                  ],
                ),
              )
            : ListView.separated(
                padding: const EdgeInsets.all(18),
                itemCount: rows.length,
                separatorBuilder: (_, _) => const SizedBox(height: 14),
                itemBuilder: (_, index) => Card(child: builder(rows[index])),
              ),
      );
    },
  );
}
