import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/auth_screen.dart';
import 'screens/student_dashboard.dart';
import 'services/api_client.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});
  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  final _navigator = GlobalKey<NavigatorState>();
  @override
  void initState() {
    super.initState();
    ApiClient.instance.authenticated.addListener(_sessionChanged);
  }

  void _sessionChanged() {
    if (!ApiClient.instance.authenticated.value) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _navigator.currentState?.popUntil((route) => route.isFirst);
        }
      });
    }
  }

  @override
  void dispose() {
    ApiClient.instance.authenticated.removeListener(_sessionChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    navigatorKey: _navigator,
    title: 'Attend',
    debugShowCheckedModeBanner: false,
    theme: appTheme(),
    builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.black,
        statusBarIconBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: ColoredBox(
        color: Colors.black,
        child: SafeArea(bottom: false, child: child ?? const SizedBox.shrink()),
      ),
    ),
    home: ValueListenableBuilder<bool>(
      valueListenable: ApiClient.instance.authenticated,
      builder: (_, signedIn, _) =>
          signedIn ? const StudentDashboard() : const AuthScreen(),
    ),
  );
}
