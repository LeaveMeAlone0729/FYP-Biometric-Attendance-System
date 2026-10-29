import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../theme.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _form = GlobalKey<FormState>();
  final _id = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  final _email = TextEditingController();
  bool _signup = false, _busy = false, _hidePassword = true;
  String? _error;
  List<dynamic> _groups = [];
  int? _groupId;
  bool? _demo;
  final _api = ApiClient.instance;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    try {
      await _api.loadConfig();
      final groups = await _api.get('/groups') as List;
      if (mounted) {
        setState(() {
          _demo = _api.config['demo_mode'] == true;
          _groups = groups;
          if (groups.isNotEmpty) _groupId = groups.first['group_id'] as int;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  void dispose() {
    _id.dispose();
    _password.dispose();
    _name.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    if (_signup && _groupId == null) {
      setState(
        () => _error =
            'Load the available student groups before creating an account.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_signup) {
        await _api.post('/register', {
          'student_id': _id.text.trim().toUpperCase(),
          'name': _name.text.trim(),
          'email': _email.text.trim(),
          'password': _password.text,
          'group_id': _groupId,
        });
      }
      await _api.login(_id.text, _password.text);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Form(
              key: _form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(11),
                        decoration: BoxDecoration(
                          color: teal,
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: const Icon(
                          Icons.fingerprint_rounded,
                          color: Colors.white,
                          size: 30,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        'Attend',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                    ],
                  ),
                  const SizedBox(height: 44),
                  Text(
                    _signup
                        ? 'Your attendance,\nyour identity.'
                        : 'Welcome back.',
                    style: Theme.of(context).textTheme.headlineLarge,
                  ),
                  const SizedBox(height: 10),
                  Text(
                    _signup
                        ? 'Create a student account to get started.'
                        : 'Sign in to verify your presence and keep track of your classes.',
                  ),
                  const SizedBox(height: 28),
                  if (_demo == true) ...[
                    const InfoNotice(
                      'Demo environment · Use a test student account. Class and group data are for demonstration.',
                      icon: Icons.science_outlined,
                    ),
                    const SizedBox(height: 22),
                  ],
                  TextFormField(
                    controller: _id,
                    enabled: !_busy,
                    textCapitalization: TextCapitalization.characters,
                    decoration: const InputDecoration(
                      labelText: 'Student ID',
                      prefixIcon: Icon(Icons.badge_outlined),
                    ),
                    validator: (v) =>
                        v == null ||
                            !RegExp(r'^[a-zA-Z0-9]{3,11}$').hasMatch(v.trim())
                        ? 'Enter a student ID with 3–11 letters or digits.'
                        : null,
                  ),
                  const SizedBox(height: 16),
                  if (_signup) ...[
                    TextFormField(
                      controller: _name,
                      enabled: !_busy,
                      decoration: const InputDecoration(
                        labelText: 'Full name',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      validator: (v) => v == null || v.trim().length < 2
                          ? 'Enter your full name.'
                          : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _email,
                      enabled: !_busy,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                        labelText: 'Email address',
                        prefixIcon: Icon(Icons.alternate_email),
                      ),
                      validator: (v) =>
                          v == null ||
                              !RegExp(
                                r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                              ).hasMatch(v.trim())
                          ? 'Enter a valid email.'
                          : null,
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<int>(
                      initialValue: _groupId,
                      decoration: const InputDecoration(
                        labelText: 'Demo student group',
                      ),
                      items: _groups
                          .map(
                            (g) => DropdownMenuItem<int>(
                              value: g['group_id'] as int,
                              child: Text(
                                '${g['programme_code']} · ${g['group_name']}',
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: _busy
                          ? null
                          : (v) => setState(() => _groupId = v),
                    ),
                    const SizedBox(height: 16),
                  ],
                  TextFormField(
                    controller: _password,
                    enabled: !_busy,
                    obscureText: _hidePassword,
                    onFieldSubmitted: (_) {
                      if (!_busy) _submit();
                    },
                    decoration: InputDecoration(
                      labelText: 'Password',
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(
                        onPressed: () =>
                            setState(() => _hidePassword = !_hidePassword),
                        tooltip: 'Show or hide password',
                        icon: Icon(
                          _hidePassword
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                      ),
                    ),
                    validator: (v) => v == null || v.isEmpty
                        ? 'Enter your password.'
                        : _signup && v.length < 8
                        ? 'Use at least 8 characters.'
                        : null,
                  ),
                  const SizedBox(height: 22),
                  if (_error != null) ...[
                    InfoNotice(_error!, warning: true),
                    TextButton(
                      onPressed: _busy ? null : _loadConfig,
                      child: const Text('Retry connection'),
                    ),
                    const SizedBox(height: 12),
                  ],
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _busy ? null : _submit,
                      child: _busy
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(_signup ? 'Create account' : 'Sign in'),
                    ),
                  ),
                  if (_demo == true)
                    Center(
                      child: TextButton(
                        onPressed: _busy
                            ? null
                            : () => setState(() {
                                _signup = !_signup;
                                _error = null;
                              }),
                        child: Text(
                          _signup
                              ? 'Already have an account? Sign in'
                              : 'New here? Create a demo account',
                        ),
                      ),
                    ),
                  const SizedBox(height: 26),
                  const Row(
                    children: [
                      Icon(Icons.shield_outlined, size: 17, color: muted),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Facial verification + gesture challenge',
                          style: TextStyle(fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Student attendance research prototype',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
