import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/services/lan_discovery.dart';
import 'package:frontend/modules/devices/screens/my_device_screen.dart';
import 'package:frontend/modules/devices/services/device_api.dart';
import 'device_verification_test.dart' show StatusVerification;

class RecoveringDeviceListing extends DeviceApi {
  int calls = 0;
  @override
  Future<Map<String, dynamic>> listDevices() async {
    calls++;
    if (calls == 1) {
      throw const ApiException(
        'Paired server unavailable',
        0,
        'PAIRED_CLASSROOM_SERVER_NOT_FOUND',
      );
    }
    return {'devices': [], 'initial_registration_available': false};
  }
}

void main() {
  late Directory fixture;
  late Map<String, dynamic> publicTrust;
  late LanTrust trust;
  setUpAll(() async {
    fixture = await Directory.systemTemp.createTemp('fyp-lan-test-');
    final python =
        Platform.environment['FYP_TEST_PYTHON'] ??
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

  testWidgets(
    'My Device offers pinned manual recovery and reloads status after connection',
    (tester) async {
      final original = ApiClient.instance;
      final d = fake([]);
      final api = ApiClient(
        url: 'http://192.168.1.9:8000',
        publicUrl: 'https://fyp.test.example',
        discovery: d,
        client: MockClient((_) async => throw StateError('No public recovery')),
      );
      ApiClient.instance = api;
      final listing = RecoveringDeviceListing();
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: MyDeviceScreen(
              api: listing,
              verificationService: StatusVerification()..fail = true,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Classroom connection'), findsOneWidget);
        await tester.enterText(find.byType(TextField), '192.168.1.8');
        final button = find.text('Verify paired server at this address');
        await tester.ensureVisible(button);
        await tester.runAsync(() async {
          await tester.tap(button);
          await Future<void>.delayed(const Duration(milliseconds: 50));
        });
        await tester.pumpAndSettle();
        expect(listing.calls, 2);
        expect(d.address, '192.168.1.8');
        expect(find.text('Registered key is missing'), findsOneWidget);
        expect(find.text('Automatic device verification: PASS'), findsNothing);
        // Connectivity recovery must not convert a key authorization error to PASS.
      } finally {
        await tester.pumpWidget(const SizedBox());
        ApiClient.instance = original;
        api.dispose();
      }
    },
  );
}
