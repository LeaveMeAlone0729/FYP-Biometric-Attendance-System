import 'dart:typed_data';
import '../../../services/api_client.dart';
import '../../biometrics/services/biometric_api.dart';
import 'attendance_device_authorization.dart';

/// Reuses the partner's camera/API; adds device proof only to attendance frames.
class AuthorizedAttendanceBiometricApi extends BiometricApi {
  AuthorizedAttendanceBiometricApi({
    ApiClient? client,
    AttendanceDeviceAuthorization? devices,
  }) : _client = client ?? ApiClient.instance,
       _devices = devices ?? AttendanceDeviceAuthorization(client: client),
       super(client);
  final ApiClient _client;
  final AttendanceDeviceAuthorization _devices;
  @override
  Future<Map<String, dynamic>> submitLivenessFrame(
    String challengeId,
    Uint8List image,
  ) async {
    final revision = _client.sessionRevision;
    final proof = await _devices.proof(challengeId);
    if (revision != _client.sessionRevision || !_client.authenticated.value) {
      throw const ApiException(
        'Your login changed. Start attendance again.',
        401,
        'ATTENDANCE_SESSION_CHANGED',
      );
    }
    final result = Map<String, dynamic>.from(
      await _client.image('/liveness/frame', image, {
            'challenge_id': challengeId,
            ...proof,
          })
          as Map,
    );
    if (result['complete'] == true) {
      _devices.completed(challengeId);
    }
    return result;
  }
}
