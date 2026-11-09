import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/networks/services/ble_diagnostics.dart';
import 'package:frontend/modules/networks/services/wifi_diagnostics.dart';
import 'package:frontend/modules/networks/widgets/ble_diagnostics_card.dart';

const testUuid = '7d9a6c10-326a-4c60-9e01-1ef000000001';
Map<String, dynamic> advertiser({
  List<int> samples = const [-61, -65, -63, -62],
}) => {
  'scan_id': 1,
  'name': 'FYP classroom beacon',
  'service_uuids': [testUuid],
  'service_data': [],
  'manufacturer_data': [],
  'rssi_dbm': samples.last,
  'rssi_samples': samples,
  'advertisement_count': samples.length,
  'last_seen_age_ms': 200,
  'last_seen_at_ms': 1794000000000,
};
Map<String, dynamic> state({
  String code = 'READY',
  bool bluetooth = true,
  String permission = 'GRANTED',
  bool devices = false,
}) => {
  'status': code,
  'supported': true,
  'bluetooth_enabled': bluetooth,
  'scan_permission': permission,
  'connect_permission': 'GRANTED',
  'location_permission': 'PRECISE_GRANTED',
  'location_enabled': true,
  'scan_duration_ms': code == 'COMPLETE' ? 8000 : 0,
  'devices': devices ? [advertiser()] : [],
};

class FakeBle extends BleDiagnostics {
  Map<String, dynamic> metadata = state(),
      data = state(code: 'COMPLETE', devices: true);
  int scans = 0,
      statuses = 0,
      stops = 0,
      cancels = 0,
      permissions = 0,
      enables = 0,
      elapsed = 0;
  String? settings;
  Object? error;
  Completer<BleSnapshot>? waiting;
  @override
  Future<BleSnapshot> status() async {
    statuses++;
    return BleSnapshot.fromMap(metadata);
  }

  @override
  Future<BleSnapshot> scan({String? requestId}) async {
    scans++;
    if (error != null) throw error!;
    return waiting?.future ??
        BleSnapshot.fromMap(data, elapsedMilliseconds: () => elapsed);
  }

  @override
  Future<void> stop({String? requestId}) async {
    stops++;
    waiting?.complete(
      BleSnapshot.fromMap(state(code: 'STOPPED', devices: true)),
    );
  }

  @override
  Future<void> cancel({String? requestId}) async {
    cancels++;
  }

  @override
  Future<void> requestPermission() async {
    permissions++;
  }

  @override
  Future<void> enableBluetooth() async {
    enables++;
  }

  @override
  Future<void> openSettings(String page) async {
    settings = page;
  }
}

class LocationPermission extends WifiDiagnostics {
  int requests = 0;
  @override
  Future<void> requestPermission() async {
    requests++;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('attendance/ble_diagnostics');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  tearDown(() => messenger.setMockMethodCallHandler(channel, null));

  test(
    'platform scan returns ephemeral identifiers and computes median from actual samples',
    () async {
      final calls = <String>[];
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call.method);
        return state(code: 'COMPLETE', devices: true);
      });
      final result = await const BleDiagnostics().scan();
      expect(calls, ['scan']);
      expect(result.advertisements.single.medianRssi, -62.5);
      expect(result.advertisements.single.serviceUuids, [testUuid]);
      expect(result.advertisements.single.rssi, -62);
      expect(result.scanDurationMs, 8000);
    },
  );
  test('odd/even median and advertisement age use monotonic delivery age', () {
    var elapsed = 0;
    final ad = BleAdvertisement.fromMap(
      advertiser(samples: [-80, -50, -60]),
      elapsedMilliseconds: () => elapsed,
    );
    expect(ad.medianRssi, -60);
    elapsed = 12000;
    expect(ad.ageSeconds, 12.2);
  });
  test('invalid RSSI/timing/error snapshot cannot become usable discovery', () {
    for (final update in [
      {'rssi_dbm': 127},
      {'last_seen_age_ms': -1},
      {'advertisement_count': 0},
      {'scan_id': 0},
    ]) {
      expect(
        () => BleAdvertisement.fromMap({...advertiser(), ...update}),
        throwsA(anything),
      );
    }
    expect(
      () => BleSnapshot.fromMap(state(code: 'BLE_SCAN_FAILED', devices: true)),
      throwsFormatException,
    );
  });
  test(
    'permissions and Bluetooth enable use explicit platform requests only',
    () async {
      final calls = <String>[];
      final location = LocationPermission();
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call.method);
        if (call.method == 'status') {
          return {...state(), 'location_permission': 'DENIED'};
        }
        return null;
      });
      final service = BleDiagnostics(location: location);
      await service.requestPermission();
      await service.enableBluetooth();
      expect(calls, ['requestPermission', 'status', 'enableBluetooth']);
      expect(location.requests, 1);
      expect(calls, isNot(contains('scan')));
    },
  );
  test(
    'denied Nearby Devices does not start a second location prompt',
    () async {
      final location = LocationPermission();
      messenger.setMockMethodCallHandler(
        channel,
        (call) async =>
            call.method == 'status' ? state(permission: 'DENIED') : null,
      );
      await BleDiagnostics(location: location).requestPermission();
      expect(location.requests, 0);
    },
  );
  testWidgets('channel timeout cancels without trusting late discovery', (
    tester,
  ) async {
    final delayed = Completer<Map<String, dynamic>>();
    int cancels = 0;
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'cancel') {
        cancels++;
        return null;
      }
      return delayed.future;
    });
    final pending = const BleDiagnostics().scan();
    final expected = expectLater(pending, throwsA(isA<TimeoutException>()));
    await tester.pump();
    await tester.pump(const Duration(seconds: 11));
    await expected;
    await tester.pump();
    expect(cancels, 1);
    delayed.complete(state(code: 'COMPLETE', devices: true));
    await tester.pump();
  });

  Future<void> show(WidgetTester tester, FakeBle fake) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: BleDiagnosticsCard(diagnostics: fake),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> scan(WidgetTester tester) async {
    await tester.ensureVisible(find.text('Scan BLE (8 seconds)'));
    await tester.tap(find.text('Scan BLE (8 seconds)'));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'open checks status only; explicit scan displays timestamp RSSI identifiers and duration',
    (tester) async {
      final f = FakeBle();
      await show(tester, f);
      expect(f.scans, 0);
      expect(f.permissions, 0);
      expect(f.enables, 0);
      await scan(tester);
      expect(f.scans, 1);
      for (final text in [
        'Bluetooth: ON',
        'Scan duration: 8000 ms',
        'Detected advertisers: 1',
        'Service UUID: $testUuid',
        'RSSI: -62 dBm; median: -62.5 dBm',
        'RSSI samples: 4; advertisements: 4',
      ]) {
        expect(find.text(text), findsOneWidget);
      }
      expect(find.textContaining('Last advertisement:'), findsOneWidget);
      expect(find.textContaining('Advertisement age:'), findsOneWidget);
      expect(find.textContaining('PASS'), findsNothing);
    },
  );
  for (final code in [
    'BLE_PERMISSION_REQUIRED',
    'LOCATION_PERMISSION_REQUIRED',
    'LOCATION_DISABLED',
    'BLE_UNSUPPORTED',
    'BLE_SCAN_FAILED',
    'BLE_SCAN_RATE_LIMITED',
  ]) {
    testWidgets('$code stops spinner and does not retain advertisements', (
      tester,
    ) async {
      final f = FakeBle()..data = state(code: code);
      await show(tester, f);
      await scan(tester);
      expect(find.byKey(const ValueKey('ble-progress')), findsNothing);
      expect(find.textContaining('Service UUID:'), findsNothing);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Scan BLE (8 seconds)'),
            )
            .onPressed,
        isNotNull,
      );
    });
  }
  testWidgets(
    'Bluetooth OFF offers system prompt and never enables on opening',
    (tester) async {
      final f = FakeBle()
        ..metadata = state(code: 'BLUETOOTH_OFF', bluetooth: false);
      await show(tester, f);
      expect(find.text('Bluetooth: OFF'), findsOneWidget);
      expect(f.enables, 0);
      await tester.ensureVisible(find.text('Enable Bluetooth'));
      await tester.tap(find.text('Enable Bluetooth'));
      await tester.pumpAndSettle();
      expect(f.enables, 1);
    },
  );
  testWidgets('settings-required denial clearly guides to app settings', (
    tester,
  ) async {
    final f = FakeBle()
      ..metadata = state(
        code: 'BLE_PERMISSION_REQUIRED',
        permission: 'SETTINGS_REQUIRED',
      );
    await show(tester, f);
    expect(
      find.textContaining('Android app settings may be required'),
      findsOneWidget,
    );
    await tester.ensureVisible(find.text('App permissions'));
    await tester.tap(find.text('App permissions'));
    await tester.pumpAndSettle();
    expect(f.settings, 'app');
  });
  testWidgets('empty window is not classroom FAIL or PASS', (tester) async {
    final f = FakeBle()..data = state(code: 'COMPLETE');
    await show(tester, f);
    await scan(tester);
    expect(
      find.textContaining('No BLE advertisements detected'),
      findsOneWidget,
    );
    expect(find.textContaining('PASS'), findsNothing);
    expect(find.textContaining('FAIL'), findsNothing);
  });
  testWidgets('Stop ends the single active scan and returns partial snapshot', (
    tester,
  ) async {
    final f = FakeBle()..waiting = Completer<BleSnapshot>();
    await show(tester, f);
    await tester.ensureVisible(find.text('Scan BLE (8 seconds)'));
    await tester.tap(find.text('Scan BLE (8 seconds)'));
    await tester.pump();
    expect(f.scans, 1);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Scan BLE (8 seconds)'),
          )
          .onPressed,
      isNull,
    );
    await tester.ensureVisible(find.text('Stop scan'));
    await tester.tap(find.text('Stop scan'));
    await tester.pumpAndSettle();
    expect(f.stops, 1);
    expect(find.textContaining('Scan stopped.'), findsOneWidget);
    expect(find.byKey(const ValueKey('ble-progress')), findsNothing);
  });
  testWidgets(
    'unresponsive service stops at UI backstop; late result discarded',
    (tester) async {
      final f = FakeBle()..waiting = Completer<BleSnapshot>();
      await show(tester, f);
      await tester.ensureVisible(find.text('Scan BLE (8 seconds)'));
      await tester.tap(find.text('Scan BLE (8 seconds)'));
      await tester.pump();
      await tester.pump(const Duration(seconds: 13));
      await tester.pumpAndSettle();
      expect(find.textContaining('timed out'), findsOneWidget);
      expect(f.cancels, greaterThan(0));
      f.waiting!.complete(
        BleSnapshot.fromMap(state(code: 'COMPLETE', devices: true)),
      );
      await tester.pump();
      expect(find.textContaining('Service UUID:'), findsNothing);
    },
  );
  testWidgets(
    'pause cancels and resume only checks status; no background scan',
    (tester) async {
      final f = FakeBle()..waiting = Completer<BleSnapshot>();
      await show(tester, f);
      await tester.ensureVisible(find.text('Scan BLE (8 seconds)'));
      await tester.tap(find.text('Scan BLE (8 seconds)'));
      await tester.pump();
      for (final s in [
        AppLifecycleState.inactive,
        AppLifecycleState.hidden,
        AppLifecycleState.paused,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(s);
      }
      await tester.pump();
      expect(f.cancels, greaterThan(0));
      f.waiting!.complete(
        BleSnapshot.fromMap(state(code: 'COMPLETE', devices: true)),
      );
      await tester.pump();
      for (final s in [
        AppLifecycleState.hidden,
        AppLifecycleState.inactive,
        AppLifecycleState.resumed,
      ]) {
        tester.binding.handleAppLifecycleStateChanged(s);
      }
      await tester.pumpAndSettle();
      expect(f.scans, 1);
      expect(find.textContaining('Service UUID:'), findsNothing);
    },
  );
  testWidgets('repeat scan clears previous data; age timer never rescans', (
    tester,
  ) async {
    final f = FakeBle();
    await show(tester, f);
    await scan(tester);
    f.elapsed = 12000;
    await tester.pump(const Duration(seconds: 1));
    expect(find.textContaining('(old snapshot)'), findsOneWidget);
    expect(f.scans, 1);
    f.waiting = Completer<BleSnapshot>();
    await tester.ensureVisible(find.text('Scan BLE (8 seconds)'));
    await tester.tap(find.text('Scan BLE (8 seconds)'));
    await tester.pump();
    expect(find.textContaining('Service UUID:'), findsNothing);
    f.waiting!.complete(BleSnapshot.fromMap(state(code: 'COMPLETE')));
    await tester.pumpAndSettle();
    expect(f.scans, 2);
  });
  for (final size in [const Size(390, 844), const Size(1024, 600)]) {
    testWidgets('advertisement identifiers fit phone/tablet $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final f = FakeBle();
      await show(tester, f);
      await scan(tester);
      expect(tester.takeException(), isNull);
    });
  }
}
