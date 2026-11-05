import 'dart:async';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../../../services/api_client.dart';

/// Presentation only. A transport failure is not a backend CIDR decision.
class NetworkVerificationFailure {
  const NetworkVerificationFailure(this.code, this.message, this.unreachable);
  final String code, message;
  final bool unreachable;
  static const unreachableMessage =
      'Unable to reach the verification server. Connect to the authorised network and try again.';

  factory NetworkVerificationFailure.from(Object error) {
    final transport =
        error is TimeoutException ||
        error is SocketException ||
        error is http.ClientException ||
        (error is ApiException &&
            error.status == 0 &&
            const {
              'REQUEST_TIMEOUT',
              'NETWORK_ERROR',
              'NETWORK_CHECK_TIMEOUT',
              'ATTENDANCE_DEVICE_TIMEOUT',
            }.contains(error.code));
    if (transport) {
      return const NetworkVerificationFailure(
        'VERIFICATION_SERVER_UNREACHABLE',
        unreachableMessage,
        true,
      );
    }
    return NetworkVerificationFailure(
      error is ApiException
          ? error.code ?? 'VERIFICATION_UNAVAILABLE'
          : 'VERIFICATION_UNAVAILABLE',
      error is ApiException
          ? error.message
          : 'Verification could not be completed. Try again.',
      false,
    );
  }

  String get attendanceMessage => unreachable
      ? 'Network verification: FAIL\n$message\nThe backend could not verify this connection. Attendance is blocked.'
      : message;
}
