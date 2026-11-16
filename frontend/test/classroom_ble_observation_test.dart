import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/networks/services/ble_diagnostics.dart';
import 'package:frontend/modules/networks/services/classroom_ble_observation.dart';

const configured = '7d9a6c10-326a-4c60-9e01-1ef000000001';
const other = '7d9a6c10-326a-4c60-9e01-1ef000000002';
const started = 1700000000000;
const completed = started + 8000;

Map<String, dynamic> advertiser(
  int id,
  String uuid,
  List<int> rssis, {
  int? count,
}) => {
  'scan_id': id,
  'service_uuids': [uuid],
  'service_data': [],
  'manufacturer_data': [],
  'rssi_dbm': rssis.last,
  'rssi_samples': rssis,
  'advertisement_count': count ?? rssis.length,
  'last_seen_age_ms': 100,
  'last_seen_at_ms': completed - 100,
  'beacon_observations': [
    {
      'service_uuid': uuid,
      'advertisement_count': count ?? rssis.length,
      'samples': [
        for (var i = 0; i < rssis.length; i++)
          {'offset_us': i * 1000000 + 100000, 'rssi_dbm': rssis[i]},
      ],
    },
  ],
};

BleSnapshot scan({
  String status = 'COMPLETE',
  List<Map<String, dynamic>> devices = const [],
  int duration = 8000,
}) => BleSnapshot.fromMap({
  'status': status,
  'supported': status != 'BLE_UNSUPPORTED',
  'bluetooth_enabled': status != 'BLUETOOTH_OFF',
  'scan_permission': status == 'BLE_PERMISSION_REQUIRED' ? 'DENIED' : 'GRANTED',
  'connect_permission': 'GRANTED',
  'location_permission': 'PRECISE_GRANTED',
  'location_enabled': true,
  'scan_started_at_ms': started,
  'completed_at_ms': completed,
  'scan_duration_ms': duration,
  'devices': devices,
});

ClassroomBleObservation observe(
  BleSnapshot scan, {
  int requestedAt = started,
  int now = completed,
}) => ClassroomBleObservation.fromScan(
  scan,
  const {configured: -65},
  requestedAtMs: requestedAt,
  nowMs: now,
);

void main() {
  test('matches exact UUID across advertisers, counts and computes median', () {
    final observed = observe(
      scan(
        devices: [
          advertiser(1, configured.toUpperCase(), [-62, -52], count: 51),
          advertiser(2, other, [-12, -12, -12]),
          advertiser(3, configured, [-50, -40]),
        ],
      ),
    );
    expect(observed.status, BleObservationStatus.detected);
    expect(observed.durationMs, 8000);
    expect(observed.beacons.single, (
      uuid: configured,
      advertisements: 53,
      medianRssi: -51.0,
      weak: false,
    ));
  });

  test('incorrect UUID and empty completed scan both mean not detected', () {
    for (final sample in [
      scan(),
      scan(
        devices: [
          advertiser(1, other, [-40]),
        ],
      ),
    ]) {
      final observed = observe(sample);
      expect(observed.status, BleObservationStatus.notDetected);
      expect(observed.beacons, isEmpty);
      expect(observed.durationMs, 8000);
    }
  });

  test('weak beacon remains detected', () {
    final observed = observe(
      scan(
        devices: [
          advertiser(1, configured, [-88]),
        ],
      ),
    );
    expect(observed.status, BleObservationStatus.detected);
    expect(observed.beacons.single.weak, isTrue);
    expect(observed.beacons.single.medianRssi, -88);
  });

  test('cached, delayed or future scans cannot report detection', () {
    final found = scan(
      devices: [
        advertiser(1, configured, [-50]),
      ],
    );
    for (final observed in [
      observe(found, requestedAt: started + 1),
      observe(found, now: completed + 2001),
      observe(found, now: completed - 1),
    ]) {
      expect(observed.status, BleObservationStatus.unavailable);
      expect(observed.reason, 'BLE_EVIDENCE_STALE');
      expect(observed.beacons, isEmpty);
    }
  });

  test(
    'radio, permissions, scanner errors and incomplete scans are unavailable',
    () {
      for (final status in [
        'BLUETOOTH_OFF',
        'BLE_PERMISSION_REQUIRED',
        'BLE_UNSUPPORTED',
        'BLE_SCAN_FAILED',
        'BLE_UNAVAILABLE',
        'CANCELLED',
      ]) {
        final observed = observe(scan(status: status, duration: 0));
        expect(observed.status, BleObservationStatus.unavailable);
        expect(observed.reason, status);
      }
      expect(observe(scan(duration: 3000)).reason, 'BLE_SCAN_INCOMPLETE');
    },
  );
}
