import 'package:flutter/material.dart';
import '../services/device_activation_state.dart';

/// Displayed only after the device API confirms COMPLETED_UNTRUSTED.
/// Key proof is a prerequisite validated by the server for that bound session.
class DeviceBiometricCompletion extends StatelessWidget {
  const DeviceBiometricCompletion({
    super.key,
    required this.onBack,
    this.activationStatus,
    this.trustedApprovalStatus,
    this.activationBusy = false,
    this.activationError,
    this.replacement = false,
    this.activationState = const DeviceActivationState.unavailable(
      keyVerified: true,
      facePassed: true,
      livenessPassed: true,
    ),
  });
  final VoidCallback onBack;
  final String? activationStatus, trustedApprovalStatus, activationError;
  final bool activationBusy, replacement;
  final DeviceActivationState activationState;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Device biometric result')),
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(
                  Icons.check_circle_outline,
                  color: Color(0xFF35D596),
                  size: 64,
                ),
                const SizedBox(height: 16),
                Text(
                  'Biometric checks completed — awaiting trusted biometric approval',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 20),
                Text(
                  'Face recognition: ${activationState.facePassed ? 'PASS' : 'NOT CONFIRMED'}',
                ),
                const SizedBox(height: 10),
                Text(
                  'Liveness detection: ${activationState.livenessPassed ? 'PASS' : 'NOT CONFIRMED'}',
                ),
                const SizedBox(height: 10),
                Text(
                  'Device key verification: ${activationState.keyVerified ? 'PASS' : 'NOT CONFIRMED'}',
                ),
                const SizedBox(height: 10),
                const Text('Registration status: NOT ACTIVE'),
                const SizedBox(height: 10),
                Text(
                  'Trusted biometric approval: ${trustedApprovalStatus ?? activationState.trustedApprovalStatus}',
                ),
                const SizedBox(height: 10),
                Text(
                  'Device activation: ${activationStatus ?? activationState.activationStatus}',
                ),
                if (activationBusy)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Checking secure activation readiness...',
                          ),
                        ),
                      ],
                    ),
                  ),
                if (activationError != null)
                  Text(
                    activationError!,
                    key: const ValueKey('activation-error'),
                  ),
                const SizedBox(height: 20),
                Text(
                  replacement
                      ? 'Your face, live gesture and candidate device key checks succeeded. The result is COMPLETED_UNTRUSTED. The old device remains ACTIVE until genuine trusted replacement approval and fresh key proof succeed. The other slot is unchanged.'
                      : 'Your face, live gesture and candidate device key checks succeeded. '
                            'The result is COMPLETED_UNTRUSTED. Slot 2 remains inactive until '
                            'the backend confirms a genuine trusted approval and fresh activation-key proof. '
                            'The biometric test result alone does not authorize registration.',
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: onBack,
                  child: const Text('Back to My Device'),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
