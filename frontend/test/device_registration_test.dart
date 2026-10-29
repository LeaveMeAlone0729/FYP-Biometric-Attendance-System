import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/modules/devices/screens/my_device_screen.dart';
import 'package:frontend/modules/devices/services/device_api.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/screens/student_profile_screen.dart';
import 'package:frontend/services/api_client.dart';

final registered = <String, dynamic>{
  'device_id': 'device-1',
  'device_name': 'My phone',
  'device_model': 'Test Android',
  'platform': 'android',
  'status': 'ACTIVE',
  'public_key_fingerprint': 'fingerprint',
  'registered_at': '2026-10-30T12:00:00+08:00',
};

class FakeKeys extends DeviceKeyStore {
  int created = 0, signed = 0;
  bool available = true;
  @override
  Future<Map<String, dynamic>?> getPublicKey(String studentId) async =>
      available ? {'public_key_fingerprint': 'fingerprint'} : null;
  @override
  Future<Map<String, dynamic>> getOrCreateKey(String studentId) async {
    created++;
    return {'public_key_spki': 'public', 'device_model': 'Test Android'};
  }

  @override
  Future<String> sign(String studentId, String payload) async {
    signed++;
    if (payload != 'payload') throw StateError('Wrong signing payload');
    return 'signature';
  }
}

class FakeDevices extends DeviceApi {
  Map<String, dynamic>? device;
  bool failConfirm = false, loseResponse = false, failFetch = false;
  int confirmed = 0;
  @override
  Future<Map<String, dynamic>?> current() async {
    if (failFetch) throw const ApiException('Cannot reach server');
    return device;
  }

  @override
  Future<Map<String, dynamic>> begin({
    required String publicKey,
    required String deviceName,
    required String deviceModel,
  }) async => {
    'registration_id': 'registration-1',
    'signing_payload': 'payload',
  };
  @override
  Future<Map<String, dynamic>> confirm(
    String registrationId,
    String signature,
  ) async {
    confirmed++;
    if (failConfirm) throw const ApiException('Signature denied', 403);
    device = Map.of(registered);
    if (loseResponse) throw const ApiException('Connection lost');
    return device!;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'Device REST calls use bearer authentication and send only public proof',
    () async {
      final calls = <String>[];
      final transport = ApiClient(
        client: MockClient((request) async {
          calls.add(request.url.path);
          if (request.url.path == '/login') {
            return http.Response(
              jsonEncode({
                'access_token': 'token',
                'student': {'student_id': 'TEST001'},
              }),
              200,
            );
          }
          expect(request.headers['Authorization'], 'Bearer token');
          if (request.url.path.endsWith('registration-challenges')) {
            final body = jsonDecode(request.body) as Map;
            expect(body.keys.toSet(), {
              'public_key_spki',
              'platform',
              'device_name',
              'device_model',
            });
            return http.Response(
              '{"registration_id":"registration-1","signing_payload":"payload"}',
              201,
            );
          }
          if (request.url.path.endsWith('registrations')) {
            expect(jsonDecode(request.body), {
              'registration_id': 'registration-1',
              'signature': 'signature',
            });
            return http.Response(jsonEncode({'device': registered}), 201);
          }
          return http.Response('{"device":null}', 200);
        }),
      );
      await transport.login('TEST001', 'password');
      final api = DeviceApi(transport);
      expect(await api.current(), isNull);
      await api.begin(
        publicKey: 'public',
        deviceName: 'Phone',
        deviceModel: 'Android',
      );
      expect(
        (await api.confirm('registration-1', 'signature'))['status'],
        'ACTIVE',
      );
      expect(calls.length, 4);
    },
  );

  test(
    'Keystore channel exposes public operations and exact base64 payload only',
    () async {
      final calls = <MethodCall>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(DeviceKeyStore.channel, (call) async {
            calls.add(call);
            return call.method == 'sign'
                ? 'DER-signature'
                : {'public_key_spki': 'public'};
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(DeviceKeyStore.channel, null),
      );
      const keys = DeviceKeyStore();
      await keys.getPublicKey('TEST001');
      await keys.getOrCreateKey('TEST001');
      expect(await keys.sign('TEST001', 'base64-payload'), 'DER-signature');
      expect(calls.map((c) => c.method), [
        'getPublicKey',
        'getOrCreateKey',
        'sign',
      ]);
      expect(calls.last.arguments, {
        'student_id': 'TEST001',
        'signing_payload': 'base64-payload',
      });
    },
  );

  testWidgets('Registers and shows ACTIVE device without replacing a key', (
    tester,
  ) async {
    final api = FakeDevices();
    final keys = FakeKeys();
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(api: api, keyStore: keys, studentId: 'TEST001'),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'My phone');
    await tester.tap(find.text('Register this device'));
    await tester.pumpAndSettle();
    expect(find.text('Status: ACTIVE'), findsOneWidget);
    expect(keys.created, 1);
    expect(keys.signed, 1);
    expect(api.confirmed, 1);
    expect(find.text('Register this device'), findsNothing);
  });

  testWidgets('Viewing another installation never generates or replaces keys', (
    tester,
  ) async {
    final api = FakeDevices()..device = Map.of(registered);
    final keys = FakeKeys()..available = false;
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(api: api, keyStore: keys, studentId: 'TEST001'),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining('replacement requires approval'),
      findsOneWidget,
    );
    expect(find.text('Register this device'), findsNothing);
    expect(keys.created, 0);
    expect(keys.signed, 0);
  });

  testWidgets(
    'Lost confirmation response is recovered through current device',
    (tester) async {
      final api = FakeDevices()..loseResponse = true;
      await tester.pumpWidget(
        MaterialApp(
          home: MyDeviceScreen(
            api: api,
            keyStore: FakeKeys(),
            studentId: 'TEST001',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'My phone');
      await tester.tap(find.text('Register this device'));
      await tester.pumpAndSettle();
      expect(find.text('Status: ACTIVE'), findsOneWidget);
      expect(find.text('Connection lost'), findsNothing);
    },
  );

  testWidgets(
    'Validation and server errors leave registration retry available',
    (tester) async {
      final api = FakeDevices()..failConfirm = true;
      await tester.pumpWidget(
        MaterialApp(
          home: MyDeviceScreen(
            api: api,
            keyStore: FakeKeys(),
            studentId: 'TEST001',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Register this device'));
      await tester.pumpAndSettle();
      expect(find.text('Enter a name for this device.'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'Phone');
      await tester.tap(find.text('Register this device'));
      await tester.pumpAndSettle();
      expect(find.text('Signature denied'), findsOneWidget);
      expect(find.text('Register this device'), findsOneWidget);
    },
  );

  testWidgets('Failed status fetch cannot start registration', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: MyDeviceScreen(
          api: FakeDevices()..failFetch = true,
          keyStore: FakeKeys(),
          studentId: 'TEST001',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Cannot reach server'), findsOneWidget);
    expect(find.text('Register this device'), findsNothing);
  });

  testWidgets('Existing student profile exposes My Device', (tester) async {
    final previous = ApiClient.instance;
    ApiClient.instance = ApiClient(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({
            'student_id': 'TEST001',
            'name': 'Student',
            'email': 'student@example.test',
            'biometric_status': 'not_registered',
            'programme_code': 'CS',
            'group_name': 'G1',
          }),
          200,
        ),
      ),
    );
    addTearDown(() => ApiClient.instance = previous);
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: StudentProfileScreen())),
    );
    await tester.pumpAndSettle();
    expect(find.text('My Device'), findsOneWidget);
  });
}
