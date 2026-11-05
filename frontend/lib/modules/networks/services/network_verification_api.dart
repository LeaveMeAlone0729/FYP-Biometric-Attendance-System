import '../../../services/api_client.dart';

/// Displays a fresh server diagnostic only; never computes CIDR membership.
class NetworkVerificationApi {
  NetworkVerificationApi([ApiClient? client])
    : _client = client ?? ApiClient.instance;
  final ApiClient _client;

  Future<Map<String, dynamic>> check() async {
    final student = _client.student?['student_id'];
    final revision = _client.sessionRevision;
    void current() {
      if (!_client.authenticated.value ||
          student == null ||
          _client.student?['student_id'] != student ||
          _client.sessionRevision != revision) {
        throw const ApiException(
          'Your login changed or expired. Sign in and check the connection again.',
          401,
          'SESSION_CHANGED',
        );
      }
    }

    current();
    final raw = await _client
        .post('/api/v1/networks/verifications', {})
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => throw const ApiException(
            'Network verification timed out. Check the backend connection and try again.',
            0,
            'NETWORK_CHECK_TIMEOUT',
          ),
        );
    current();
    if (raw is! Map) {
      throw const ApiException(
        'Invalid network verification response.',
        0,
        'INVALID_NETWORK_RESULT',
      );
    }
    final data = Map<String, dynamic>.from(raw);
    final pass = data['result'] == 'PASS';
    if (data['success'] != true ||
        !['PASS', 'FAIL'].contains(data['result']) ||
        data['operation'] != 'network_diagnostic' ||
        data['attendance_authorized'] != false ||
        data['verification_id'] is! int ||
        (data['verification_id'] as int) <= 0 ||
        data['reason_code'] is! String ||
        data['message'] is! String ||
        data['verified_at'] is! String ||
        DateTime.tryParse(data['verified_at'] as String) == null ||
        (data['source_ip'] != null && data['source_ip'] is! String) ||
        (pass &&
            (data['reason_code'] != 'NETWORK_AUTHORIZED' ||
                data['source_ip'] is! String ||
                (data['source_ip'] as String).isEmpty ||
                data['matched_policy_id'] is! String ||
                (data['matched_policy_id'] as String).isEmpty)) ||
        (!pass && data['matched_policy_id'] != null)) {
      throw const ApiException(
        'The backend returned an incompatible network result. No authorization was accepted.',
        0,
        'INVALID_NETWORK_RESULT',
      );
    }
    return data;
  }
}
