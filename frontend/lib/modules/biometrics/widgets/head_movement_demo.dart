// Module owner: Chew Zhexuan
// Module: Facial Recognition and Liveness Detection
import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Offline, mirrored examples of only the action requested by the server.
class HeadMovementDemo extends StatefulWidget {
  const HeadMovementDemo({super.key, required this.action, this.active = true});

  final String action;
  final bool active;

  @override
  State<HeadMovementDemo> createState() => _HeadMovementDemoState();
}

class _HeadMovementDemoState extends State<HeadMovementDemo>
    with SingleTickerProviderStateMixin {
  late final AnimationController _motion = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 3200),
  );
  bool _reducedMotion = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reducedMotion = MediaQuery.disableAnimationsOf(context);
    _updatePlayback();
  }

  @override
  void didUpdateWidget(HeadMovementDemo oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.action != widget.action) _motion.reset();
    _updatePlayback();
  }

  void _updatePlayback() {
    if (_reducedMotion || !widget.active) {
      _motion.stop();
    } else if (!_motion.isAnimating) {
      _motion.repeat();
    }
  }

  @override
  void dispose() {
    _motion.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final blink = widget.action == 'blink';
    final left = widget.action == 'turn_left';
    final description = blink
        ? 'Blink once normally when you see "Blink now". Do not hold your eyes shut. Keep your head facing forward.'
        : 'Turn only a little, about 20–30°. Keep your shoulders and phone still; keep both eyes visible.';
    return Semantics(
      key: const ValueKey('head-movement-demo'),
      label: blink
          ? 'Blink demonstration. $description'
          : 'Mirrored demonstration: turn slightly to your ${left ? 'left' : 'right'}. $description',
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFF2F5FA),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            ExcludeSemantics(
              child: SizedBox(
                width: 96,
                height: 112,
                child: AnimatedBuilder(
                  animation: _motion,
                  builder: (context, _) => CustomPaint(
                    key: ValueKey('head-demo-${widget.action}'),
                    painter: HeadMovementDemoPainter(
                      action: widget.action,
                      progress: _reducedMotion
                          ? (blink ? .325 : .55)
                          : _motion.value,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Watch, then copy',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 4),
                  Text(description, style: const TextStyle(fontSize: 14)),
                  const SizedBox(height: 6),
                  Text(
                    blink
                        ? 'Example: one normal blink'
                        : 'Mirror view · your ${left ? 'left' : 'right'}',
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xFF144DA1),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The shoulders stay fixed while a small face turn or blink is illustrated.
class HeadMovementDemoPainter extends CustomPainter {
  const HeadMovementDemoPainter({required this.action, required this.progress});

  final String action;
  final double progress;

  double get _pose {
    if (action == 'blink') {
      // A normal blink, rather than copying the turn's long closed-eye hold.
      if (progress < .25 || progress >= .42) return 0;
      if (progress < .30) {
        return Curves.easeInOut.transform((progress - .25) / .05);
      }
      if (progress < .35) return 1;
      return 1 - Curves.easeInOut.transform((progress - .35) / .07);
    }
    // Face forward, turn gently, hold, then return. No full-profile turn.
    if (progress < .15) return 0;
    if (progress < .4) {
      return Curves.easeInOut.transform((progress - .15) / .25);
    }
    if (progress < .65) return 1;
    if (progress < .9) {
      return 1 - Curves.easeInOut.transform((progress - .65) / .25);
    }
    return 0;
  }

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 96, size.height / 112);
    final ink = Paint()
      ..color = const Color(0xFF253858)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    final skin = Paint()..color = const Color(0xFFF2C9A8);
    final blue = Paint()..color = const Color(0xFF144DA1);
    final pose = _pose;
    final blink = action == 'blink';
    final turn = blink ? 0.0 : (action == 'turn_left' ? -1.0 : 1.0) * pose;

    // Fixed neck and shoulders make it clear that the body does not rotate.
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(41, 65, 14, 21),
        const Radius.circular(5),
      ),
      skin,
    );
    final shoulders = Path()
      ..moveTo(13, 108)
      ..quadraticBezierTo(13, 84, 35, 82)
      ..quadraticBezierTo(48, 92, 61, 82)
      ..quadraticBezierTo(83, 84, 83, 108)
      ..close();
    canvas.drawPath(shoulders, blue);

    final center = Offset(48 + turn * 2, 41);
    final halfWidth = 25 - pose * (blink ? 0 : 2);
    final face = Rect.fromCenter(
      center: center,
      width: halfWidth * 2,
      height: 64,
    );
    canvas.drawOval(face, skin);
    canvas.drawOval(face, ink);
    canvas.drawArc(
      face.deflate(1),
      math.pi * 1.06,
      math.pi * .88,
      false,
      Paint()
        ..color = const Color(0xFF253858)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6,
    );

    final features = turn * 8;
    final eyeY = 37.0;
    final leftEyeX = center.dx - 10 + features;
    final rightEyeX = center.dx + 10 + features;
    final closure = blink ? pose : 0.0;
    for (final x in [leftEyeX, rightEyeX]) {
      if (closure > .88) {
        canvas.drawLine(Offset(x - 4, eyeY), Offset(x + 4, eyeY), ink);
      } else {
        canvas.drawOval(
          Rect.fromCenter(
            center: Offset(x, eyeY),
            width: 7,
            height: 7 * (1 - closure),
          ),
          Paint()..color = const Color(0xFF253858),
        );
      }
    }
    canvas.drawPath(
      Path()
        ..moveTo(center.dx + features, 42)
        ..lineTo(center.dx + features + turn * 4, 50)
        ..lineTo(center.dx + features - 2, 51),
      ink,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(center.dx + features, 55),
        width: 13,
        height: 8,
      ),
      .2,
      math.pi - .4,
      false,
      ink,
    );

    if (!blink) {
      // Direction matches a mirrored front-camera preview: your left is screen left.
      final direction = action == 'turn_left' ? -1.0 : 1.0;
      final arrow = Path()
        ..moveTo(48 - direction * 13, 77)
        ..lineTo(48 + direction * 13, 77)
        ..moveTo(48 + direction * 7, 72)
        ..lineTo(48 + direction * 13, 77)
        ..lineTo(48 + direction * 7, 82);
      canvas.drawPath(arrow, ink..color = const Color(0xFF144DA1));
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(HeadMovementDemoPainter oldDelegate) =>
      oldDelegate.action != action || oldDelegate.progress != progress;
}
