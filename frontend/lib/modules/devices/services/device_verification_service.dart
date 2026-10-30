import 'package:flutter/services.dart';
import '../../../services/api_client.dart';
import 'device_api.dart';
import 'device_key_store.dart';

class DeviceVerificationException implements Exception {
  const DeviceVerificationException(this.code, this.message);
  final String code;
  final String message;
  @override
  String toString() => message;
}

/// A displayable point-in-time result, not an attendance token or cached grant.
class DeviceVerificationResult {
  const DeviceVerificationResult({
    required this.verificationId,
    required this.challengeId,
    required this.deviceId,
    required this.operation,
    required this.verifiedAt,
  });
  final int verificationId;
  final String challengeId, deviceId, operation;
  final DateTime verifiedAt;
}

class DeviceVerificationService {
  DeviceVerificationService({
    ApiClient? client,
    DeviceApi? api,
    DeviceKeyStore? keys,
  }) : _client = client ?? ApiClient.instance,
       _api = api ?? DeviceApi(client ?? ApiClient.instance),
       _keys = keys ?? const DeviceKeyStore();
  final ApiClient _client;
  final DeviceApi _api;
  final DeviceKeyStore _keys;

  /// Each call obtains a new single-use challenge; no successful result is reused.
  /// Phase 5 must add a server-validated attendance-attempt operation/context.
  Future<DeviceVerificationResult> verify({
    String operation = 'device_status',
  }) async {
    final studentId = _client.student?['student_id'] as String?;
    final revision = _client.sessionRevision;
    bool sameSession() =>
        _client.authenticated.value &&
        revision == _client.sessionRevision &&
        _client.student?['student_id'] == studentId;
    void checkSession() {
      if (!sameSession()) {
        throw const DeviceVerificationException(
          'SESSION_CHANGED',
          'Your sign-in changed during the device check. Open My Device again.',
        );
      }
    }

    if (studentId == null || !sameSession()) {
      throw const DeviceVerificationException(
        'SIGN_IN_REQUIRED',
        'Sign in before checking this device.',
      );
    }
    String? challengeId;
    try {
      final local = await _keys.getPublicKey(studentId);
      checkSession();
      if (local == null) {
        throw const DeviceVerificationException(
          'LOCAL_KEY_MISSING',
          'The registered private key is missing from this installation. Device replacement requires approval.',
        );
      }
      final challenge = await _api.beginVerification(
        operation,
        publicKeyFingerprint: local['public_key_fingerprint'] as String,
      );
      checkSession();
      challengeId = challenge['challenge_id'] as String;
      if (challenge['operation'] != operation ||
          challenge['algorithm'] != 'ECDSA_P256_SHA256' ||
          challenge['signature_encoding'] != 'base64-DER') {
        throw const DeviceVerificationException(
          'INVALID_RESPONSE',
          'The server returned an incompatible device challenge.',
        );
      }
      if (local['public_key_fingerprint'] !=
          challenge['public_key_fingerprint']) {
        throw const DeviceVerificationException(
          'LOCAL_KEY_MISMATCH',
          'This installation does not hold the registered device key. Device replacement requires approval.',
        );
      }
      final signature = await _keys.sign(
        studentId,
        challenge['signing_payload'] as String,
      );
      checkSession();
      final response = await _api.confirmVerification(
        challengeId,
        operation,
        signature,
      );
      checkSession();
      if (response['success'] != true ||
          response['result'] != 'PASS' ||
          response['attendance_authorized'] != false ||
          response['operation'] != operation ||
          response['challenge_id'] != challengeId ||
          response['device_id'] != challenge['device_id']) {
        throw const DeviceVerificationException(
          'INVALID_RESPONSE',
          'The server did not confirm this device check.',
        );
      }
      return DeviceVerificationResult(
        verificationId: response['verification_id'] as int,
        challengeId: challengeId,
        deviceId: response['device_id'] as String,
        operation: operation,
        verifiedAt: DateTime.parse(response['verified_at'] as String),
      );
    } catch (error) {
      final failure = error is DeviceVerificationException
          ? error
          : error is PlatformException
          ? DeviceVerificationException(
              error.code == 'KEY_MISSING'
                  ? 'LOCAL_KEY_MISSING'
                  : 'KEYSTORE_UNAVAILABLE',
              error.message ??
                  'Android Keystore could not sign the device challenge.',
            )
          : error is MissingPluginException
          ? const DeviceVerificationException(
              'KEYSTORE_UNAVAILABLE',
              'Automatic device checks require the Android app and its Keystore channel.',
            )
          : error is ApiException
          ? DeviceVerificationException(
              error.code ?? 'API_FAILURE',
              error.message,
            )
          : const DeviceVerificationException(
              'INVALID_RESPONSE',
              'The device check could not be completed. Open My Device again.',
            );
      // Only report negative diagnostics, under the same login. These are untrusted
      // client reports and can never create PASS or an attendance authorization.
      if (sameSession() &&
          const {
            'LOCAL_KEY_MISSING',
            'LOCAL_KEY_MISMATCH',
            'KEYSTORE_UNAVAILABLE',
          }.contains(failure.code)) {
        try {
          await _api.reportVerificationFailure(
            challengeId,
            operation,
            failure.code,
          );
        } catch (_) {
          // Preserve the original error even when the diagnostic cannot reach the API.
        }
      }
      throw failure;
    }
  }
}
