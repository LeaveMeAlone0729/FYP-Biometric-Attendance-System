/// A public route is deliberately allowlisted. Everything else stays on LAN.
class ApiRoutes {
  ApiRoutes({required this.lan, String public = '', bool localMode = false})
    : public = public.isEmpty ? null : public {
    for (final value in [lan, if (this.public != null) this.public!]) {
      final uri = Uri.parse(value);
      if (!uri.hasAuthority ||
          uri.userInfo.isNotEmpty ||
          !['http', 'https'].contains(uri.scheme) ||
          !['', '/'].contains(uri.path) ||
          uri.hasQuery ||
          uri.hasFragment) {
        throw ArgumentError('API URLs must be origins without credentials.');
      }
    }
    if (localMode) {
      final uri = Uri.parse(lan);
      final octets = uri.host.split('.').map(int.tryParse).toList();
      final privateV4 =
          octets.length == 4 &&
          octets.every((n) => n != null && n >= 0 && n <= 255) &&
          octets.map((n) => n.toString()).join('.') == uri.host &&
          (octets[0] == 10 ||
              (octets[0] == 172 && octets[1]! >= 16 && octets[1]! <= 31) ||
              (octets[0] == 192 && octets[1] == 168));
      if (this.public == null ||
          Uri.parse(this.public!).origin != uri.origin ||
          uri.scheme != 'http' ||
          uri.port != 8000 ||
          !privateV4) {
        throw ArgumentError(
          'Local mode requires identical private LAN HTTP origins on port 8000.',
        );
      }
    } else if (this.public != null &&
        Uri.parse(this.public!).scheme != 'https') {
      throw ArgumentError('PUBLIC_API_BASE_URL must use HTTPS.');
    }
  }
  final String lan;
  final String? public;
  static bool general(String path) => const {
    '/config',
    '/login',
    '/logout',
    '/me',
    '/classes',
    '/attendance/history',
    '/attendance/summary',
  }.contains(path);
  Uri uri(String path) {
    if (!path.startsWith('/') ||
        path.startsWith('//') ||
        path.contains('..') ||
        path.contains('?') ||
        path.contains('#')) {
      throw ArgumentError('Expected a canonical API path.');
    }
    return Uri.parse(
      '${(general(path) ? public ?? lan : lan).replaceAll(RegExp(r'/$'), '')}$path',
    );
  }

  static bool attendanceProof(String path) =>
      path == '/verify-face' ||
      path.startsWith('/liveness/') ||
      path.startsWith('/verification/') ||
      path.startsWith('/api/v1/attendance/');
}
