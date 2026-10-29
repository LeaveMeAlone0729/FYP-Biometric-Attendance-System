import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<dynamic> _history = [], _summary = [], _attempts = [];
  bool _loading = true;
  String? _error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final api = ApiClient.instance;
      final data = await Future.wait([
        api.get('/attendance/history'),
        api.get('/attendance/summary'),
        api.get('/verification-attempts'),
      ]);
      if (mounted) {
        setState(() {
          _history = data[0] as List;
          _summary = data[1] as List;
          _attempts = data[2] as List;
          _loading = false;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 3,
    child: SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 24, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your attendance',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 7),
                      const Text('Recorded classes and verification activity'),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: _load,
                  tooltip: 'Refresh attendance',
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
          ),
          const TabBar(
            tabs: [
              Tab(text: 'Records'),
              Tab(text: 'By course'),
              Tab(text: 'Activity'),
            ],
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: InfoNotice(_error!, warning: true),
                    ),
                  )
                : TabBarView(
                    children: [
                      _list(
                        _history,
                        'No attendance recorded yet.',
                        (r) => ListTile(
                          contentPadding: const EdgeInsets.all(16),
                          leading: const CircleAvatar(
                            backgroundColor: Color(0xFFE5F3F0),
                            child: Icon(Icons.check_rounded, color: teal),
                          ),
                          title: Text(
                            r['course_name'] as String,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            '${r['course_code']}\n${friendlyTime(r['taken_at'] as String?)}\nVerification #${r['verification_id']}',
                            style: const TextStyle(fontSize: 12),
                          ),
                          isThreeLine: true,
                          trailing: Text(
                            r['status'] as String,
                            style: const TextStyle(
                              color: teal,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),
                      _list(
                        _summary,
                        'Course summaries appear after classes finish.',
                        (r) => Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                r['course_name'] as String,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: ink,
                                ),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                '${r['attended']} of ${r['total']} eligible classes attended · ${r['percentage']}%',
                              ),
                              const SizedBox(height: 14),
                              LinearProgressIndicator(
                                value:
                                    (r['percentage'] as num).toDouble() / 100,
                                minHeight: 7,
                                borderRadius: BorderRadius.circular(6),
                              ),
                            ],
                          ),
                        ),
                      ),
                      _list(
                        _attempts,
                        'Your verification activity will appear here.',
                        (r) => ListTile(
                          contentPadding: const EdgeInsets.all(16),
                          leading: Icon(
                            r['result'] == 'success'
                                ? Icons.verified_outlined
                                : r['result'] == 'pending'
                                ? Icons.schedule
                                : Icons.info_outline,
                            color: r['result'] == 'success' ? teal : muted,
                          ),
                          title: Text(
                            '${r['stage']} · ${r['result']}',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            '${friendlyTime(r['attempted_at'] as String?)}${r['failure_reason'] == null ? '' : '\n${r['failure_reason']}'}',
                            style: const TextStyle(fontSize: 12),
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    ),
  );

  Widget _list(
    List<dynamic> rows,
    String empty,
    Widget Function(dynamic) item,
  ) => RefreshIndicator(
    onRefresh: _load,
    child: rows.isEmpty
        ? ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(32),
            children: [
              const SizedBox(height: 75),
              const Icon(Icons.receipt_long_outlined, color: muted, size: 45),
              const SizedBox(height: 16),
              Text(empty, textAlign: TextAlign.center),
            ],
          )
        : ListView.separated(
            padding: const EdgeInsets.all(20),
            itemCount: rows.length,
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (_, i) => Card(child: item(rows[i])),
          ),
  );
}
