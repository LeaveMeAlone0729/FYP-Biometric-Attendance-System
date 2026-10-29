import 'package:flutter/material.dart';

const universityBlue = Color(0xFF144DA1);
const portalPurple = Color(0xFF5724A4);
const ink = Color(0xFF161616);
const teal = universityBlue;
const mist = Colors.white;
const muted = Color(0xFF707070);

ThemeData appTheme() => ThemeData(
  useMaterial3: false,
  fontFamily: 'PatrickHand',
  colorScheme: ColorScheme.fromSeed(
    seedColor: teal,
    primary: teal,
    secondary: ink,
  ),
  scaffoldBackgroundColor: mist,
  appBarTheme: const AppBarTheme(
    backgroundColor: universityBlue,
    foregroundColor: Colors.white,
    centerTitle: false,
  ),
  textTheme: const TextTheme(
    headlineLarge: TextStyle(
      fontSize: 32,
      fontWeight: FontWeight.normal,
      color: ink,
      letterSpacing: -1,
    ),
    headlineMedium: TextStyle(
      fontSize: 26,
      fontWeight: FontWeight.normal,
      color: ink,
      letterSpacing: -.6,
    ),
    titleLarge: TextStyle(
      fontSize: 20,
      fontWeight: FontWeight.normal,
      color: ink,
    ),
    titleMedium: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.normal,
      color: ink,
    ),
    bodyLarge: TextStyle(fontSize: 16, color: ink),
    bodyMedium: TextStyle(fontSize: 17, color: ink, height: 1.2),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: Colors.white,
    contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(6),
      borderSide: const BorderSide(color: Color(0xFFD9E3E7)),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(6),
      borderSide: const BorderSide(color: Color(0xFFD9E3E7)),
    ),
  ),
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(
      minimumSize: const Size(0, 54),
      textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
  ),
  cardTheme: CardThemeData(
    color: Colors.white,
    elevation: 0,
    margin: EdgeInsets.zero,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(8),
      side: const BorderSide(color: Color(0xFFE2EAED)),
    ),
  ),
  navigationBarTheme: NavigationBarThemeData(
    backgroundColor: Colors.white,
    indicatorColor: teal.withValues(alpha: .12),
  ),
);

class InfoNotice extends StatelessWidget {
  const InfoNotice(
    this.text, {
    super.key,
    this.icon = Icons.info_outline,
    this.warning = false,
  });
  final String text;
  final IconData icon;
  final bool warning;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: warning ? const Color(0xFFFFF2DC) : const Color(0xFFEEF3FC),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: warning ? const Color(0xFF99600A) : teal, size: 22),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: warning ? const Color(0xFF805510) : teal,
              height: 1.45,
            ),
          ),
        ),
      ],
    ),
  );
}

String friendlyTime(String? value) {
  if (value == null) return '';
  // Preserve the academic timezone supplied by the backend, not the device timezone.
  final local = value.length > 19 ? value.substring(0, 19) : value;
  final date = DateTime.tryParse(local);
  if (date == null) return value;
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year} · ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
}
