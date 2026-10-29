import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, [this.status = 0]);
  final String message;
  final int status;
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
  final http.Client _client;
  final String baseUrl;
  final ValueNotifier<bool> authenticated = ValueNotifier(false);
  String? _token;
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
    try {
      final response = await (() async {
        final streamed = await _client.send(request);
        return http.Response.fromStream(streamed);
      })().timeout(const Duration(seconds: 25));
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
        throw ApiException(message, response.statusCode);
      }
      return data;
    } on TimeoutException {
      throw const ApiException(
        'The server is taking too long. Check your connection and try again.',
      );
    } on SocketException {
      throw const ApiException(
        'Cannot reach the attendance server. Check the server and your network.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Cannot reach the attendance server. Check the server and your network.',
      );
    }
  }
}
