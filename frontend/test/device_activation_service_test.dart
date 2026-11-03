import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/devices/services/device_activation_service.dart';

class ActivationKeys extends DeviceKeyStore {
  int signs = 0, created = 0;
  bool missing = false;
  String fingerprint = 'candidate-fingerprint';
  Future<void> Function()? beforeSign;
  @override
  Future<Map<String, dynamic>?> getPublicKey(String id) async =>
      missing ? null : {'public_key_fingerprint': fingerprint};
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String id) async {
    created++;
    throw StateError('Never rotate/create');
  }

  @override
  Future<String> sign(String id, String payload) async {
    signs++;
    if (beforeSign != null) await beforeSign!();
    return 'candidate-signature';
  }
}

class ActivationFixture {
  final keys = ActivationKeys();
  bool unavailable = false,
      active = false,
      lostResponse = false,
      forged = false,
      invalidPayload = false,
      rejectSignature = false;
  String? readinessError;
  Completer<http.Response>? delayedReadiness;
  String pendingId = 'pending',
      candidateId = 'tablet',
      fingerprint = 'candidate-fingerprint';
  int confirms = 0;
  final paths = <String>[];
  final expiry = DateTime.now()
      .toUtc()
      .add(const Duration(seconds: 60))
      .toIso8601String();
  Map<String, dynamic> get binding => {
    'success': true,
    'pending_registration_id': pendingId,
    'candidate_device_id': candidateId,
    'public_key_fingerprint': fingerprint,
    'operation': 'enroll_second_device',
    'slot_number': 2,
  };
  Map<String, dynamic> get device => {
    'device_id': candidateId,
    'public_key_fingerprint': fingerprint,
    'slot_number': 2,
    'status': 'ACTIVE',
  };
  http.Response response(Object body, int status) => http.Response(
    jsonEncode(body),
    status,
    headers: {'content-type': 'application/json'},
  );
  late final client = ApiClient(
    client: MockClient((request) async {
      final path = request.url.path;
      if (path == '/login') {
        return response({
          'access_token': 'fixture-token',
          'student': {'student_id': jsonDecode(request.body)['student_id']},
        }, 200);
      }
      paths.add(path);
      if (request.headers['Authorization'] != 'Bearer fixture-token') {
        throw StateError('Missing bearer authentication');
      }
      if (path.endsWith('/activation-status')) {
        return response({
          ...binding,
          'status': active ? 'ACTIVE' : 'NOT_ACTIVE',
          'attendance_authorized': false,
          'maximum_active_devices': 2,
          'active_count': active ? 2 : 1,
          'device': active ? device : null,
        }, 200);
      }
      if (path.endsWith('/activation-readiness')) {
        if ((jsonDecode(request.body) as Map).isNotEmpty) {
          throw StateError('Readiness accepts no PASS flags');
        }
        if (delayedReadiness != null) return delayedReadiness!.future;
        if (unavailable || readinessError != null) {
          return response({
            'success': false,
            'code': readinessError ?? 'APPROVAL_UNAVAILABLE',
            'message': 'Trusted biometric approval unavailable or invalid.',
          }, readinessError == null ? 503 : 410);
        }
        return response({
          ...binding,
          'status': 'ELIGIBLE',
          'approval_id': 'grant',
          'trusted_template_revision_id': 'revision',
          'biometric_result_id': 'trusted-result',
          'expires_at': expiry,
        }, 200);
      }
      if (path.endsWith('/activation-challenges')) {
        if (jsonDecode(request.body)['approval_id'] != 'grant') {
          throw StateError('Wrong grant');
        }
        final values = {
          ...binding,
          'approval_id': 'grant',
          'trusted_template_revision_id': 'revision',
          'biometric_result_id': 'trusted-result',
          'challenge_id': 'nonce',
          'expires_at': expiry,
        };
        final payload = {
          ...values,
          'version': 1,
          'purpose': invalidPayload ? 'attendance' : 'device_activation',
          'student_id': 'TEST001',
          'nonce': 'random-server-nonce',
        };
        return response({
          ...values,
          'algorithm': 'ECDSA_P256_SHA256',
          'signature_encoding': 'base64-DER',
          'signing_payload': base64Encode(utf8.encode(jsonEncode(payload))),
        }, 201);
      }
      if (path.endsWith('/activate')) {
        confirms++;
        final submitted = jsonDecode(request.body);
        if (submitted['challenge_id'] != 'nonce' ||
            submitted['approval_id'] != 'grant' ||
            submitted['signature'] != 'candidate-signature') {
          throw StateError('Incorrect activation signature contract');
        }
        if (rejectSignature) {
          return response({
            'success': false,
            'code': 'INVALID_ACTIVATION_SIGNATURE',
            'message': 'Signature rejected.',
          }, 403);
        }
        active = true;
        if (lostResponse) {
          throw http.ClientException('lost confirmation response');
        }
        return response({
          'success': true,
          'attendance_authorized': false,
          'device': {
            ...device,
            if (forged) 'public_key_fingerprint': 'other-key',
          },
        }, 200);
      }
      throw StateError('Forbidden endpoint $path');
    }),
  );
  late final service = DeviceActivationService(client: client, keys: keys);
  Future<void> login() => client.login('TEST001', 'fixture');
}

void main() {
  test(
    'Automatic readiness, retained-key signing and confirmed ACTIVE uses only device APIs',
    () async {
      final f = ActivationFixture();
      await f.login();
      final device = await f.service.activate('pending');
      expect(device['status'], 'ACTIVE');
      expect(f.keys.signs, 1);
      expect(f.keys.created, 0);
      expect(f.confirms, 1);
      expect(
        f.paths.every(
          (p) => p.startsWith('/api/v1/devices/pending-registrations/'),
        ),
        isTrue,
      );
    },
  );
  test(
    'Unavailable or expired trusted approval never signs or claims ACTIVE',
    () async {
      for (final code in [
        null,
        'APPROVAL_EXPIRED',
        'BIOMETRIC_TRUST_REQUIRED',
      ]) {
        final f = ActivationFixture()
          ..unavailable = true
          ..readinessError = code;
        await f.login();
        await expectLater(
          f.service.activate('pending'),
          throwsA(isA<ApiException>()),
        );
        expect(f.keys.signs, 0);
        expect(f.confirms, 0);
        expect(f.active, isFalse);
      }
    },
  );
  test(
    'Candidate key missing or fingerprint mismatch never creates a key or signs',
    () async {
      for (final missing in [true, false]) {
        final f = ActivationFixture();
        f.keys.missing = missing;
        f.keys.fingerprint = 'wrong-key';
        await f.login();
        await expectLater(
          f.service.activate('pending'),
          throwsA(isA<ApiException>()),
        );
        expect(f.keys.signs, 0);
        expect(f.keys.created, 0);
        expect(f.confirms, 0);
      }
    },
  );
  test('Session change while signing prevents submission', () async {
    final f = ActivationFixture();
    await f.login();
    f.keys.beforeSign = () async {
      await f.client.login('OTHER', 'fixture');
    };
    await expectLater(
      f.service.activate('pending'),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'SESSION_CHANGED'),
      ),
    );
    expect(f.confirms, 0);
  });
  test(
    'Duplicate automatic calls share one signature and confirmation',
    () async {
      final f = ActivationFixture();
      await f.login();
      await Future.wait([
        f.service.activate('pending'),
        f.service.activate('pending'),
      ]);
      expect(f.keys.signs, 1);
      expect(f.confirms, 1);
    },
  );
  test(
    'Lost confirmation is reconciled without replaying the signed nonce',
    () async {
      final f = ActivationFixture()..lostResponse = true;
      await f.login();
      expect((await f.service.activate('pending'))['status'], 'ACTIVE');
      expect(f.confirms, 1);
      expect(f.keys.signs, 1);
      expect(f.paths.where((p) => p.endsWith('/activation-status')).length, 2);
    },
  );
  test('Already ACTIVE is recovered without new grant or signing', () async {
    final f = ActivationFixture()..active = true;
    await f.login();
    expect((await f.service.activate('pending'))['status'], 'ACTIVE');
    expect(f.keys.signs, 0);
    expect(f.paths.length, 1);
  });
  test(
    'Cross-operation payload and incompatible ACTIVE device are rejected',
    () async {
      final wrong = ActivationFixture()..invalidPayload = true;
      await wrong.login();
      await expectLater(
        wrong.service.activate('pending'),
        throwsA(isA<ApiException>()),
      );
      expect(wrong.keys.signs, 0);
      final forged = ActivationFixture()..forged = true;
      await forged.login();
      await expectLater(
        forged.service.activate('pending'),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('Invalid signature response is visible with no blind retry', () async {
    final f = ActivationFixture()..rejectSignature = true;
    await f.login();
    await expectLater(
      f.service.activate('pending'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          'INVALID_ACTIVATION_SIGNATURE',
        ),
      ),
    );
    expect(f.confirms, 1);
  });
  testWidgets('Hung readiness times out with no signature or activation', (
    tester,
  ) async {
    final f = ActivationFixture()
      ..delayedReadiness = Completer<http.Response>();
    await f.login();
    final checked = expectLater(
      f.service.activate('pending'),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'ACTIVATION_TIMEOUT'),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 16));
    await checked;
    expect(f.keys.signs, 0);
    expect(f.confirms, 0);
    f.delayedReadiness!.complete(f.response({}, 503));
    await tester.pump();
  });
}
