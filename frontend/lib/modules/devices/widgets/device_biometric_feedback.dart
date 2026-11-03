import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Presentation only. The workflow supplies feedback from authenticated server
/// results; these widgets never perform detection, HTTP calls or authorization.
enum DeviceGuideFeedback { checking, adjust, confirmed }

class DeviceBiometricGuide extends StatelessWidget {
  const DeviceBiometricGuide({
    super.key,
    required this.feedback,
    required this.liveness,
    this.acceptedFrames = 0,
  });
  final DeviceGuideFeedback feedback;
  final bool liveness;
  final int acceptedFrames;

  Color get color => switch (feedback) {
    DeviceGuideFeedback.checking => Colors.white,
    DeviceGuideFeedback.adjust => const Color(0xFFEF5350),
    DeviceGuideFeedback.confirmed => const Color(0xFF35D596),
  };

  String get label => switch (feedback) {
    DeviceGuideFeedback.checking => 'CHECKING AUTOMATICALLY',
    DeviceGuideFeedback.adjust =>
      liveness ? 'ADJUST YOUR GESTURE' : 'ADJUST YOUR POSITION',
    DeviceGuideFeedback.confirmed =>
      liveness && acceptedFrames > 0
          ? 'GESTURE ACCEPTED · HOLD STEADY'
          : 'FACE VERIFIED · SHOW YOUR GESTURE',
  };

  @override
  Widget build(BuildContext context) => IgnorePointer(
    child: Semantics(
      label: label,
      liveRegion: true,
      child: LayoutBuilder(
        builder: (context, constraints) {
          // Keep the proven tablet guide geometry, independent of preview rotation.
          final width = math.min(
            constraints.maxWidth * .58,
            constraints.maxHeight * .62 * .78,
          );
          final height = width / .78;
          return Stack(
            fit: StackFit.expand,
            children: [
              Center(
                child: AnimatedContainer(
                  key: ValueKey(
                    liveness ? 'device-liveness-guide' : 'device-face-guide',
                  ),
                  duration: const Duration(milliseconds: 220),
                  width: liveness ? double.infinity : width,
                  height: liveness ? double.infinity : height,
                  margin: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: liveness
                        ? BorderRadius.circular(18)
                        : BorderRadius.all(
                            Radius.elliptical(width / 2, height / 2),
                          ),
                    border: Border.all(color: color, width: liveness ? 4 : 5),
                  ),
                ),
              ),
              Positioned(
                left: 16,
                right: 16,
                bottom: 18,
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 9,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black87,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      label,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: color,
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        letterSpacing: .5,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    ),
  );
}

class DeviceLivenessPanel extends StatelessWidget {
  const DeviceLivenessPanel({
    super.key,
    required this.fingers,
    required this.acceptedFrames,
    required this.requiredFrames,
  });
  final int fingers, acceptedFrames, requiredFrames;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'Show $fingers finger${fingers == 1 ? '' : 's'}',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      const Text(
        'Keep your face and one full hand visible, palm toward the camera. '
        'Neither needs to be centered. Leave space between them.',
      ),
      const SizedBox(height: 12),
      Semantics(
        liveRegion: true,
        label: '$acceptedFrames of $requiredFrames consecutive checks accepted',
        child: LinearProgressIndicator(
          key: const ValueKey('device-liveness-progress'),
          value: requiredFrames > 0
              ? (acceptedFrames / requiredFrames).clamp(0.0, 1.0)
              : 0,
          minHeight: 7,
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      const SizedBox(height: 8),
      Text(
        '$acceptedFrames/$requiredFrames consecutive checks accepted',
        key: const ValueKey('device-liveness-count'),
      ),
    ],
  );
}
