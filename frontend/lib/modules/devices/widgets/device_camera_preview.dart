import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

/// Preserve the camera plugin's sensor/display rotation and front-camera mirror.
/// CameraPreview listens to CameraValue and selects its own aspect ratio; a
/// forced portrait box fights that transform. Only the explicitly scoped AVD
/// ImageReader workaround may add a preview-only correction.
class DeviceCameraPreview extends StatelessWidget {
  const DeviceCameraPreview({
    super.key,
    required this.controller,
    this.overlay,
    this.previewQuarterTurns = 0,
  });
  final CameraController controller;
  final Widget? overlay;
  final int previewQuarterTurns;

  @override
  Widget build(BuildContext context) => Center(
    child: ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.55,
      ),
      child: previewQuarterTurns == 0
          ? CameraPreview(controller, child: overlay)
          : RotatedBox(
              quarterTurns: previewQuarterTurns,
              child: CameraPreview(controller, child: overlay),
            ),
    ),
  );
}
