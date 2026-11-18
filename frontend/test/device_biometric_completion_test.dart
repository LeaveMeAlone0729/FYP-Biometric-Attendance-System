import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/modules/devices/widgets/device_biometric_completion.dart';

void main() {
  for (final size in [
    const Size(360, 640),
    const Size(844, 390),
    const Size(777, 1164),
    const Size(1164, 777),
  ]) {
    testWidgets('Clean completion scrolls safely at $size', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var returned = 0;
      await tester.pumpWidget(
        MaterialApp(home: DeviceBiometricCompletion(onBack: () => returned++)),
      );
      for (final status in [
        'Face recognition: PASS',
        'Liveness detection: PASS',
        'Device key verification: PASS',
        'Registration status: NOT ACTIVE',
        'Trusted biometric approval: NOT YET AVAILABLE',
        'Device activation: UNAVAILABLE',
      ]) {
        await tester.scrollUntilVisible(
          find.text(status),
          find.text(status).evaluate().isNotEmpty &&
                  tester.getTopLeft(find.text(status)).dy < 0
              ? -80
              : 80,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.text(status), findsOneWidget);
      }
      await tester.scrollUntilVisible(
        find.text('Back to My Device'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      await Scrollable.ensureVisible(
        tester.element(find.text('Back to My Device')),
        alignment: .5,
      );
      await tester.pump();
      await tester.tap(find.text('Back to My Device'));
      expect(returned, 1);
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.textContaining('Show '), findsNothing);
      expect(
        find.byType(FilledButton),
        findsOneWidget,
      ); // Only the return action.
      expect(tester.takeException(), isNull);
    });
  }
}
