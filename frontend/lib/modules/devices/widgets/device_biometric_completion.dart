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
    this.supervisedScanReference,
    this.localDemo = false,
    this.replacement = false,
    this.activationState = const DeviceActivationState.unavailable(
      keyVerified: true,
      facePassed: true,
      livenessPassed: true,
    ),
  });
  final VoidCallback onBack;
  final String? activationStatus, trustedApprovalStatus, activationError;
  final String? supervisedScanReference;
  final bool activationBusy, replacement, localDemo;
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
                  'Face verification complete',
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
                if (supervisedScanReference case final reference?) ...[
                  const SizedBox(height: 16),
                  Text(
                    localDemo
                        ? 'Give the scan reference to the local FYP operator for demo verification.'
                        : 'An authorized institution verifier must check your identity and witness a fresh Slot 2 scan. Give the verifier the reference from that supervised scan.',
                  ),
                  SelectableText('Scan reference: $reference'),
                  Text(
                    localDemo
                        ? 'After the operator records the demo evidence, cancel this pending request and run a fresh Slot 2 scan.'
                        : 'After the verifier records the signed evidence, cancel the pending request and start Slot 2 registration again.',
                  ),
                ],
                const SizedBox(height: 20),
                Text(
                  replacement
                      ? 'Your old device remains ACTIVE until replacement is approved. Your other device is unchanged.'
                      : 'Slot 2 remains inactive until the server approves registration.',
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
