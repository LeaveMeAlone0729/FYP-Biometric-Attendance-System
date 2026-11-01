/// UI readiness only; no activation HTTP calls or client-controlled authorization.
/// This model displays untrusted evidence only. DeviceActivationService handles
/// the implemented server-confirmed ACTIVE path separately.
class DeviceActivationState {
  const DeviceActivationState.unavailable({
    this.keyVerified = false,
    this.facePassed = false,
    this.livenessPassed = false,
  });
  final bool keyVerified, facePassed, livenessPassed;

  factory DeviceActivationState.fromBiometricResult(
    Map<String, dynamic> result,
  ) {
    final completed =
        result['stage'] == 'COMPLETED_UNTRUSTED' &&
        result['complete'] == true &&
        result['face_verified'] == true &&
        result['liveness_verified'] == true &&
        ((result['operation'] == 'enroll_second_device' &&
                result['slot_number'] == 2) ||
            (result['operation'] == 'replace_device' &&
                [1, 2].contains(result['slot_number']))) &&
        result['result_classification'] == 'UNTRUSTED_TEST_RESULT' &&
        result['trusted'] == false &&
        result['consumable'] == false &&
        result['activation_eligible'] == false &&
        result['activation_enabled'] == false;
    if (!completed) return const DeviceActivationState.unavailable();
    // The authenticated B3 service requires KEY_PROVEN for this exact binding.
    return const DeviceActivationState.unavailable(
      keyVerified: true,
      facePassed: true,
      livenessPassed: true,
    );
  }

  bool get automaticActivationAvailable => false;
  bool get isActive => false;
  String get trustedApprovalStatus => 'NOT YET AVAILABLE';
  String get activationStatus => 'UNAVAILABLE';
}
