import 'ble_diagnostics.dart';

typedef BeaconObservation = ({
  String uuid,
  int advertisements,
  double medianRssi,
  bool weak,
});

enum BleObservationStatus { detected, notDetected, unavailable }

class ClassroomBleObservation {
  const ClassroomBleObservation(
    this.status,
    this.reason, {
    this.durationMs = 0,
    this.beacons = const [],
  });

  final BleObservationStatus status;
  final String reason;
  final int durationMs;
  final List<BeaconObservation> beacons;

  factory ClassroomBleObservation.fromScan(
    BleSnapshot scan,
    Map<String, int> thresholds, {
    required int requestedAtMs,
    required int nowMs,
  }) {
    final duration = scan.scanDurationMs;
    if (scan.status != 'COMPLETE' || !scan.ready) {
      return ClassroomBleObservation(
        BleObservationStatus.unavailable,
        scan.status == 'COMPLETE' ? 'BLE_UNAVAILABLE' : scan.status,
        durationMs: duration,
      );
    }
    if (duration < 7000 || duration > 10000) {
      return ClassroomBleObservation(
        BleObservationStatus.unavailable,
        'BLE_SCAN_INCOMPLETE',
        durationMs: duration,
      );
    }
    final start = scan.startedAtMs, end = scan.completedAtMs;
    if (start == null ||
        end == null ||
        start < requestedAtMs ||
        end > nowMs ||
        nowMs - end > 2000 ||
        (end - start - duration).abs() > 1000) {
      return ClassroomBleObservation(
        BleObservationStatus.unavailable,
        'BLE_EVIDENCE_STALE',
        durationMs: duration,
      );
    }
    final counts = <String, int>{};
    final samples = <String, List<int>>{};
    for (final group in matchingBleSamples(scan, thresholds.keys.toSet())) {
      counts.update(
        group.uuid,
        (count) => count + group.count,
        ifAbsent: () => group.count,
      );
      (samples[group.uuid] ??= []).addAll(group.samples.values);
    }
    final observations = (samples.keys.toList()..sort()).map((uuid) {
      final median = medianBleRssi(samples[uuid]!);
      return (
        uuid: uuid,
        advertisements: counts[uuid]!,
        medianRssi: median,
        weak: median < thresholds[uuid]!,
      );
    }).toList();
    return ClassroomBleObservation(
      observations.isEmpty
          ? BleObservationStatus.notDetected
          : BleObservationStatus.detected,
      observations.isEmpty ? 'BLE_BEACON_NOT_FOUND' : 'BLE_BEACON_DETECTED',
      durationMs: duration,
      beacons: observations,
    );
  }
}

/// Only samples whose own packet carried a configured UUID qualify.
Iterable<({String uuid, int count, Map<int, int> samples})> matchingBleSamples(
  BleSnapshot scan,
  Set<String> configured,
) sync* {
  for (final ad in scan.advertisements) {
    for (final group in ad.beaconObservations) {
      final uuid = (group['service_uuid'] as String?)?.toLowerCase();
      if (uuid == null || !configured.contains(uuid)) continue;
      final rawSamples = group['samples'];
      if (rawSamples is! List || rawSamples.length > 50) {
        throw const FormatException('Invalid timestamped BLE samples.');
      }
      final samples = <int, int>{};
      for (final raw in rawSamples) {
        if (raw is! Map ||
            raw['offset_us'] is! int ||
            raw['rssi_dbm'] is! int) {
          throw const FormatException('Invalid BLE sample.');
        }
        final offset = raw['offset_us'] as int, rssi = raw['rssi_dbm'] as int;
        if (offset < 0 ||
            offset > scan.scanDurationMs * 1000 ||
            rssi < -127 ||
            rssi > 126 ||
            samples.containsKey(offset)) {
          throw const FormatException(
            'BLE sample outside scan bounds or repeated.',
          );
        }
        samples[offset] = rssi;
      }
      final count = group['advertisement_count'] ?? samples.length;
      if (count is! int || count < samples.length || count > ad.count) {
        throw const FormatException('Invalid matching advertisement count.');
      }
      if (samples.isNotEmpty) {
        yield (uuid: uuid, count: count, samples: samples);
      }
    }
  }
}
