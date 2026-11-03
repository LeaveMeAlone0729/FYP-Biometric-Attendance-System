import '../../../services/api_client.dart';

class DeviceApi {
  DeviceApi([ApiClient? client]) : _client = client ?? ApiClient.instance;
  final ApiClient _client;

  Future<Map<String, dynamic>> listDevices() async =>
      Map<String, dynamic>.from(await _client.get('/api/v1/devices') as Map);

  Future<Map<String, dynamic>?> current() async {
    final response = await _client.get('/api/v1/devices/current') as Map;
    final device = response['device'];
    return device == null ? null : Map<String, dynamic>.from(device as Map);
  }

  Future<Map<String, dynamic>> begin({
    required String publicKey,
    required String deviceName,
    required String deviceModel,
  }) async => Map<String, dynamic>.from(
    await _client.post('/api/v1/devices/registration-challenges', {
          'public_key_spki': publicKey,
          'platform': 'android',
          'device_name': deviceName,
          'device_model': deviceModel,
        })
        as Map,
  );

  Future<Map<String, dynamic>> confirm(
    String registrationId,
    String signature,
  ) async {
    final response =
        await _client.post('/api/v1/devices/registrations', {
              'registration_id': registrationId,
              'signature': signature,
            })
            as Map;
    return Map<String, dynamic>.from(response['device'] as Map);
  }

  Future<Map<String, dynamic>> beginPending({
    required String publicKey,
    required String deviceName,
    required String deviceModel,
  }) async => Map<String, dynamic>.from(
    await _client.post('/api/v1/devices/pending-registrations', {
          'public_key_spki': publicKey,
          'platform': 'android',
          'device_name': deviceName,
          'device_model': deviceModel,
        })
        as Map,
  );

  Future<Map<String, dynamic>> provePending(
    String id,
    String signature,
  ) async => Map<String, dynamic>.from(
    await _client.post('/api/v1/devices/pending-registrations/$id/proof', {
          'signature': signature,
        })
        as Map,
  );

  Future<Map<String, dynamic>> pendingStatus(String id) async =>
      Map<String, dynamic>.from(
        await _client.get('/api/v1/devices/pending-registrations/$id') as Map,
      );

  Future<Map<String, dynamic>?> currentPending() async {
    final response =
        await _client.get('/api/v1/devices/pending-registrations/current')
            as Map;
    final pending = response['pending'];
    return pending == null ? null : Map<String, dynamic>.from(pending as Map);
  }

  Future<void> requestDeviceApproval(String pendingId) async {
    await _client.post('/api/v1/device-approvals', {
      'pending_registration_id': pendingId,
    });
  }

  Future<Map<String, dynamic>> beginVerification(
    String operation, {
    required String publicKeyFingerprint,
  }) async => Map<String, dynamic>.from(
    await _client.post('/api/v1/devices/verification-challenges', {
          'operation': operation,
          'public_key_fingerprint': publicKeyFingerprint,
        })
        as Map,
  );

  Future<Map<String, dynamic>> confirmVerification(
    String challengeId,
    String operation,
    String signature,
  ) async => Map<String, dynamic>.from(
    await _client.post('/api/v1/devices/verifications', {
          'challenge_id': challengeId,
          'operation': operation,
          'signature': signature,
        })
        as Map,
  );

  Future<void> reportVerificationFailure(
    String? challengeId,
    String operation,
    String reasonCode,
  ) async {
    await _client.post('/api/v1/devices/verification-failures', {
      'challenge_id': challengeId,
      'operation': operation,
      'reason_code': reasonCode,
    });
  }
}
