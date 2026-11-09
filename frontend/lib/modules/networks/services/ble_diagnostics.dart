import 'dart:async';
import 'package:flutter/services.dart';
import 'wifi_diagnostics.dart';

/// Ephemeral local scan data only. No MAC addresses, backend client or storage.
class BleAdvertisement {
  BleAdvertisement.fromMap(Map data, {int Function()? elapsedMilliseconds})
    : id = data['scan_id'] as int,
      name = data['name'] as String?,
      serviceUuids = List<String>.from(data['service_uuids'] as List),
      serviceData = (data['service_data'] as List)
          .map((v) => Map<String, dynamic>.from(v as Map))
          .toList(),
      manufacturerData = (data['manufacturer_data'] as List)
          .map((v) => Map<String, dynamic>.from(v as Map))
          .toList(),
      rssi = data['rssi_dbm'] as int,
      samples = List<int>.from(data['rssi_samples'] as List),
      beaconObservations = (data['beacon_observations'] as List? ?? [])
          .map((v) => Map<String, dynamic>.from(v as Map))
          .toList(),
      count = data['advertisement_count'] as int,
      initialAgeMs = data['last_seen_age_ms'] as int,
      timestamp = DateTime.fromMillisecondsSinceEpoch(
        data['last_seen_at_ms'] as int,
        isUtc: true,
      ),
      _elapsed = elapsedMilliseconds {
    if (id <= 0 ||
        initialAgeMs < 0 ||
        count <= 0 ||
        samples.isEmpty ||
        samples.length > 50 ||
        samples.any((v) => v < -127 || v > 126) ||
        rssi < -127 ||
        rssi > 126 ||
        timestamp.millisecondsSinceEpoch <= 0 ||
        serviceUuids.length > 8 ||
        serviceData.length > 4 ||
        manufacturerData.length > 4) {
      throw const FormatException('Invalid BLE advertisement.');
    }
    _clock.start();
  }
  final int id, rssi, count, initialAgeMs;
  final String? name;
  final List<String> serviceUuids;
  final List<Map<String, dynamic>> serviceData, manufacturerData;
  final List<int> samples;
  final List<Map<String, dynamic>> beaconObservations;
  final DateTime timestamp;
  final int Function()? _elapsed;
  final _clock = Stopwatch();
  double get ageSeconds =>
      (initialAgeMs +
          (_elapsed?.call() ?? _clock.elapsedMilliseconds).clamp(0, 1 << 62)) /
      1000.0;
  double get medianRssi {
    final values = [...samples]..sort();
    final mid = values.length ~/ 2;
    return values.length.isOdd
        ? values[mid].toDouble()
        : (values[mid - 1] + values[mid]) / 2.0;
  }
}

class BleSnapshot {
  BleSnapshot.fromMap(Map data, {int Function()? elapsedMilliseconds})
    : status = data['status'] as String? ?? 'BLE_UNAVAILABLE',
      supported = data['supported'] as bool? ?? false,
      bluetoothEnabled = data['bluetooth_enabled'] as bool?,
      scanPermission = data['scan_permission'] as String? ?? 'UNKNOWN',
      connectPermission = data['connect_permission'] as String? ?? 'UNKNOWN',
      locationPermission = data['location_permission'] as String? ?? 'UNKNOWN',
      locationEnabled = data['location_enabled'] as bool?,
      scanDurationMs = data['scan_duration_ms'] as int? ?? 0,
      errorCode = data['scan_error_code'] as int?,
      startedAtMs = data['scan_started_at_ms'] as int?,
      completedAtMs = data['completed_at_ms'] as int?,
      advertisements = (data['devices'] as List? ?? [])
          .map(
            (r) => BleAdvertisement.fromMap(
              r as Map,
              elapsedMilliseconds: elapsedMilliseconds,
            ),
          )
          .toList() {
    if (scanDurationMs < 0 ||
        advertisements.length > 40 ||
        (!['COMPLETE', 'STOPPED'].contains(status) &&
            advertisements.isNotEmpty)) {
      throw const FormatException('Invalid BLE snapshot.');
    }
  }
  final String status, scanPermission, connectPermission, locationPermission;
  final bool supported;
  final bool? bluetoothEnabled, locationEnabled;
  final int scanDurationMs;
  final int? errorCode;
  final int? startedAtMs, completedAtMs;
  final List<BleAdvertisement> advertisements;
  bool get ready =>
      supported &&
      bluetoothEnabled == true &&
      ['GRANTED', 'LEGACY_LOCATION_REQUIRED'].contains(scanPermission) &&
      connectPermission == 'GRANTED' &&
      locationPermission == 'PRECISE_GRANTED' &&
      locationEnabled == true;
}

class BleDiagnostics {
  const BleDiagnostics({
    this.channel = const MethodChannel('attendance/ble_diagnostics'),
    this.location = const WifiDiagnostics(),
  });
  final MethodChannel channel;
  final WifiDiagnostics location;
  Future<BleSnapshot> status() async {
    final value = await channel
        .invokeMapMethod<dynamic, dynamic>('status')
        .timeout(const Duration(seconds: 3));
    if (value == null) {
      throw const FormatException('Bluetooth status unavailable.');
    }
    return BleSnapshot.fromMap(value);
  }

  Future<BleSnapshot> scan({String? requestId}) async {
    try {
      final value = await channel
          .invokeMapMethod<dynamic, dynamic>('scan', {'request_id': requestId})
          .timeout(const Duration(seconds: 10));
      if (value == null) throw const FormatException('BLE scan unavailable.');
      return BleSnapshot.fromMap(value);
    } on TimeoutException {
      unawaited(cancel(requestId: requestId));
      rethrow;
    }
  }

  Future<void> _dispatch(String method, {String? requestId}) async {
    // Never leave a cleanup timeout timer after widget disposal. Native owns an
    // independent eight-second deadline even if Dart/this future disappears.
    unawaited(
      channel
          .invokeMethod<void>(method, {'request_id': requestId})
          .catchError((Object _) {}),
    );
  }

  Future<void> stop({String? requestId}) =>
      _dispatch('stop', requestId: requestId);
  Future<void> cancel({String? requestId}) =>
      _dispatch('cancel', requestId: requestId);
  Future<void> requestPermission() async {
    await channel
        .invokeMethod<void>('requestPermission')
        .timeout(const Duration(seconds: 60));
    final state = await status();
    if (state.supported &&
        [
          'GRANTED',
          'LEGACY_LOCATION_REQUIRED',
        ].contains(state.scanPermission) &&
        state.connectPermission == 'GRANTED' &&
        state.locationPermission != 'PRECISE_GRANTED') {
      await location.requestPermission().timeout(const Duration(seconds: 60));
    }
  }

  Future<void> enableBluetooth() => channel
      .invokeMethod<void>('enableBluetooth')
      .timeout(const Duration(seconds: 60));
  Future<void> openSettings(String page) => location.openSettings(page);
}
