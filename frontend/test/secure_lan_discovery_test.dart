import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/lan_discovery.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/pending_device_service.dart';
import 'pending_device_test.dart' show CandidateKeys, candidate;

void main() {
  late Directory fixture;
  late Map<String, dynamic> publicTrust;
  late LanTrust trust;
  setUpAll(() async {
    fixture = await Directory.systemTemp.createTemp('fyp-lan-test-');
    final python = Platform.environment['FYP_TEST_PYTHON'] ??
        (Platform.isWindows
            ? '../backend/venv/Scripts/python.exe'
            : '../backend/venv/bin/python');
    final result = await Process.run(python, [
      '-c',
      "import sys;from pathlib import Path;sys.path.insert(0,str(Path('../backend').resolve()));from lan_discovery import provision;provision(Path(sys.argv[1])/'full','Full','a'*64,protect=lambda _:None);provision(Path(sys.argv[1])/'rogue','Full','a'*64,protect=lambda _:None)",
      fixture.path,
    ]);
    expect(
      result.exitCode,
      0,
      reason: 'Disposable certificate generation failed',
    );
    publicTrust =
        jsonDecode(
              await File(
                '${fixture.path}/full/public-trust.json',
              ).readAsString(),
            )
            as Map<String, dynamic>;
    trust = LanTrust.fromMap(publicTrust, localMode: false);
  });
  tearDownAll(() async {
    await fixture.delete(recursive: true);
  });
  Map<String, dynamic> identity([LanTrust? value]) {
    final t = value ?? trust;
    return {
      'version': 1,
      'mode': t.mode,
      'server_id': t.serverId,
      'database_identity': t.databaseIdentity,
    };
  }

  Map<String, dynamic> hints(List<String> ips, {bool wifi = true}) => {
    'wifi': wifi,
    'subnets': [
      {'address': ips.isEmpty ? '192.168.1.2' : ips.first, 'prefix': 24},
    ],
    'candidates': ips.map((ip) => {'address': ip, 'port': 8005}).toList(),
  };
  SecureLanDiscovery fake(
    List<String> ips, {
    Map? reply,
    bool wifi = true,
    void Function(http.Request)? onRequest,
  }) => SecureLanDiscovery(
    trust,
    discover: () async => hints(ips, wifi: wifi),
    transport: (_) => MockClient((r) async {
      onRequest?.call(r);
      return http.Response(jsonEncode(reply ?? identity()), 200);
    }),
  );

  test(
    'Same pinned backend at home then school address; fresh probes',
    () async {
      var ip = '192.168.0.162';
      var probes = 0;
      final d = SecureLanDiscovery(
        trust,
        discover: () async => hints([ip]),
        transport: (_) => MockClient((r) async {
          expect(r.headers.containsKey('Authorization'), false);
          expect(r.url.host, trust.hostname);
          probes++;
          return http.Response(jsonEncode(identity()), 200);
        }),
      );
      await d.ensureReady();
      expect(d.address, ip);
      d.invalidate();
      ip = '10.46.58.220';
      await d.ensureReady();
      expect(d.address, ip);
      expect(probes, 2);
      d.invalidate();
    },
  );
  test('Unknown environment identity cannot receive a bearer', () async {
    final d = fake(
      ['192.168.1.1'],
      reply: {...identity(), 'database_identity': 'b' * 64},
    );
    var generalCalls = 0;
    final api = ApiClient(
      url: 'http://192.168.1.9:8000',
      publicUrl: 'https://fyp.test.example',
      discovery: d,
      client: MockClient((r) async {
        generalCalls++;
        return http.Response(
          jsonEncode({
            'access_token': 'synthetic',
            'student': {'student_id': 'TEST'},
          }),
          200,
        );
      }),
    );
    await api.login('TEST', 'synthetic');
    await expectLater(
      api.post('/attendance/start', {}),
      throwsA(isA<ApiException>()),
    );
    expect(generalCalls, 1);
    expect(d.address, null);
    api.dispose();
  });
  for (final ip in [
    '127.0.0.1',
    '169.254.1.3',
    '8.8.8.8',
    '224.0.0.251',
    '::1',
    '192.168.1.2/24',
    'https://192.168.1.2',
    '192.168.01.2',
  ]) {
    test('Malicious/unrelated address rejected: $ip', () {
      expect(privateLanAddress(ip), false);
      expect(
        () => fake([]).manualAddress(ip),
        throwsA(isA<LanDiscoveryException>()),
      );
    });
  }
  test('Multiple authenticated endpoints fail closed', () async {
    final d = fake(['192.168.1.1', '192.168.1.2']);
    await expectLater(d.ensureReady(), throwsA(isA<LanDiscoveryException>()));
    expect(d.lastError, 'MULTIPLE_PAIRED_SERVERS');
  });
  test('Duplicate advertisements do not create multiple servers', () async {
    final d = fake(['192.168.1.1', '192.168.1.1']);
    await d.ensureReady();
    expect(d.address, '192.168.1.1');
    d.invalidate();
  });
  test(
    'Advertisement cannot redirect anonymous probes outside current Wi-Fi subnet',
    () async {
      var probes = 0;
      final d = SecureLanDiscovery(
        trust,
        discover: () async => {
          'wifi': true,
          'subnets': [
            {'address': '192.168.1.2', 'prefix': 24},
          ],
          'candidates': [
            {'address': '10.1.1.2', 'port': 8005},
          ],
        },
        transport: (_) => MockClient((_) async {
          probes++;
          return http.Response('{}', 200);
        }),
      );
      await expectLater(d.ensureReady(), throwsA(isA<LanDiscoveryException>()));
      expect(probes, 0);
      expect(currentWifiSubnet('192.168.1.3', []), false);
      expect(
        currentWifiSubnet('192.168.1.3', [
          {'address': '192.168.1.2', 'prefix': 0},
        ]),
        false,
      );
    },
  );
  test(
    'Blocked multicast/no results: no subnet probes or untrusted fallback',
    () async {
      final d = fake([]);
      await expectLater(d.ensureReady(), throwsA(isA<LanDiscoveryException>()));
      expect(d.lastError, 'PAIRED_CLASSROOM_SERVER_NOT_FOUND');
    },
  );
  test(
    'Discovery timeout is bounded and cannot send an authenticated request',
    () async {
      var probes = 0;
      final d = SecureLanDiscovery(
        trust,
        discover: () => Completer<Map<dynamic, dynamic>>().future,
        discoveryTimeout: const Duration(milliseconds: 20),
        transport: (_) => MockClient((_) async {
          probes++;
          return http.Response('{}', 200);
        }),
      );
      await expectLater(d.ensureReady(), throwsA(isA<TimeoutException>()));
      expect(probes, 0);
      expect(d.lastError, 'LAN_DISCOVERY_UNAVAILABLE');
    },
  );
  test('Permission or native NSD error fails closed', () async {
    final d = SecureLanDiscovery(
      trust,
      discover: () async => throw StateError('permission unavailable'),
    );
    await expectLater(d.ensureReady(), throwsStateError);
    expect(d.address, null);
  });
  test('Explicit manual hint still requires installed identity', () async {
    final d = fake([]);
    d.manualAddress('192.168.1.8');
    await d.ensureReady();
    expect(d.address, '192.168.1.8');
    d.invalidate();
    final rogue = fake([], reply: {...identity(), 'server_id': 'f' * 32});
    rogue.manualAddress('192.168.1.8');
    await expectLater(
      rogue.ensureReady(),
      throwsA(isA<LanDiscoveryException>()),
    );
  });
  test(
    'Mobile data immediately blocks LAN probing but leaves public API usable',
    () async {
      var probes = 0;
      final d = fake(['192.168.1.1'], wifi: false, onRequest: (_) => probes++);
      final api = ApiClient(
        url: 'http://192.168.1.9:8000',
        publicUrl: 'https://fyp.test.example',
        discovery: d,
        client: MockClient((r) async {
          expect(r.url.origin, 'https://fyp.test.example');
          return http.Response('{}', 200);
        }),
      );
      await api.get('/classes');
      await expectLater(
        api.post('/attendance/start', {}),
        throwsA(isA<ApiException>()),
      );
      expect(probes, 0);
      expect(d.lastError, 'CLASSROOM_WIFI_REQUIRED');
      api.dispose();
    },
  );
  test('Full trust cannot be reused by Local installation', () {
    expect(
      () => LanTrust.fromMap(publicTrust, localMode: true),
      throwsA(isA<LanDiscoveryException>()),
    );
  });
  test(
    'Local sends general and classroom API only to paired TLS backend',
    () async {
      final localTrust = LanTrust.fromMap({
        ...publicTrust,
        'mode': 'Local',
      }, localMode: true);
      final origins = <String>[];
      final d = SecureLanDiscovery(
        localTrust,
        discover: () async => hints(['192.168.1.3']),
        transport: (_) => MockClient((r) async {
          origins.add(r.url.origin);
          return http.Response(
            jsonEncode(
              r.url.path == '/classroom-discovery/identity'
                  ? identity(localTrust)
                  : {},
            ),
            200,
          );
        }),
      );
      final api = ApiClient(
        url: 'http://192.168.1.9:8000',
        publicUrl: 'http://192.168.1.9:8000',
        localMode: true,
        discovery: d,
        client: MockClient(
          (_) async => throw StateError('No HTTP or public fallback'),
        ),
      );
      await api.get('/classes');
      await api.post('/api/v1/devices/verifications', {});
      expect(origins.every((o) => o == localTrust.origin), true);
      api.dispose();
    },
  );
  test('LAN remains usable while public Cloudflare is unavailable', () async {
    final d = fake(['192.168.1.1']);
    final api = ApiClient(
      url: 'http://192.168.1.9:8000',
      publicUrl: 'https://fyp.test.example',
      discovery: d,
      client: MockClient(
        (_) async => throw http.ClientException('unavailable'),
      ),
    );
    await expectLater(api.get('/classes'), throwsA(isA<ApiException>()));
    await api.post('/api/v1/networks/verifications', {});
    expect(d.address, '192.168.1.1');
    api.dispose();
  });
  test(
    'Network changes abandon pending discovery, not reuse old proof',
    () async {
      final completion = Completer<Map<dynamic, dynamic>>();
      final d = SecureLanDiscovery(
        trust,
        discover: () => completion.future,
        transport: (_) =>
            MockClient((_) async => http.Response(jsonEncode(identity()), 200)),
      );
      final attempt = d.ensureReady();
      d.invalidate();
      completion.complete(hints(['192.168.1.3']));
      await expectLater(attempt, throwsA(isA<LanDiscoveryException>()));
      expect(d.address, null);
    },
  );
  test(
    'A failed signed POST is never replayed or sent over public fallback',
    () async {
      var signed = 0;
      final d = SecureLanDiscovery(
        trust,
        discover: () async => hints(['192.168.1.3']),
        transport: (_) => MockClient((r) async {
          if (r.url.path == '/classroom-discovery/identity') {
            return http.Response(jsonEncode(identity()), 200);
          }
          signed++;
          throw http.ClientException('lost');
        }),
      );
      final api = ApiClient(
        url: 'http://192.168.1.9:8000',
        publicUrl: 'https://fyp.test.example',
        discovery: d,
        client: MockClient((_) async => throw StateError('No fallback')),
      );
      await expectLater(
        api.post('/api/v1/attendance/preflight-challenges', {}),
        throwsA(isA<ApiException>()),
      );
      expect(signed, 1);
      api.dispose();
    },
  );
  test(
    'Late old cancellation failure cannot discard a new paired transport',
    () async {
      final old = Completer<http.Response>();
      var ip = '192.168.1.3';
      final d = SecureLanDiscovery(
        trust,
        discover: () async => hints([ip]),
        transport: (address) => MockClient((r) async {
          if (r.url.path == '/classroom-discovery/identity') {
            return http.Response(jsonEncode(identity()), 200);
          }
          return old.future;
        }),
      );
      await d.ensureReady();
      final failed = expectLater(
        d.send(
          http.Request(
            'POST',
            Uri.parse('${trust.origin}/attendance/cancel/old'),
          ),
        ),
        throwsA(isA<http.ClientException>()),
      );
      d.invalidate();
      ip = '192.168.1.4';
      await d.ensureReady();
      old.completeError(http.ClientException('old cancellation failed'));
      await failed;
      expect(
        d.address,
        ip,
        reason: 'Only the failing transport may be invalidated',
      );
      d.invalidate();
    },
  );

  test(
    'Fresh PIN retry rediscovers paired HTTPS after failed face and server IP change',
    () async {
      var ip = '192.168.1.3';
      var probes = 0, starts = 0, faceRequests = 0, publicCalls = 0;
      final attempts = <String>[];
      final d = SecureLanDiscovery(
        trust,
        discover: () async => hints([ip]),
        transport: (address) => MockClient((r) async {
          expect(r.url.origin, trust.origin);
          if (r.url.path == '/classroom-discovery/identity') {
            probes++;
            return http.Response(jsonEncode(identity()), 200);
          }
          if (address != ip) throw http.ClientException('old server address');
          if (r.url.path == '/api/v1/networks/verifications') {
            return http.Response(jsonEncode({'result': 'PASS'}), 200);
          }
          if (r.url.path == '/attendance/start') {
            starts++;
            expect(jsonDecode(r.body)['pin'], '123456');
            final id = 'attempt-$starts';
            attempts.add(id);
            return http.Response(jsonEncode({'challenge_id': id}), 200);
          }
          if (r.url.path == '/verify-face') {
            faceRequests++;
            return http.Response(
              jsonEncode({
                'message': 'Face not matched.',
                'code': 'FACE_NOT_MATCHED',
              }),
              403,
            );
          }
          return http.Response('{}', 200);
        }),
      );
      final api = ApiClient(
        url: 'http://192.168.1.99:8000',
        publicUrl: 'https://fyp.test.example',
        discovery: d,
        client: MockClient((r) async {
          publicCalls++;
          expect(r.url.path, '/login', reason: 'No public attendance fallback');
          return http.Response(
            jsonEncode({
              'access_token': 'synthetic',
              'student': {'student_id': 'TEST'},
            }),
            200,
          );
        }),
      );
      await api.login('TEST', 'synthetic');
      expect(
        (await api.post('/api/v1/networks/verifications', {}) as Map)['result'],
        'PASS',
      );
      await api.post('/attendance/start', {'pin': '123456'});
      await api.post('/api/v1/attendance/preflight', {});
      await expectLater(
        api.post('/verify-face', {}),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'FACE_NOT_MATCHED'),
        ),
      );
      ip =
          '192.168.1.4'; // Server changes address without a phone network event.
      final retry =
          await api.post('/attendance/start', {'pin': '123456'}) as Map;
      await api.post('/api/v1/attendance/preflight', {});
      expect(retry['challenge_id'], 'attempt-2');
      expect(attempts, ['attempt-1', 'attempt-2']);
      expect(d.address, ip);
      expect(probes, greaterThanOrEqualTo(3));
      expect(starts, 2);
      expect(
        faceRequests,
        1,
        reason: 'Failed signed/biometric request never replayed',
      );
      expect(publicCalls, 1);
      api.dispose();
    },
  );

  test(
    'Fresh attempt preserves manual hint but revalidates its pinned identity',
    () async {
      var probes = 0;
      final d = fake([], onRequest: (_) => probes++);
      d.manualAddress('192.168.1.8');
      await d.ensureReady();
      await d.refresh();
      expect(d.address, '192.168.1.8');
      expect(probes, 2);
      d.invalidate();
    },
  );

  test(
    'First device prepare refreshes stale paired address before one key proof',
    () async {
      var ip = '192.168.1.3';
      var probes = 0, begun = 0, proved = 0;
      final keys = CandidateKeys();
      final d = SecureLanDiscovery(
        trust,
        discover: () async => hints([ip]),
        transport: (address) => MockClient((r) async {
          expect(r.url.origin, trust.origin);
          if (r.url.path == '/classroom-discovery/identity') {
            probes++;
            return http.Response(jsonEncode(identity()), 200);
          }
          if (address != ip) throw http.ClientException('obsolete address');
          if (r.url.path == '/api/v1/devices') {
            return http.Response(
              jsonEncode({'pending_enrollment_available': true, 'devices': []}),
              200,
            );
          }
          if (r.url.path == '/api/v1/devices/pending-registrations') {
            begun++;
            expect(jsonDecode(r.body)['device_name'], 'sh tablet');
            return http.Response(jsonEncode(candidate()), 201);
          }
          if (r.url.path.endsWith('/proof')) {
            proved++;
            return http.Response(jsonEncode(candidate('KEY_PROVEN')), 200);
          }
          return http.Response(jsonEncode({'result': 'PASS'}), 200);
        }),
      );
      final api = ApiClient(
        url: 'http://192.168.1.99:8000',
        publicUrl: 'https://fyp.test.example',
        discovery: d,
        client: MockClient((r) async {
          expect(
            r.url.path,
            '/login',
            reason: 'No public registration fallback',
          );
          return http.Response(
            jsonEncode({
              'access_token': 'synthetic',
              'student': {'student_id': 'TEST001'},
            }),
            200,
          );
        }),
      );
      await api.login('TEST001', 'synthetic');
      await api.post('/api/v1/networks/verifications', {});
      ip = '192.168.1.4';
      final service = PendingDeviceService(client: api, keys: keys);
      expect((await service.prepare('sh tablet'))['status'], 'KEY_PROVEN');
      expect(d.address, ip);
      expect(probes, 2);
      expect(begun, 1);
      expect(proved, 1);
      expect(keys.signed, 1);
      api.dispose();
    },
  );

  test(
    'Unreachable discovery blocks device preparation before key creation or proof',
    () async {
      final keys = CandidateKeys();
      final d = fake([], wifi: false);
      final api = ApiClient(
        url: 'http://192.168.1.9:8000',
        publicUrl: 'https://fyp.test.example',
        discovery: d,
        client: MockClient((r) async {
          expect(r.url.path, '/login');
          return http.Response(
            jsonEncode({
              'access_token': 'synthetic',
              'student': {'student_id': 'TEST001'},
            }),
            200,
          );
        }),
      );
      await api.login('TEST001', 'synthetic');
      await expectLater(
        PendingDeviceService(client: api, keys: keys).prepare('tablet'),
        throwsA(isA<ApiException>()),
      );
      expect(keys.created, 0);
      expect(keys.signed, 0);
      api.dispose();
    },
  );

  test(
    'Real TLS validates provisioned CA and hostname; rogue CA fails',
    () async {
      Future<void> verify(
        String folder,
        bool accepted, {
        LanTrust? installed,
      }) async {
        final ctx = SecurityContext()
          ..useCertificateChain('${fixture.path}/$folder/server.pem')
          ..usePrivateKey('${fixture.path}/$folder/server.key');
        final server = await HttpServer.bindSecure(
          InternetAddress.loopbackIPv4,
          0,
          ctx,
        );
        final sub = server.listen((request) async {
          request.response.headers.contentType = ContentType.json;
          request.response.write(jsonEncode(identity()));
          await request.response.close();
        });
        final d = SecureLanDiscovery(
          installed ?? trust,
          discover: () async => hints(['192.168.1.9']),
          connect: (_, _) =>
              Socket.startConnect(InternetAddress.loopbackIPv4, server.port),
        );
        try {
          if (accepted) {
            final rawProbe = d.createTransport('192.168.1.9');
            try {
              await rawProbe.get(
                Uri.parse('${trust.origin}/classroom-discovery/identity'),
              );
            } finally {
              rawProbe.close();
            }
            await d.ensureReady();
            expect(d.address, '192.168.1.9');
          } else {
            await expectLater(
              d.ensureReady(),
              throwsA(isA<LanDiscoveryException>()),
            );
            expect(d.address, null);
          }
        } finally {
          d.invalidate();
          await server.close(force: true);
          await sub.cancel();
        }
      }

      await verify('full', true);
      await verify('rogue', false);
      await verify(
        'full',
        false,
        installed: LanTrust.fromMap({
          ...publicTrust,
          'server_id': 'f' * 32,
          'hostname': 'fyp-${'f' * 32}.local',
        }, localMode: false),
      );
    },
  );
}
