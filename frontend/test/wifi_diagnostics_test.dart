import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/networks/services/wifi_diagnostics.dart';
import 'package:frontend/modules/networks/widgets/wifi_diagnostics_card.dart';
import 'package:frontend/modules/networks/screens/network_verification_screen.dart';
import 'package:frontend/modules/networks/services/network_verification_api.dart';

Map<String, dynamic> sample({
  String status = 'AVAILABLE',
  String permission = 'PRECISE_GRANTED',
  String type = 'WIFI',
  bool enabled = true,
  bool location = true,
}) => {
  'status': status,
  'permission_status': permission,
  'connection_type': type,
  'wifi_enabled': enabled,
  'wifi_connected': enabled && type == 'WIFI',
  'location_enabled': location,
  'ssid': status == 'AVAILABLE' ? 'Campus Demo' : null,
  'bssid': status == 'AVAILABLE' ? '10:22:33:44:55:66' : null,
  'rssi_dbm': status == 'AVAILABLE' ? -62 : null,
  'observed_at_ms': 1793940000000,
};

class FakeWifi extends WifiDiagnostics {
  Map<String, dynamic> data = sample();
  int reads = 0, requests = 0;
  String? settings;
  Object? error;
  Completer<WifiReading>? waiting;
  @override
  Future<WifiReading> read() async {
    reads++;
    if (error != null) throw error!;
    return waiting?.future ?? WifiReading.fromMap(data);
  }

  @override
  Future<void> requestPermission() async {
    requests++;
  }

  @override
  Future<void> openSettings(String page) async {
    settings = page;
  }
}

class BackendFixture extends NetworkVerificationApi {
  int calls = 0;
  bool authorized = true;
  @override
  Future<Map<String, dynamic>> check() async {
    calls++;
    return {
      'result': authorized ? 'PASS' : 'FAIL',
      'reason_code': authorized
          ? 'NETWORK_AUTHORIZED'
          : 'NETWORK_NOT_AUTHORIZED',
      'message': 'Synthetic backend CIDR decision.',
      'source_ip': '192.0.2.10',
      'matched_policy_id': 'sim',
      'verified_at': '2026-11-06T12:00:00+08:00',
    };
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('attendance/wifi_diagnostics');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  tearDown(() => messenger.setMockMethodCallHandler(channel, null));

  test(
    'Channel reads Android values and exposes no authorization result',
    () async {
      final methods = <String>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        methods.add(call.method);
        return sample()..['ssid'] = '"Campus Demo"';
      });
      final value = await const WifiDiagnostics().read();
      expect(value.ssid, 'Campus Demo');
      expect(value.bssid, '10:22:33:44:55:66');
      expect(value.rssi, -62);
      expect(value.permission, 'PRECISE_GRANTED');
      expect(methods, [
        'read',
      ]); // No permission prompt or backend request on read.
    },
  );

  test('Unknown/redacted SSID BSSID and invalid RSSI remain unavailable', () {
    for (final bssid in [
      '02:00:00:00:00:00',
      '00:00:00:00:00:00',
      'ff:ff:ff:ff:ff:ff',
      'bad',
    ]) {
      final value = WifiReading.fromMap({
        'ssid': '<unknown ssid>',
        'bssid': bssid,
        'rssi_dbm': -127,
      });
      expect(value.ssid, isNull);
      expect(value.bssid, isNull);
      expect(value.rssi, isNull);
    }
    expect(WifiReading.fromMap({'rssi_dbm': 0}).rssi, isNull);
    expect(
      WifiReading.fromMap({'ssid': '  genuine spaces  '}).ssid,
      '  genuine spaces  ',
    );
  });

  testWidgets('Native snapshot timeout is bounded', (tester) async {
    final pending = Completer<Map<String, dynamic>>();
    messenger.setMockMethodCallHandler(channel, (_) => pending.future);
    final checked = expectLater(
      const WifiDiagnostics().read(),
      throwsA(isA<TimeoutException>()),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 6));
    await checked;
    pending.complete(sample());
    await tester.pump();
  });

  for (final size in [
    const Size(390, 844),
    const Size(844, 390),
    const Size(1280, 800),
  ]) {
    testWidgets('Reading and long SSID fit portrait/landscape $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final wifi = FakeWifi()
        ..data['ssid'] = 'A long classroom wireless network name';
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: WifiDiagnosticsCard(diagnostics: wifi),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('RSSI: -62 dBm'), findsOneWidget);
      expect(find.text('BSSID: 10:22:33:44:55:66'), findsOneWidget);
      expect(
        find.text('Local readings only; not attendance authorization.'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });
  }

  for (final permission in ['NOT_REQUESTED', 'DENIED', 'APPROXIMATE_ONLY']) {
    testWidgets('$permission requires explicit user permission action', (
      tester,
    ) async {
      final wifi = FakeWifi()
        ..data = sample(status: 'PERMISSION_REQUIRED', permission: permission);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: WifiDiagnosticsCard(diagnostics: wifi),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(wifi.requests, 0);
      expect(
        find.text('Location permission: ${permission.replaceAll('_', ' ')}'),
        findsOneWidget,
      );
      await tester.tap(find.text('Allow precise location'));
      await tester.pumpAndSettle();
      expect(wifi.requests, 1);
      expect(find.text('SSID: Unavailable / redacted'), findsOneWidget);
    });
  }

  testWidgets('Permanently denied opens app settings, never silently grants', (
    tester,
  ) async {
    final wifi = FakeWifi()
      ..data = sample(
        status: 'PERMISSION_REQUIRED',
        permission: 'SETTINGS_REQUIRED',
      );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: WifiDiagnosticsCard(diagnostics: wifi),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open app permissions'));
    await tester.pump();
    expect(wifi.settings, 'app');
    expect(wifi.requests, 0);
  });

  testWidgets('Location off, Wi-Fi off and mobile data are distinct', (
    tester,
  ) async {
    final wifi = FakeWifi()
      ..data = sample(status: 'LOCATION_DISABLED', location: false);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: WifiDiagnosticsCard(diagnostics: wifi),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Location services: Off'), findsOneWidget);
    await tester.tap(find.text('Open Location settings'));
    await tester.pump();
    expect(wifi.settings, 'location');
    wifi.data = sample(status: 'WIFI_OFF', type: 'MOBILE_DATA', enabled: false);
    await tester.tap(find.text('Refresh'));
    await tester.pumpAndSettle();
    expect(find.text('Connection type: MOBILE DATA'), findsOneWidget);
    expect(find.text('Wi-Fi: Off'), findsOneWidget);
    expect(find.text('RSSI: Unavailable'), findsOneWidget);
  });

  testWidgets('Error stops loading, clears old readings and allows retry', (
    tester,
  ) async {
    final wifi = FakeWifi();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: WifiDiagnosticsCard(diagnostics: wifi),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    wifi.error = TimeoutException('synthetic timeout');
    await tester.tap(find.text('Refresh'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Wi-Fi reading unavailable.'), findsOneWidget);
    expect(find.text('SSID: Campus Demo'), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    wifi.error = null;
    await tester.tap(find.text('Refresh'));
    await tester.pumpAndSettle();
    expect(find.text('SSID: Campus Demo'), findsOneWidget);
  });

  testWidgets('Late reading after disposal does not update UI', (tester) async {
    final wifi = FakeWifi()..waiting = Completer<WifiReading>();
    await tester.pumpWidget(
      MaterialApp(home: WifiDiagnosticsCard(diagnostics: wifi)),
    );
    await tester.pump();
    await tester.pumpWidget(const SizedBox());
    wifi.waiting!.complete(WifiReading.fromMap(sample()));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Resume refreshes permission state and discards an old in-flight reading',
    (tester) async {
      final wifi = FakeWifi();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: WifiDiagnosticsCard(diagnostics: wifi),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final old = Completer<WifiReading>();
      wifi.waiting = old;
      await tester.tap(find.text('Refresh'));
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      old.complete(WifiReading.fromMap(sample()..['ssid'] = 'Stale AP'));
      await tester.pump();
      wifi.waiting = null;
      wifi.data = sample(status: 'PERMISSION_REQUIRED', permission: 'DENIED');
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('SSID: Stale AP'), findsNothing);
      expect(find.text('Location permission: DENIED'), findsOneWidget);
      expect(find.text('SSID: Unavailable / redacted'), findsOneWidget);
    },
  );

  testWidgets(
    'Wi-Fi refresh leaves backend CIDR result and call count unchanged',
    (tester) async {
      final backend = BackendFixture();
      final wifi = FakeWifi();
      await tester.pumpWidget(
        MaterialApp(
          home: NetworkVerificationScreen(api: backend, wifiDiagnostics: wifi),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Network verification: PASS'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Refresh'),
        150,
        scrollable: find.byType(Scrollable).first,
      );
      final backendCalls = backend.calls;
      final wifiReads = wifi.reads;
      await tester.tap(find.text('Refresh'));
      await tester.pumpAndSettle();
      expect(backend.calls, backendCalls);
      expect(wifi.reads, wifiReads + 1);
      await tester.scrollUntilVisible(
        find.text('Network verification: PASS'),
        -200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Network verification: PASS'), findsOneWidget);
    },
  );

  for (final authorized in [true, false]) {
    testWidgets(
      'Denied Wi-Fi permission cannot change backend verdict $authorized',
      (tester) async {
        final backend = BackendFixture()..authorized = authorized;
        final wifi = FakeWifi()
          ..data = sample(status: 'PERMISSION_REQUIRED', permission: 'DENIED');
        await tester.pumpWidget(
          MaterialApp(
            home: NetworkVerificationScreen(
              api: backend,
              wifiDiagnostics: wifi,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          find.text('Network verification: ${authorized ? 'PASS' : 'FAIL'}'),
          findsOneWidget,
        );
        await tester.scrollUntilVisible(
          find.text('Allow precise location'),
          120,
          scrollable: find.byType(Scrollable).first,
        );
        // Scrolling may mount another diagnostic section; settle its metadata-only
        // platform call before checking Wi-Fi/backend independence.
        await tester.pumpAndSettle();
        expect(wifi.requests, 0);
        expect(backend.calls, 1);
      },
    );
  }
}
