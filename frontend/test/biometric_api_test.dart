// Module owner: Chew Zhexuan
// Module: Facial Recognition and Liveness Detection
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/modules/biometrics/services/biometric_api.dart';
import 'package:frontend/services/api_client.dart';

void main() {
  test(
    'Blink burst uses authenticated frame checks and stops at the next action',
    () async {
      final uploaded = <String>[];
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path == '/login') {
            return http.Response(
              jsonEncode({
                'access_token': 'blink-token',
                'student': {'student_id': 'TEST001'},
              }),
              200,
            );
          }
          expect(request.url.path, '/verify-face');
          expect(request.headers['Authorization'], 'Bearer blink-token');
          final body = latin1.decode(request.bodyBytes);
          expect(body, contains('name="preview_only"\r\n\r\nfalse'));
          final sample = [
            'open-sample',
            'blink-sample',
            'reopened-sample',
          ][uploaded.length];
          expect(body, contains(sample));
          uploaded.add(sample);
          return http.Response(
            jsonEncode({
              'success': true,
              'liveness_step': 'head',
              'head_action': uploaded.length < 3 ? 'blink' : 'look_straight',
            }),
            200,
          );
        }),
      );
      await client.login('TEST001', 'test-password');
      final api = BiometricApi(client);
      final result = await api.verifyBlink('challenge-id', [
        for (final text in [
          'open-sample',
          'blink-sample',
          'reopened-sample',
          'unused-sample',
        ])
          Uint8List.fromList(utf8.encode(text)),
      ]);
      expect(uploaded, hasLength(3));
      expect(result['head_action'], 'look_straight');
    },
  );

  test(
    'Biometric requests preserve bearer authentication and multipart fields',
    () async {
      final calls = <String>[];
      final transport = ApiClient(
        client: MockClient((request) async {
          final path = request.url.path;
          if (path == '/login') {
            return http.Response(
              jsonEncode({
                'access_token': 'test-token',
                'student': {'student_id': 'TEST001'},
              }),
              200,
            );
          }
          calls.add('${request.method} $path');
          expect(request.headers['Authorization'], 'Bearer test-token');
          if (path == '/register-face' ||
              path == '/verify-face' ||
              path == '/liveness/frame') {
            expect(
              request.headers['content-type'],
              startsWith('multipart/form-data; boundary='),
            );
            final body = latin1.decode(request.bodyBytes);
            expect(body, contains('name="file"; filename="capture.jpg"'));
            expect(body, contains('camera-image'));
            if (path == '/register-face') {
              expect(body, contains('name="consent"\r\n\r\ntrue'));
            } else {
              expect(body, contains('name="challenge_id"\r\n\r\nchallenge-id'));
            }
            if (path != '/liveness/frame') {
              expect(body, contains('name="auto_capture"\r\n\r\ntrue'));
              expect(body, contains('name="preview_only"\r\n\r\ntrue'));
            }
          }
          return http.Response('{"success":true}', 200);
        }),
      );
      await transport.login('TEST001', 'test-password');
      final api = BiometricApi(transport);
      final image = Uint8List.fromList(utf8.encode('camera-image'));
      await api.registerFace(image, consent: true, previewOnly: true);
      await api.verifyFace('challenge-id', image, previewOnly: true);
      await api.submitLivenessFrame('challenge-id', image);
      await api.getResult('challenge-id');
      await api.cancel('challenge-id');
      expect(calls, [
        'POST /register-face',
        'POST /verify-face',
        'POST /liveness/frame',
        'GET /verification/challenge-id',
        'POST /attendance/cancel/challenge-id',
      ]);
    },
  );
}
