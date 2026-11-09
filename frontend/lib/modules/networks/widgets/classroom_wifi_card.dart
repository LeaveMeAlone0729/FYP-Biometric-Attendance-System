import 'package:flutter/material.dart';
import '../../../services/api_client.dart';
import '../services/classroom_wifi_api.dart';

class ClassroomWifiCard extends StatefulWidget {
  const ClassroomWifiCard({super.key, this.api});
  final ClassroomWifiApi? api;
  @override
  State<ClassroomWifiCard> createState() => _ClassroomWifiCardState();
}

class _ClassroomWifiCardState extends State<ClassroomWifiCard>
    with WidgetsBindingObserver {
  late final _api = widget.api ?? ClassroomWifiApi();
  List<Map<String, dynamic>> _rooms = [];
  String? _room, _error, _code;
  Map<String, dynamic>? _result;
  bool _busy = false;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  String message(Object error) {
    if (error is ApiException) {
      if (error.status == 404) {
        return 'Classroom Wi-Fi is unavailable on this backend. Use the isolated test backend on port 8002.';
      }
      if (['NETWORK_ERROR', 'REQUEST_TIMEOUT'].contains(error.code)) {
        return 'Unable to reach the verification server. No classroom policy result was confirmed. Check the LAN or USB connection and retry.';
      }
      return error.message;
    }
    return 'Classroom verification is unavailable. Check the connection and Android permissions, then retry.';
  }

  Future<void> _load() async {
    if (_busy) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _error = null;
      _code = null;
      _result = null;
    });
    try {
      final rooms = await _api.classrooms();
      if (mounted && generation == _generation) {
        setState(() {
          _rooms = rooms;
          _room = rooms.isEmpty ? null : rooms.first['classroom_id'] as String;
        });
      }
    } catch (e) {
      if (mounted && generation == _generation) {
        setState(() {
          _error = message(e);
          _code = e is ApiException ? e.code : 'CLASSROOM_UNAVAILABLE';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    if (_busy || _room == null) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _result = null;
      _error = null;
      _code = null;
    });
    try {
      final result = await _api.verify(_room!);
      if (mounted && generation == _generation) {
        setState(() => _result = result);
      }
    } catch (e) {
      if (mounted && generation == _generation) {
        setState(() {
          _error = message(e);
          _code = e is ApiException ? e.code : 'CLASSROOM_UNAVAILABLE';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      _generation++;
      setState(() {
        _result = null;
        _error = null;
        _code = null;
      });
    }
  }

  @override
  void dispose() {
    _generation++;
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Classroom Wi-Fi Verification',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const Text(
            'Simulation only. Signed Android observations are not proof of physical presence and do not authorize attendance.',
          ),
          const SizedBox(height: 12),
          if (_rooms.isNotEmpty)
            DropdownButtonFormField<String>(
              key: ValueKey(_room),
              initialValue: _room,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Test classroom'),
              items: _rooms
                  .map(
                    (r) => DropdownMenuItem<String>(
                      value: r['classroom_id'] as String,
                      child: Text(r['name'] as String),
                    ),
                  )
                  .toList(),
              onChanged: _busy
                  ? null
                  : (value) => setState(() {
                      _room = value;
                      _result = null;
                      _error = null;
                      _code = null;
                    }),
            ),
          if (!_busy && _rooms.isEmpty && _error == null)
            const Text(
              'No test classrooms configured. Add a policy using fyp-test.ps1.',
            ),
          if (_busy)
            const Padding(
              padding: EdgeInsets.all(12),
              child: Row(
                children: [
                  SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(),
                  ),
                  SizedBox(width: 12),
                  Flexible(child: Text('Checking classroom Wi-Fi…')),
                ],
              ),
            ),
          if (_result != null) ...[
            Text(
              'Classroom Wi-Fi verification: ${_result!['result']}',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: _result!['result'] == 'PASS' ? Colors.green : Colors.red,
              ),
            ),
            Text('Reason: ${_result!['reason_code']}'),
            Text(_result!['message'] as String),
            if (_result!['matched_policy_id'] != null)
              Text('Matched policy: ${_result!['matched_policy_id']}'),
            Text('Checked: ${_result!['verified_at']}'),
          ],
          if (_error != null) ...[
            const Text(
              'Classroom Wi-Fi verification: FAIL',
              style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
            ),
            Text('Reason: ${_code ?? 'CLASSROOM_UNAVAILABLE'}'),
            Text(_error!),
          ],
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton(
                onPressed: _busy || _room == null ? null : _verify,
                child: const Text('Refresh / Verify classroom'),
              ),
              TextButton(
                onPressed: _busy ? null : _load,
                child: const Text('Reload classrooms'),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
