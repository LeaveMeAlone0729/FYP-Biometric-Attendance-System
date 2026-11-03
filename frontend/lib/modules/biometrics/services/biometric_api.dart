// Module owner: Chew Zhexuan
// Module: Facial Recognition and Liveness Detection
import 'dart:typed_data';

import '../../../services/api_client.dart';

/// Biometric HTTP calls; authentication and transport remain in the shared client.
class BiometricApi {
  BiometricApi([ApiClient? client]) : _client = client ?? ApiClient.instance;

  final ApiClient _client;

  Future<Map<String, dynamic>> registerFace(
    Uint8List image, {
    required bool consent,
    bool previewOnly = false,
  }) async => Map<String, dynamic>.from(
    await _client.image('/register-face', image, {
          'consent': consent.toString(),
          'auto_capture': 'true',
          'preview_only': previewOnly.toString(),
        })
        as Map,
  );

  Future<Map<String, dynamic>> verifyFace(
    String challengeId,
    Uint8List image, {
    bool previewOnly = false,
  }) async => Map<String, dynamic>.from(
    await _client.image('/verify-face', image, {
          'challenge_id': challengeId,
          'auto_capture': 'true',
          'preview_only': previewOnly.toString(),
        })
        as Map,
  );

  Future<Map<String, dynamic>> submitLivenessFrame(
    String challengeId,
    Uint8List image,
  ) async => Map<String, dynamic>.from(
    await _client.image('/liveness/frame', image, {'challenge_id': challengeId})
        as Map,
  );

  Future<Map<String, dynamic>> getResult(String challengeId) async =>
      Map<String, dynamic>.from(
        await _client.get('/verification/${Uri.encodeComponent(challengeId)}')
            as Map,
      );

  Future<void> cancel(String challengeId) async {
    await _client.post(
      '/attendance/cancel/${Uri.encodeComponent(challengeId)}',
      {},
    );
  }

  Future<void> removeRegistration() async {
    await _client.delete('/biometrics');
  }
}
