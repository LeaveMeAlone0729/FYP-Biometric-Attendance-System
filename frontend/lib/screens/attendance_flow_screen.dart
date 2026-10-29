import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import 'camera_screen.dart';

class AttendanceFlowScreen extends StatefulWidget {
  const AttendanceFlowScreen({super.key, this.onRecorded});
  final VoidCallback? onRecorded;
  @override
  State<AttendanceFlowScreen> createState() => _AttendanceFlowScreenState();
}

class _AttendanceFlowScreenState extends State<AttendanceFlowScreen> {
  String _pin = '';
  String? _error;
  bool _busy = false;

  void _key(String key) {
    if (_busy) return;
    setState(() {
      if (key == 'back') {
        if (_pin.isNotEmpty) _pin = _pin.substring(0, _pin.length - 1);
      } else if (_pin.length < 6) {
        _pin += key;
      }
      _error = null;
    });
  }

  Future<void> _submit() async {
    if (_pin.length != 6 || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final challenge = Map<String, dynamic>.from(
        await ApiClient.instance.post('/attendance/start', {'pin': _pin})
            as Map,
      );
      if (!mounted) return;
      final result = await Navigator.push<bool>(
        context,
        MaterialPageRoute(builder: (_) => CameraScreen(challenge: challenge)),
      );
      if (mounted) setState(() => _pin = '');
      if (result == true) widget.onRecorded?.call();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final diameter = math.min(86.0, constraints.maxWidth * .205);
        final gap = math.max(12.0, diameter * .18);
        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(19, 20, 19, 28),
          child: Column(
            children: [
              const Text(
                'Please enter a 6 digits code to register your attendance.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 19),
              ),
              const SizedBox(height: 23),
              Row(
                children: List.generate(
                  6,
                  (index) => Expanded(
                    child: Semantics(
                      label: 'Attendance digit ${index + 1}',
                      value: index < _pin.length ? _pin[index] : 'Empty',
                      child: Container(
                        height: 54,
                        margin: EdgeInsets.only(right: index == 5 ? 0 : 9),
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: const Color(0xFFB6B6B6),
                            width: 1.3,
                          ),
                        ),
                        child: Text(
                          index < _pin.length ? _pin[index] : '',
                          style: const TextStyle(
                            fontSize: 28,
                            color: universityBlue,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 2),
                    child: Icon(Icons.help, size: 16, color: Color(0xFF008778)),
                  ),
                  const SizedBox(width: 28),
                  const Expanded(
                    child: Text(
                      'Use the PIN provided for your class during its attendance window, then verify your face and complete the hand gesture.',
                      style: TextStyle(fontSize: 15, height: 1.15),
                    ),
                  ),
                ],
              ),
              SizedBox(height: constraints.maxHeight > 700 ? 42 : 30),
              for (final row in [
                ['1', '2', '3'],
                ['4', '5', '6'],
                ['7', '8', '9'],
                ['back', '0', 'submit'],
              ]) ...[
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: row
                      .map(
                        (key) => SizedBox.square(
                          dimension: diameter,
                          child: Material(
                            color: universityBlue,
                            shape: const CircleBorder(),
                            clipBehavior: Clip.antiAlias,
                            child: key == 'submit'
                                ? IconButton(
                                    key: const ValueKey('submit-attendance'),
                                    tooltip: 'Submit attendance code',
                                    onPressed: _pin.length == 6 && !_busy
                                        ? _submit
                                        : null,
                                    padding: EdgeInsets.zero,
                                    disabledColor: Colors.white54,
                                    color: Colors.white,
                                    icon: _busy
                                        ? const SizedBox(
                                            width: 24,
                                            height: 24,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: Colors.white,
                                            ),
                                          )
                                        : const Icon(Icons.check, size: 43),
                                  )
                                : InkWell(
                                    customBorder: const CircleBorder(),
                                    onTap: _busy ? null : () => _key(key),
                                    onLongPress: key == 'back' && !_busy
                                        ? () => setState(() {
                                            _pin = '';
                                            _error = null;
                                          })
                                        : null,
                                    child: Center(
                                      child: key == 'back'
                                          ? const Tooltip(
                                              triggerMode:
                                                  TooltipTriggerMode.manual,
                                              message:
                                                  'Delete digit; hold to clear',
                                              child: Icon(
                                                Icons.backspace_outlined,
                                                color: Colors.white,
                                                size: 34,
                                              ),
                                            )
                                          : Text(
                                              key,
                                              style: const TextStyle(
                                                fontSize: 34,
                                                color: Colors.white,
                                              ),
                                            ),
                                    ),
                                  ),
                          ),
                        ),
                      )
                      .toList(),
                ),
                SizedBox(height: gap),
              ],
              if (_error != null) ...[
                const SizedBox(height: 10),
                InfoNotice(_error!, warning: true),
              ],
            ],
          ),
        );
      },
    );
  }
}
