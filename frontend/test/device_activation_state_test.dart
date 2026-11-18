import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/devices/services/device_activation_state.dart';

Map<String, dynamic> complete() => {
  'stage': 'COMPLETED_UNTRUSTED',
  'complete': true,
  'face_verified': true,
  'liveness_verified': true,
  'operation': 'enroll_second_device',
  'slot_number': 2,
  'result_classification': 'UNTRUSTED_TEST_RESULT',
  'trusted': false,
  'consumable': false,
  'activation_eligible': false,
  'activation_enabled': false,
};

void main() {
  test(
    'Completed untrusted checks never enable automatic activation or ACTIVE',
    () {
      final state = DeviceActivationState.fromBiometricResult(complete());
      expect(state.keyVerified, isTrue);
      expect(state.facePassed, isTrue);
      expect(state.livenessPassed, isTrue);
      expect(state.automaticActivationAvailable, isFalse);
      expect(state.isActive, isFalse);
      expect(state.activationStatus, 'UNAVAILABLE');
    },
  );
  test(
    'Replacement completion displays genuine checks but grants no activation',
    () {
      for (final slot in [1, 2]) {
        final state = DeviceActivationState.fromBiometricResult({
          ...complete(),
          'operation': 'replace_device',
          'slot_number': slot,
        });
        expect(state.facePassed, isTrue);
        expect(state.livenessPassed, isTrue);
        expect(state.keyVerified, isTrue);
        expect(state.isActive, isFalse);
      }
    },
  );
  test('Client trust flags or incomplete checks cannot advance readiness', () {
    for (final change in [
      {'trusted': true},
      {'activation_enabled': true},
      {'consumable': true},
      {'activation_eligible': true},
      {'stage': 'ACTIVE'},
      {'face_verified': false},
      {'liveness_verified': false},
      {'slot_number': 1},
    ]) {
      final state = DeviceActivationState.fromBiometricResult({
        ...complete(),
        ...change,
      });
      expect(state.automaticActivationAvailable, isFalse);
      expect(state.isActive, isFalse);
      expect(state.facePassed, isFalse);
    }
  });
}
