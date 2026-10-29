import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';

void main() {
  test('Login sends credentials without installation identifiers', () async {
    final api = ApiClient(
      client: MockClient((request) async {
        expect(request.url.path, '/login');
        expect(jsonDecode(request.body), {
          'student_id': 'TEST001',
          'password': 'test-password',
        });
        return http.Response(
          jsonEncode({
            'access_token': 'test-token',
            'student': {'student_id': 'TEST001', 'biometric_status': 'active'},
          }),
          200,
        );
      }),
    );
    await api.login(' test001 ', 'test-password');
    expect(api.authenticated.value, isTrue);
    expect(api.student?['biometric_status'], 'active');
  });

  test('A network failure becomes an actionable message', () async {
    final api = ApiClient(
      client: MockClient(
        (_) async => throw http.ClientException('connection refused'),
      ),
    );
    await expectLater(
      api.get('/config'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.message,
          'message',
          contains('Cannot reach'),
        ),
      ),
    );
  });
  test('Server validation errors identify the invalid field', () async {
    final api = ApiClient(
      client: MockClient(
        (_) async => http.Response(
          '{"message":"Check the fields","fields":[{"field":"email","message":"Enter a valid email."}]}',
          422,
        ),
      ),
    );
    await expectLater(
      api.post('/register', {}),
      throwsA(
        isA<ApiException>().having(
          (e) => e.message,
          'message',
          contains('email: Enter a valid email.'),
        ),
      ),
    );
  });
  test(
    'Unexpected response formats do not leak parsing errors into the UI',
    () async {
      final api = ApiClient(
        client: MockClient(
          (_) async => http.Response('<html>proxy error</html>', 502),
        ),
      );
      await expectLater(
        api.get('/config'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('unexpected response'),
          ),
        ),
      );
    },
  );
}
