import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';
import 'package:flutter/services.dart';
import 'api_routes.dart';
import 'lan_discovery.dart';

class ApiException implements Exception {
  const ApiException(this.message, [this.status = 0, this.code]);
  final String message;
  final int status;
  final String? code;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({
    http.Client? client,
    String? url,
    String? publicUrl,
    bool localMode = defaultLocalMode,
    Stream<dynamic>? networkChanges,
    SecureLanDiscovery? discovery,
    this.generalTimeout = const Duration(seconds: 10),
    this.classroomTimeout = const Duration(seconds: 10),
  }) : _injected = client,
       _localMode = localMode,
       baseUrl = url ?? defaultLanUrl,
       routes = ApiRoutes(
         lan: url ?? defaultLanUrl,
         public: publicUrl ?? (url == null ? defaultPublicUrl : ''),
         localMode: localMode,
       ) {
    lanDiscovery =
        discovery ??
        (client == null && defaultTrust.isNotEmpty
            ? SecureLanDiscovery(
                LanTrust.fromMap(
                  Map<String, dynamic>.from(
                    jsonDecode(utf8.decode(base64Decode(defaultTrust))) as Map,
                  ),
                  localMode: localMode,
                ),
              )
            : null);
    if (networkChanges != null) {
      _networkSubscription = networkChanges.listen((_) => networkChanged());
    } else if (client == null && !kIsWeb && Platform.isAndroid) {
      _networkSubscription = const EventChannel('fyp/network_changes')
          .receiveBroadcastStream()
          .listen((_) => networkChanged(), onError: (Object _) {});
    }
  }
  static const defaultLanUrl = String.fromEnvironment(
    'CLASSROOM_API_BASE_URL',
    defaultValue: defaultUrl,
  );
  static const defaultPublicUrl = String.fromEnvironment('PUBLIC_API_BASE_URL');
  static const defaultLocalMode = bool.fromEnvironment('FYP_LOCAL_MODE');
  static const defaultTrust = String.fromEnvironment('FYP_LAN_TRUST_B64');
  static const defaultUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
  static ApiClient instance = ApiClient();
  static int _diagnosticSequence = 0;
  final http.Client? _injected;
  final bool _localMode;
  late final SecureLanDiscovery? lanDiscovery;
  final ApiRoutes routes;
  final Duration generalTimeout;
  final Duration classroomTimeout;
  final Map<bool, http.Client> _transports = {};
  StreamSubscription<dynamic>? _networkSubscription;
  int _networkRevision = 0;
  int? _attendanceRevision;
  void networkChanged() {
    lanDiscovery?.invalidate();
    _networkRevision++;
    // Existing signing/scan clients abandon old work on sessionRevision change.
    // The bearer, student and authenticated state remain intact.
    _sessionRevision++;
    for (final client in _transports.values) {
      client.close();
    }
    _transports.clear();
  }

  void dispose() {
    lanDiscovery?.invalidate();
    _networkSubscription?.cancel();
    for (final client in _transports.values) {
      client.close();
    }
    _transports.clear();
  }

  http.Client transport(bool general) =>
      _injected ??
      _transports.putIfAbsent(
        general,
        () => IOClient(
          HttpClient()..connectionTimeout = Duration(seconds: general ? 5 : 3),
        ),
      );
  static const changed = ApiException(
    'Network changed during verification. Please retry.',
    0,
    'NETWORK_CHANGED',
  );
  final String baseUrl;
  final ValueNotifier<bool> authenticated = ValueNotifier(false);
  String? _token;
  int _sessionRevision = 0;
  int get sessionRevision => _sessionRevision;
  Map<String, dynamic>? student;
  Map<String, dynamic> config = {};

  Future<void> loadConfig() async {
    config = Map<String, dynamic>.from(await get('/config') as Map);
  }

  Future<void> login(String id, String password) async {
    final data =
        await post('/login', {
              'student_id': id.trim().toUpperCase(),
              'password': password,
            })
            as Map;
    _token = data['access_token'] as String;
    _sessionRevision++;
    student = Map<String, dynamic>.from(data['student'] as Map);
    authenticated.value = true;
  }

  Future<void> refreshStudent() async {
    student = Map<String, dynamic>.from(await get('/me') as Map);
  }

  Future<void> logout() async {
    // Keep the local session if revocation fails, so the student can retry signing out.
    await post('/logout', {});
    _token = null;
    _sessionRevision++;
    student = null;
    authenticated.value = false;
  }

  Future<dynamic> get(String path) => _send('GET', path);
  Future<dynamic> post(String path, Map<String, dynamic> body) =>
      _send('POST', path, body: body);
  Future<dynamic> postDiagnostic(String path, Map<String, dynamic> body) =>
      _send('POST', path, body: body, invalidateSessionOnUnauthorized: false);
  Future<dynamic> delete(String path) => _send('DELETE', path);

  bool _secureLan(String path) =>
      lanDiscovery != null && (_localMode || !ApiRoutes.general(path));

  /// Explicit user-initiated preparation, before any new candidate/key proof.
  Future<void> prepareDeviceOperation() async {
    await _requestUri('/api/v1/devices/pending-registrations', fresh: true);
  }

  Future<Uri> _requestUri(String path, {bool fresh = false}) async {
    // Preserve path validation, including when discovery overrides the origin.
    final original = routes.uri(path);
    if (!_secureLan(path)) return original;
    try {
      if (fresh || path == '/attendance/start') {
        // Fresh PIN submission is a NEW operation, not a retry/replay of old
        // signed work. Revalidate the paired server before transmitting it.
        await lanDiscovery!.refresh();
      } else {
        await lanDiscovery!.ensureReady();
      }
    } catch (error) {
      throw ApiException(
        'Paired classroom server unavailable. Connect to classroom Wi-Fi or refresh the classroom connection.',
        0,
        error is LanDiscoveryException
            ? error.code
            : 'LAN_DISCOVERY_UNAVAILABLE',
      );
    }
    return Uri.parse('${lanDiscovery!.trust.origin}$path');
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool invalidateSessionOnUnauthorized = true,
  }) async {
    if (ApiRoutes.attendanceProof(path) &&
        _attendanceRevision != null &&
        _attendanceRevision != _networkRevision) {
      throw changed;
    }
    Future<dynamic> attempt() async {
      final networkRevision = _networkRevision;
      final request = http.Request(method, await _requestUri(path));
      if (networkRevision != _networkRevision) throw changed;
      request.headers['Content-Type'] = 'application/json';
      if (_token != null) request.headers['Authorization'] = 'Bearer $_token';
      if (body != null) request.body = jsonEncode(body);
      final result = await _perform(
        request,
        invalidateSessionOnUnauthorized: invalidateSessionOnUnauthorized,
      );
      if (path == '/attendance/start') {
        _attendanceRevision = networkRevision;
      }
      return result;
    }

    try {
      return await attempt();
    } on ApiException catch (error) {
      // At most one retry, GET-only, general routes only. Never replay a proof/upload.
      if (method == 'GET' &&
          ApiRoutes.general(path) &&
          [
            'NETWORK_ERROR',
            'REQUEST_TIMEOUT',
            'NETWORK_CHANGED',
          ].contains(error.code)) {
        return attempt();
      }
      rethrow;
    }
  }

  Future<dynamic> image(
    String path,
    Uint8List bytes,
    Map<String, String> fields,
  ) async {
    if (ApiRoutes.attendanceProof(path) &&
        _attendanceRevision != null &&
        _attendanceRevision != _networkRevision) {
      throw changed;
    }
    final request = http.MultipartRequest('POST', await _requestUri(path));
    if (_token != null) request.headers['Authorization'] = 'Bearer $_token';
    request.fields.addAll(fields);
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: 'capture.jpg'),
    );
    return _perform(request);
  }

  Future<dynamic> _perform(
    http.BaseRequest request, {
    bool invalidateSessionOnUnauthorized = true,
  }) async {
    final generation = _networkRevision;
    final session = _sessionRevision;
    final general = ApiRoutes.general(request.url.path);
    final imageUpload = request is http.MultipartRequest;
    final timeout = imageUpload
        ? const Duration(seconds: 25)
        : (general ? generalTimeout : classroomTimeout);
    final deviceBiometric = request.url.path.startsWith(
      '/api/v1/device-approvals',
    );
    final deviceManagement = request.url.path.startsWith('/api/v1/devices');
    final requestId = deviceBiometric
        ? 'b3-${DateTime.now().microsecondsSinceEpoch.toRadixString(16)}-${++_diagnosticSequence}'
        : null;
    final diagnosticClock = Stopwatch()..start();
    int? diagnosticStatus;
    if (requestId != null) {
      request.headers['X-Request-ID'] = requestId;
      if (kDebugMode) {
        final safePath = request.url.path.replaceFirst(
          RegExp(r'/device-approvals/[^/]+'),
          '/device-approvals/:id',
        );
        debugPrint(
          'B3_HTTP request_id=$requestId stage=send method=${request.method} endpoint=$safePath host=${request.url.host} port=${request.url.port}',
        );
      }
    }
    try {
      final response = await (() async {
        final streamed = await (_secureLan(request.url.path)
            ? lanDiscovery!.send(request)
            : transport(general).send(request));
        return http.Response.fromStream(streamed);
      })().timeout(timeout);
      if (generation != _networkRevision) {
        throw changed;
      }
      if (session != _sessionRevision) {
        throw const ApiException(
          'Your login changed. Retry the request.',
          0,
          'SESSION_CHANGED',
        );
      }
      diagnosticStatus = response.statusCode;
      dynamic data;
      try {
        data = jsonDecode(response.body);
      } on FormatException {
        throw const ApiException(
          'The server returned an unexpected response. Try again.',
        );
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        if (invalidateSessionOnUnauthorized &&
            response.statusCode == 401 &&
            _token != null) {
          _token = null;
          _sessionRevision++;
          student = null;
          authenticated.value = false;
        }
        String message = data is Map
            ? (data['message'] ?? 'The request could not be completed.')
                  .toString()
            : 'The request could not be completed.';
        if (data is Map &&
            data['fields'] is List &&
            (data['fields'] as List).isNotEmpty) {
          final field = (data['fields'] as List).first as Map;
          message = '${field['field']}: ${field['message']}';
        }
        throw ApiException(
          message,
          response.statusCode,
          data is Map ? data['code']?.toString() : null,
        );
      }
      return data;
    } on TimeoutException {
      if (generation != _networkRevision) {
        throw changed;
      }
      if (deviceBiometric) {
        throw const ApiException(
          'Device biometric request timed out. Check USB reverse and restart the scan.',
          0,
          'REQUEST_TIMEOUT',
        );
      }
      throw ApiException(
        general
            ? 'Unable to connect to server. Please check your internet connection.'
            : deviceManagement
            ? 'Cannot reach the paired device-registration server. Check classroom Wi-Fi and refresh the paired connection.'
            : 'Cannot reach the classroom verification server. Classroom Wi-Fi is required for attendance.',
        0,
        'REQUEST_TIMEOUT',
      );
    } on SocketException {
      if (generation != _networkRevision) {
        throw changed;
      }
      if (deviceBiometric) {
        throw const ApiException(
          'Cannot reach the device verification server. Check USB reverse and API_BASE_URL.',
          0,
          'NETWORK_ERROR',
        );
      }
      throw ApiException(
        general
            ? 'Cannot reach the server. Please check your internet connection.'
            : deviceManagement
            ? 'Cannot reach the paired device-registration server. Check classroom Wi-Fi and refresh the paired connection.'
            : 'Cannot reach the classroom verification server. Classroom Wi-Fi is required for attendance.',
        0,
        'NETWORK_ERROR',
      );
    } on http.ClientException {
      if (generation != _networkRevision) {
        throw changed;
      }
      if (deviceBiometric) {
        throw const ApiException(
          'Cannot reach the device verification server. Check USB reverse and API_BASE_URL.',
          0,
          'NETWORK_ERROR',
        );
      }
      throw ApiException(
        general
            ? 'Cannot reach the server. Please check your internet connection.'
            : deviceManagement
            ? 'Cannot reach the paired device-registration server. Check classroom Wi-Fi and refresh the paired connection.'
            : 'Cannot reach the classroom verification server. Classroom Wi-Fi is required for attendance.',
        0,
        'NETWORK_ERROR',
      );
    } finally {
      if (deviceBiometric && kDebugMode) {
        debugPrint(
          'B3_HTTP request_id=$requestId stage=finished status=${diagnosticStatus ?? 'NO_RESPONSE'} elapsed_ms=${diagnosticClock.elapsedMilliseconds}',
        );
      }
    }
  }
}
