import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';
import '../modules/devices/screens/my_device_screen.dart';
import '../modules/networks/screens/network_verification_screen.dart';
import '../modules/biometrics/screens/camera_screen.dart';

class StudentProfileScreen extends StatefulWidget {
  const StudentProfileScreen({super.key});
  @override
  State<StudentProfileScreen> createState() => _StudentProfileScreenState();
}

class _StudentProfileScreenState extends State<StudentProfileScreen> {
  final _api = ApiClient.instance;
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
    final canEnroll = student['biometric_status'] == 'not_registered';
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
            Card(
              child: ListTile(
                leading: const Icon(Icons.phonelink_lock),
                title: const Text('My Device'),
                subtitle: const Text(
                  'Register or view your trusted Android device',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(builder: (_) => const MyDeviceScreen()),
                ),
              ),
            ),
            const SizedBox(height: 24),
            Card(
              child: ListTile(
                leading: const Icon(Icons.network_check),
                title: const Text('Network Verification'),
                subtitle: const Text('View the backend connection diagnostic'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const NetworkVerificationScreen(),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            // Chew Zhexuan: facial registration and department support guidance.
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
                                : canEnroll
                                ? 'Face registration needed'
                                : 'Contact your department',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      enrolled
                          ? 'Your encrypted facial template is ready for attendance verification. Registration is locked to prevent changes by students.'
                          : canEnroll
                          ? 'Register your own face once. Registration is locked after enrollment. Your face will be checked before each gesture challenge.'
                          : 'Your facial registration needs attention. Visit your department for assistance.',
                    ),
                    if (canEnroll) ...[
                      const SizedBox(height: 18),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: _busy
                              ? null
                              : () async {
                                  await Navigator.push<bool>(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) =>
                                          const CameraScreen(enrollment: true),
                                    ),
                                  );
                                  await _refresh();
                                },
                          icon: const Icon(Icons.face_retouching_natural),
                          label: const Text('Register my face'),
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    const Text(
                      'If face verification repeatedly fails, ask your lecturer to record attendance manually. Visit your department for identity verification and supervised re-registration.',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 22),
            const InfoNotice(
              'Biometric privacy\nYour camera photos are processed for verification. The server stores an encrypted face template and verification outcomes. Contact your department for facial data removal requests.',
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
