import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

/// Discovery hints never authenticate a server. TLS and the installed environment
/// binding must both pass before ApiClient may attach a bearer or upload a face.
class LanDiscoveryException implements Exception {
  const LanDiscoveryException(this.code);
  final String code;
  @override
  String toString() => code;
}

class LanTrust {
  LanTrust.fromMap(Map<String, dynamic> data, {required bool localMode})
    : mode = data['mode'] as String,
      serverId = data['server_id'] as String,
      hostname = data['hostname'] as String,
      databaseIdentity = data['database_identity'] as String,
      caPem = data['ca_pem'] as String {
    if (data['version'] != 1 ||
        data['port'] != 8005 ||
        mode != (localMode ? 'Local' : 'Full') ||
        !RegExp(r'^[0-9a-f]{32}$').hasMatch(serverId) ||
        hostname != 'fyp-$serverId.local' ||
        !RegExp(r'^[0-9a-f]{64}$').hasMatch(databaseIdentity)) {
      throw const LanDiscoveryException('LAN_TRUST_BINDING_INVALID');
    }
    context = SecurityContext(withTrustedRoots: false)
      ..setTrustedCertificatesBytes(utf8.encode(caPem));
  }
  final String mode, serverId, hostname, databaseIdentity, caPem;
  late final SecurityContext context;
  String get origin => 'https://$hostname:8005';
  bool matches(Map data) =>
      data['version'] == 1 &&
      data['mode'] == mode &&
      data['server_id'] == serverId &&
      data['database_identity'] == databaseIdentity;
}

bool privateLanAddress(String value) {
  final parts = value.split('.').map(int.tryParse).toList();
  return parts.length == 4 &&
      parts.every((p) => p != null && p >= 0 && p <= 255) &&
      parts.join('.') == value &&
      (parts[0] == 10 ||
          (parts[0] == 172 && parts[1]! >= 16 && parts[1]! <= 31) ||
          (parts[0] == 192 && parts[1] == 168));
}

bool currentWifiSubnet(String address, Object? subnets) {
  if (!privateLanAddress(address) || subnets is! List) return false;
  int number(String ip) =>
      ip.split('.').fold(0, (n, p) => (n << 8) | int.parse(p));
  for (final row in subnets.take(8)) {
    if (row is! Map ||
        row['address'] is! String ||
        !privateLanAddress(row['address']) ||
        row['prefix'] is! int ||
        row['prefix'] < 1 ||
        row['prefix'] > 32) {
      continue;
    }
    final mask = (0xffffffff << (32 - (row['prefix'] as int))) & 0xffffffff;
    if ((number(address) & mask) == (number(row['address'] as String) & mask)) {
      return true;
    }
  }
  return false;
}

typedef DiscoverLan = Future<Map<dynamic, dynamic>> Function();
typedef LanTransport = http.Client Function(String address);

class SecureLanDiscovery {
  SecureLanDiscovery(
    this.trust, {
    DiscoverLan? discover,
    LanTransport? transport,
    Future<ConnectionTask<Socket>> Function(String, int)? connect,
    this.discoveryTimeout = const Duration(seconds: 7),
  }) : _discover =
           discover ??
           (() async =>
               await channel.invokeMapMethod<dynamic, dynamic>('discover') ??
               {}),
       _transport = transport,
       _connect = connect ?? Socket.startConnect;
  static const channel = MethodChannel('fyp/lan_discovery');
  final LanTrust trust;
  final Duration discoveryTimeout;
  final DiscoverLan _discover;
  final LanTransport? _transport;
  final Future<ConnectionTask<Socket>> Function(String, int) _connect;
  http.Client? _client;
  Future<void>? _pending;
  int _revision = 0;
  String? address;
  String? _manual;
  String? lastError;

  void invalidate({bool preserveManual = false}) {
    _revision++;
    _client?.close();
    _client = null;
    address = null;
    // Callers may retain an address hint, never an authenticated transport.
    if (!preserveManual) _manual = null;
    _pending = null;
  }

  /// A new user-initiated PIN attempt revalidates TLS at fresh discovery hints.
  /// Keep an explicit manual hint, but recheck its subnet and pinned identity.
  Future<void> refresh() {
    invalidate(preserveManual: true);
    return ensureReady();
  }

  void manualAddress(String value) {
    if (!privateLanAddress(value)) {
      throw const LanDiscoveryException('LAN_CANDIDATE_INVALID');
    }
    invalidate();
    _manual = value;
  }

  http.Client createTransport(String ip) {
    if (!privateLanAddress(ip)) {
      throw const LanDiscoveryException('LAN_CANDIDATE_INVALID');
    }
    if (_transport != null) return _transport(ip);
    final client = HttpClient(context: trust.context)
      ..connectionTimeout = const Duration(seconds: 2)
      ..findProxy = (_) => 'DIRECT';
    client.connectionFactory = (uri, proxyHost, proxyPort) async {
      if (uri.scheme != 'https' ||
          uri.host != trust.hostname ||
          uri.port != 8005 ||
          proxyHost != null) {
        throw const LanDiscoveryException('LAN_TRANSPORT_ORIGIN_REJECTED');
      }
      // A custom connectionFactory owns TLS itself. Preserve logical-hostname
      // verification while connecting only to the resolved literal Wi-Fi IP.
      final raw = await _connect(ip, 8005);
      Socket? active;
      var cancelled = false;
      final secured = () async {
        active = await raw.socket;
        if (cancelled) {
          active!.destroy();
          throw const LanDiscoveryException('NETWORK_CHANGED');
        }
        active = await SecureSocket.secure(
          active!,
          host: trust.hostname,
          context: trust.context,
        );
        if (cancelled) {
          active!.destroy();
          throw const LanDiscoveryException('NETWORK_CHANGED');
        }
        return active!;
      }();
      return ConnectionTask.fromSocket(secured, () {
        cancelled = true;
        raw.cancel();
        active?.destroy();
      });
    };
    return IOClient(client);
  }

  Future<void> ensureReady() async {
    if (_client != null) return;
    if (_pending != null) return _pending;
    final revision = _revision;
    final pending = _resolve(revision);
    _pending = pending;
    try {
      await pending;
    } finally {
      if (revision == _revision) _pending = null;
    }
  }

  Future<void> _resolve(int revision) async {
    final accepted = <String, http.Client>{};
    try {
      final scan = await _discover().timeout(discoveryTimeout);
      if (scan['wifi'] != true) {
        throw const LanDiscoveryException('CLASSROOM_WIFI_REQUIRED');
      }
      final candidates = <String>{?_manual};
      final rows = scan['candidates'];
      if (rows is List) {
        for (final row in rows.take(16)) {
          if (row is Map &&
              row['port'] == 8005 &&
              row['address'] is String &&
              privateLanAddress(row['address'])) {
            candidates.add(row['address'] as String);
          }
        }
      }
      // Parallel, bounded TLS probes; no account data, cookies, bearer or PIN.
      await Future.wait(
        candidates
            .where((ip) => currentWifiSubnet(ip, scan['subnets']))
            .take(8)
            .map((ip) async {
              final client = createTransport(ip);
              var keep = false;
              try {
                final valid = await (() async {
                  final request = http.Request(
                    'GET',
                    Uri.parse('${trust.origin}/classroom-discovery/identity'),
                  )..followRedirects = false;
                  final response = await client.send(request);
                  if (response.statusCode != 200) return false;
                  final bytes = <int>[];
                  await for (final chunk in response.stream.timeout(
                    const Duration(seconds: 2),
                  )) {
                    bytes.addAll(chunk);
                    if (bytes.length > 2048) return false;
                  }
                  final data = jsonDecode(utf8.decode(bytes));
                  return data is Map && trust.matches(data);
                })().timeout(const Duration(seconds: 3));
                if (valid && revision == _revision) {
                  accepted[ip] = client;
                  keep = true;
                }
              } catch (_) {
                // No TLS details, credentials, packet contents or certificates logged.
              } finally {
                if (!keep) client.close();
              }
            }),
      );
      if (revision != _revision) {
        throw const LanDiscoveryException('NETWORK_CHANGED');
      }
      if (accepted.length != 1) {
        throw LanDiscoveryException(
          accepted.isEmpty
              ? 'PAIRED_CLASSROOM_SERVER_NOT_FOUND'
              : 'MULTIPLE_PAIRED_SERVERS',
        );
      }
      address = accepted.keys.single;
      _client = accepted.remove(address);
      lastError = null;
    } catch (error) {
      lastError = error is LanDiscoveryException
          ? error.code
          : 'LAN_DISCOVERY_UNAVAILABLE';
      rethrow;
    } finally {
      for (final client in accepted.values) {
        client.close();
      }
    }
  }

  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    // No implicit rediscovery/replay once a signed operation has been prepared.
    if (_client == null) throw const LanDiscoveryException('NETWORK_CHANGED');
    if (request.url.origin != trust.origin) {
      throw const LanDiscoveryException('LAN_TRANSPORT_ORIGIN_REJECTED');
    }
    request.followRedirects = false;
    final client = _client!;
    final revision = _revision;
    try {
      return await client.send(request);
    } catch (_) {
      // A cancelled/failed old request must not tear down a newer verified
      // connection established for a subsequent user-initiated attempt.
      if (revision == _revision && identical(client, _client)) {
        invalidate(preserveManual: true);
      }
      rethrow;
    }
  }
}
