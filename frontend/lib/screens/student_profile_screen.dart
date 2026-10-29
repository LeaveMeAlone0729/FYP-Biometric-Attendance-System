import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import '../modules/biometrics/screens/camera_screen.dart';
import '../modules/biometrics/services/biometric_api.dart';

class StudentProfileScreen extends StatefulWidget {
  const StudentProfileScreen({super.key});
  @override
  State<StudentProfileScreen> createState() => _StudentProfileScreenState();
}

class _StudentProfileScreenState extends State<StudentProfileScreen> {
  final _api = ApiClient.instance;
  // Chew Zhexuan: the profile's face enrollment actions use the biometric module.
  final _biometrics = BiometricApi();
  bool _busy = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      await _api.refreshStudent();
      if (mounted) setState(() => _error = null);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _remove() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove face registration?'),
        content: const Text(
          'Your encrypted face template will be deleted. You will need to register again to take attendance. Your attendance history is kept.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep registration'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove template'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _biometrics.removeRegistration();
      await _refresh();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _logout() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _api.logout();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final student = _api.student ?? {};
    final enrolled = student['biometric_status'] == 'active';
    return SafeArea(
      child: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text(
              'Your profile',
              style: Theme.of(context).textTheme.headlineLarge,
            ),
            const SizedBox(height: 26),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    CircleAvatar(
                      radius: 35,
                      backgroundColor: const Color(0xFFE3F1EE),
                      child: Text(
                        (student['name'] as String? ?? 'S')
                            .substring(0, 1)
                            .toUpperCase(),
                        style: const TextStyle(
                          fontSize: 30,
                          color: teal,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      student['name'] as String? ?? '',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 5),
                    Text(student['student_id'] as String? ?? ''),
                    const SizedBox(height: 5),
                    Text(
                      student['email'] as String? ?? '',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      '${student['programme_code'] ?? ''} · ${student['group_name'] ?? ''}',
                      style: const TextStyle(
                        color: teal,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Facial biometrics',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 14),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          enrolled
                              ? Icons.verified_outlined
                              : Icons.face_outlined,
                          color: teal,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            enrolled
                                ? 'Face registered'
                                : 'Face registration needed',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      enrolled
                          ? 'Your encrypted facial template is ready for attendance verification.'
                          : 'Register your face once. Your face will be checked before each gesture challenge.',
                    ),
                    const SizedBox(height: 18),
                    SizedBox(
                      width: double.infinity,
                      child: enrolled
                          ? OutlinedButton.icon(
                              onPressed: _busy ? null : _remove,
                              icon: const Icon(Icons.delete_outline),
                              label: const Text('Remove face registration'),
                            )
                          : FilledButton.icon(
                              onPressed: _busy
                                  ? null
                                  : () async {
                                      await Navigator.push<bool>(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => const CameraScreen(
                                            enrollment: true,
                                          ),
                                        ),
                                      );
                                      await _refresh();
                                    },
                              icon: const Icon(Icons.face_retouching_natural),
                              label: const Text('Register my face'),
                            ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 22),
            const InfoNotice(
              'Biometric privacy\nYour camera photos are processed for verification. The server stores an encrypted face template and verification outcomes. You can remove your template at any time.',
              icon: Icons.lock_outline,
            ),
            const SizedBox(height: 22),
            if (_error != null) ...[
              InfoNotice(_error!, warning: true),
              const SizedBox(height: 14),
            ],
            OutlinedButton.icon(
              onPressed: _busy ? null : _logout,
              icon: const Icon(Icons.logout_rounded),
              label: Text(_busy ? 'Please wait…' : 'Sign out'),
            ),
            const SizedBox(height: 20),
            const Center(
              child: Text(
                'Attend · Student research prototype',
                style: TextStyle(fontSize: 11),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
