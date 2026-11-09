import 'package:flutter/services.dart';

/// Android observations only. No API client, storage or authorization result.
class WifiReading {
  WifiReading.fromMap(Map<dynamic, dynamic> data)
    : status = data['status'] as String? ?? 'INFO_UNAVAILABLE',
      connectionType = data['connection_type'] as String? ?? 'UNKNOWN',
      permission = data['permission_status'] as String? ?? 'UNKNOWN',
      wifiEnabled = data['wifi_enabled'] as bool?,
      wifiConnected = data['wifi_connected'] as bool?,
      locationEnabled = data['location_enabled'] as bool?,
      ssid = _ssid(data['ssid']),
      bssid = _bssid(data['bssid']),
      rssi = _rssi(data['rssi_dbm']),
      observedAt = data['observed_at_ms'] is int
          ? DateTime.fromMillisecondsSinceEpoch(data['observed_at_ms'] as int)
          : null;

  final String status, connectionType, permission;
  final bool? wifiEnabled, wifiConnected, locationEnabled;
  final String? ssid, bssid;
  final int? rssi;
  final DateTime? observedAt;

  /// Signed only for an explicit classroom check; Phase 1 remains local-only.
  Map<String, dynamic> toEvidenceMap() => {
    'status': status,
    'connection_type': connectionType,
    'permission_status': permission,
    'wifi_enabled': wifiEnabled,
    'wifi_connected': wifiConnected,
    'location_enabled': locationEnabled,
    'ssid': ssid,
    'bssid': bssid,
    'rssi_dbm': rssi,
    'observed_at_ms': observedAt?.millisecondsSinceEpoch,
  };

  static String? _ssid(dynamic value) {
    if (value is! String) return null;
    if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
      value = value.substring(1, value.length - 1);
    }
    return value.trim().isEmpty || value.toLowerCase() == '<unknown ssid>'
        ? null
        : value;
  }

  static String? _bssid(dynamic value) {
    if (value is! String ||
        !RegExp(
          r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$',
          caseSensitive: false,
        ).hasMatch(value) ||
        {
          '02:00:00:00:00:00',
          '00:00:00:00:00:00',
          'ff:ff:ff:ff:ff:ff',
        }.contains(value.toLowerCase())) {
      return null;
    }
    return value.toLowerCase();
  }

  static int? _rssi(dynamic value) =>
      value is int && value >= -126 && value < 0 ? value : null;
}

class WifiDiagnostics {
  const WifiDiagnostics([
    this.channel = const MethodChannel('attendance/wifi_diagnostics'),
  ]);
  final MethodChannel channel;

  Future<WifiReading> read() async {
    final data = await channel
        .invokeMapMethod<dynamic, dynamic>('read')
        .timeout(const Duration(seconds: 5));
    if (data == null) throw const FormatException('Wi-Fi reading unavailable.');
    return WifiReading.fromMap(data);
  }

  Future<void> requestPermission() =>
      channel.invokeMethod<void>('requestPermission');

  Future<void> openSettings(String page) => channel
      .invokeMethod<void>('openSettings', {'page': page})
      .timeout(const Duration(seconds: 5));
}
