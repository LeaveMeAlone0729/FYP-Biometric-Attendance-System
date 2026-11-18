import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/services/api_routes.dart';

void main() {
  const lan = 'http://192.168.10.20:8000';
  test(
    'Local uses identical private backend for general and security calls',
    () async {
      final client = ApiClient(
        url: lan,
        publicUrl: lan,
        localMode: true,
        client: MockClient((r) async {
          expect(r.url.origin, lan);
          expect(r.url.host, isNot('api.bioattsys.xyz'));
          return http.Response(
            jsonEncode(
              r.url.path == '/login'
                  ? {
                      'access_token': 'synthetic-test',
                      'student': {'student_id': 'LOCAL'},
                    }
                  : {'success': true},
            ),
            200,
          );
        }),
      );
      await client.login('LOCAL', 'synthetic');
      for (final path in [
        '/me',
        '/classes',
        '/attendance/history',
        '/attendance/summary',
      ]) {
        await client.get(path);
      }
      for (final path in [
        '/attendance/start',
        '/api/v1/networks/verifications',
        '/api/v1/devices/verifications',
        '/api/v1/classroom-wifi/challenges',
        '/api/v1/classroom-ble/challenges',
      ]) {
        await client.post(path, {});
      }
    },
  );
  test('Full mode continues to reject general HTTP', () {
    expect(() => ApiRoutes(lan: lan, public: lan), throwsArgumentError);
    final full = ApiRoutes(lan: lan, public: 'https://api.bioattsys.xyz');
    expect(full.uri('/login').scheme, 'https');
    expect(full.uri('/attendance/start').origin, lan);
  });
  for (final other in [
    'http://192.168.10.21:8000',
    'http://example.com:8000',
    'http://8.8.8.8:8000',
    'http://127.0.0.1:8000',
    'http://10.0.0.2:8001',
  ]) {
    test('Local rejects mismatched or nonprivate origin $other', () {
      expect(
        () => ApiRoutes(lan: lan, public: other, localMode: true),
        throwsArgumentError,
      );
    });
  }
  test('Explicit Local flag does not allow a shared arbitrary HTTP host', () {
    for (final bad in [
      'http://8.8.8.8:8000',
      'http://example.com:8000',
      'http://10.000.0.1:8000',
    ]) {
      expect(
        () => ApiRoutes(lan: bad, public: bad, localMode: true),
        throwsArgumentError,
      );
    }
  });
}
