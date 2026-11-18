import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/services/api_routes.dart';

void main() {
  const lan = 'http://192.0.2.1:8000';
  const public = 'https://fyp.test.example';
  http.Response ok([Object? value]) =>
      http.Response(jsonEncode(value ?? {'success': true}), 200);
  http.Response login() => ok({
    'access_token': 'synthetic-token',
    'student': {'student_id': 'TEST'},
  });

  test(
    'General APIs always use HTTPS; every classroom proof remains LAN',
    () async {
      final api = ApiClient(
        url: lan,
        publicUrl: public,
        client: MockClient((r) async {
          expect(r.url.origin, ApiRoutes.general(r.url.path) ? public : lan);
          return r.url.path == '/login' ? login() : ok();
        }),
      );
      for (final path in [
        '/config',
        '/me',
        '/classes',
        '/attendance/history',
        '/attendance/summary',
      ]) {
        await api.get(path);
      }
      await api.login('TEST', 'synthetic');
      for (final path in [
        '/attendance/start',
        '/api/v1/networks/verifications',
        '/api/v1/attendance/preflight-challenges',
        '/api/v1/classroom-wifi/challenges',
        '/api/v1/classroom-ble/challenges',
        '/api/v1/devices/verifications',
      ]) {
        await api.post(path, {});
      }
      await api.image('/verify-face', Uint8List(0), {});
      await api.image('/liveness/frame', Uint8List(0), {});
    },
  );

  test('Wi-Fi to mobile and back keeps same account and bearer', () async {
    final events = StreamController<dynamic>(sync: true);
    final api = ApiClient(
      url: lan,
      publicUrl: public,
      networkChanges: events.stream,
      client: MockClient((r) async {
        if (r.url.path == '/login') {
          return login();
        }
        expect(r.headers['Authorization'], 'Bearer synthetic-token');
        return ok();
      }),
    );
    await api.login('TEST', 'synthetic');
    final revision = api.sessionRevision;
    for (final _ in [1, 2, 3, 4]) {
      events.add('changed');
      await api.get('/me');
      expect(api.authenticated.value, true);
      expect(api.student!['student_id'], 'TEST');
    }
    expect(api.sessionRevision, greaterThan(revision));
    api.dispose();
    await events.close();
  });

  test('LAN failure never falls back to public, login still works', () async {
    var lanRequests = 0;
    final api = ApiClient(
      url: lan,
      publicUrl: public,
      client: MockClient((r) async {
        if (r.url.host == '192.0.2.1') {
          lanRequests++;
          throw http.ClientException('offline');
        }
        return r.url.path == '/login' ? login() : ok();
      }),
    );
    await api.login('TEST', 'synthetic');
    await expectLater(
      api.post('/attendance/start', {}),
      throwsA(isA<ApiException>()),
    );
    expect(lanRequests, 1);
    expect(api.authenticated.value, true);
    await api.get('/me');
  });

  test('Public failure never sends credentials to LAN', () async {
    var requests = 0;
    final api = ApiClient(
      url: lan,
      publicUrl: public,
      client: MockClient((r) async {
        requests++;
        expect(r.url.origin, public);
        throw http.ClientException('offline');
      }),
    );
    await expectLater(
      api.login('TEST', 'synthetic'),
      throwsA(isA<ApiException>()),
    );
    expect(requests, 1);
  });

  test(
    'Interrupted proof/upload never retries and old attempt cannot resume',
    () async {
      late ApiClient api;
      var images = 0;
      api = ApiClient(
        url: lan,
        publicUrl: public,
        client: MockClient((r) async {
          if (r.url.path == '/login') {
            return login();
          }
          if (r.url.path == '/verify-face') {
            images++;
            api.networkChanged();
          }
          return ok();
        }),
      );
      await api.login('TEST', 'synthetic');
      await api.post('/attendance/start', {});
      await expectLater(
        api.image('/verify-face', Uint8List(0), {}),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'NETWORK_CHANGED'),
        ),
      );
      await expectLater(
        api.image('/liveness/frame', Uint8List(0), {}),
        throwsA(isA<ApiException>()),
      );
      expect(images, 1);
      expect(api.authenticated.value, true);
      await api.post('/attendance/start', {});
      await api.image('/liveness/frame', Uint8List(0), {});
    },
  );

  test(
    'General GET retries once after change, mutation is not replayed',
    () async {
      late ApiClient api;
      var reads = 0, writes = 0;
      api = ApiClient(
        url: lan,
        publicUrl: public,
        client: MockClient((r) async {
          if (r.method == 'GET') {
            reads++;
            if (reads == 1) {
              api.networkChanged();
            }
          } else {
            writes++;
            api.networkChanged();
          }
          return ok();
        }),
      );
      await api.get('/me');
      expect(reads, 2);
      await expectLater(api.post('/logout', {}), throwsA(isA<ApiException>()));
      expect(writes, 1);
    },
  );

  test('Classroom timeout is bounded and keeps login', () async {
    final api = ApiClient(
      url: lan,
      publicUrl: public,
      classroomTimeout: const Duration(milliseconds: 5),
      client: MockClient((r) async {
        if (r.url.path == '/login') {
          return login();
        }
        return Completer<http.Response>().future;
      }),
    );
    await api.login('TEST', 'synthetic');
    await expectLater(
      api.post('/attendance/start', {}),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'REQUEST_TIMEOUT')
            .having((e) => e.message, 'message', contains('Classroom Wi-Fi')),
      ),
    );
    expect(api.authenticated.value, true);
  });

  test(
    'Unsafe endpoint configuration rejected; legacy LAN build supported',
    () {
      expect(
        () => ApiRoutes(lan: lan, public: 'http://example.com'),
        throwsArgumentError,
      );
      expect(
        () => ApiRoutes(lan: lan, public: 'https://user:secret@example.com'),
        throwsArgumentError,
      );
      final routes = ApiRoutes(lan: lan);
      expect(routes.uri('/login').origin, lan);
      expect(() => routes.uri('//attacker.example/login'), throwsArgumentError);
    },
  );
}
