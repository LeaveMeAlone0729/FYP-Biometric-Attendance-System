import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, [this.status = 0, this.code]);
  final String message;
  final int status;
  final String? code;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({http.Client? client, String? url})
    : _client = client ?? http.Client(),
      baseUrl = url ?? defaultUrl;
  static const defaultUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
  static ApiClient instance = ApiClient();
  static int _diagnosticSequence = 0;
  final http.Client _client;
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
  Future<dynamic> delete(String path) => _send('DELETE', path);

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final request = http.Request(method, Uri.parse('$baseUrl$path'));
    request.headers['Content-Type'] = 'application/json';
    if (_token != null) request.headers['Authorization'] = 'Bearer $_token';
    if (body != null) request.body = jsonEncode(body);
    return _perform(request);
  }

  Future<dynamic> image(
    String path,
    Uint8List bytes,
    Map<String, String> fields,
  ) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'));
    if (_token != null) request.headers['Authorization'] = 'Bearer $_token';
    request.fields.addAll(fields);
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: 'capture.jpg'),
    );
    return _perform(request);
  }

  Future<dynamic> _perform(http.BaseRequest request) async {
    final deviceBiometric = request.url.path.startsWith(
      '/api/v1/device-approvals',
    );
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
        final streamed = await _client.send(request);
        return http.Response.fromStream(streamed);
      })().timeout(const Duration(seconds: 25));
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
        if (response.statusCode == 401 && _token != null) {
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
      if (deviceBiometric) {
        throw const ApiException(
          'Device biometric request timed out. Check USB reverse and restart the scan.',
          0,
          'REQUEST_TIMEOUT',
        );
      }
      throw const ApiException(
        'The server is taking too long. Check your connection and try again.',
      );
    } on SocketException {
      if (deviceBiometric) {
        throw const ApiException(
          'Cannot reach the device verification server. Check USB reverse and API_BASE_URL.',
          0,
          'NETWORK_ERROR',
        );
      }
      throw const ApiException(
        'Cannot reach the attendance server. Check the server and your network.',
      );
    } on http.ClientException {
      if (deviceBiometric) {
        throw const ApiException(
          'Cannot reach the device verification server. Check USB reverse and API_BASE_URL.',
          0,
          'NETWORK_ERROR',
        );
      }
      throw const ApiException(
        'Cannot reach the attendance server. Check the server and your network.',
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
