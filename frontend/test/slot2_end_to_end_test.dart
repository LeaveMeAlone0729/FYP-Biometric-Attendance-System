// Opt-in cross-process integration only. No fixture switch exists in lib/.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/io_client.dart';
import 'package:frontend/services/api_client.dart';
import 'package:frontend/theme.dart';
import 'package:frontend/modules/devices/services/device_api.dart';
import 'package:frontend/modules/devices/services/device_key_store.dart';
import 'package:frontend/modules/devices/services/pending_device_service.dart';
import 'package:frontend/modules/devices/services/device_biometric_api.dart';
import 'package:frontend/modules/devices/services/device_activation_service.dart';
import 'package:frontend/modules/devices/services/device_verification_service.dart';
import 'package:frontend/modules/devices/screens/my_device_screen.dart';

class RealLoopbackHttp extends HttpOverrides {}

void main() {
  final manifestPath = Platform.environment['SLOT2_E2E_MANIFEST'];
  testWidgets(
    'Real HTTP and MariaDB registration or replacement refreshes My Device to 2/2',
    (tester) async {
      final manifest =
          jsonDecode(File(manifestPath!).readAsStringSync()) as Map;
      final replacementTarget = manifest['replacement_target'] == null
          ? null
          : Map<String, dynamic>.from(manifest['replacement_target'] as Map);
      final operation = replacementTarget == null
          ? 'enroll_second_device'
          : 'replace_device';
      final slot = replacementTarget?['slot_number'] as int? ?? 2;
      final uri = Uri.parse(manifest['base_url'] as String);
      if (uri.host != '127.0.0.1' || uri.port == 8000) {
        throw StateError('Integration must not contact production');
      }
      final oldHttp = HttpOverrides.current, oldClient = ApiClient.instance;
      HttpOverrides.global = RealLoopbackHttp();
      final transport = IOClient(HttpClient());
      final client = ApiClient(url: uri.toString(), client: transport);
      ApiClient.instance = client;
      final signatures = <String>[];
      var keyCreations = 0;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(DeviceKeyStore.channel, (call) async {
            final args = Map<String, dynamic>.from(call.arguments as Map);
            if (args['student_id'] != manifest['student']) {
              throw PlatformException(code: 'WRONG_FIXTURE_STUDENT');
            }
            if (call.method == 'getPublicKey') {
              return {
                'public_key_spki': manifest['public_key_spki'],
                'public_key_fingerprint': manifest['public_key_fingerprint'],
                'device_model': 'Software P256 fixture',
              };
            }
            if (call.method == 'getOrCreateKey') {
              keyCreations++;
              throw StateError('Retained candidate key must not rotate');
            }
            if (call.method == 'sign') {
              final payload = args['signing_payload'] as String;
              final data =
                  jsonDecode(utf8.decode(base64Decode(payload))) as Map;
              signatures.add((data['purpose'] ?? data['operation']) as String);
              final signed = await Process.run(manifest['python'] as String, [
                manifest['signer'] as String,
                '--key',
                manifest['key_path'] as String,
                '--payload',
                payload,
              ]);
              if (signed.exitCode != 0) {
                throw StateError('Disposable test signer failed');
              }
              return (signed.stdout as String).trim();
            }
            throw StateError('Unexpected key operation');
          });
      final snapshot = GlobalKey();
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      try {
        late Map<String, dynamic> initial, pending, biometric, active;
        await tester.runAsync(() async {
          final font = FontLoader('PatrickHand');
          font.addFont(
            Future.value(
              ByteData.sublistView(
                File('assets/fonts/PatrickHand-Regular.ttf').readAsBytesSync(),
              ),
            ),
          );
          await font.load();
          await client.login(
            manifest['student'] as String,
            manifest['password'] as String,
          );
          initial = await DeviceApi(client).listDevices();
          pending = await PendingDeviceService(
            client: client,
            replacementTarget: replacementTarget,
          ).prepare('Integration tablet');
          final bio = DeviceBiometricApi(client, operation, slot);
          await bio.begin(pending['pending_registration_id'] as String);
          biometric = await bio.frame(
            Uint8List.fromList(utf8.encode('e2e-fresh-face')),
            liveness: false,
          );
          if (biometric['stage'] != 'LIVENESS') {
            throw StateError('Server face verification did not pass');
          }
          for (var i = 0; i < 3; i++) {
            biometric = await bio.frame(
              Uint8List.fromList(utf8.encode('e2e-fresh-live-$i')),
              liveness: true,
            );
          }
          active =
              await DeviceActivationService(
                client: client,
                operation: operation,
                slotNumber: slot,
                replacedDeviceId: replacementTarget?['device_id'] as String?,
                replacedDeviceFingerprint:
                    replacementTarget?['public_key_fingerprint'] as String?,
              ).activate(
                pending['pending_registration_id'] as String,
                expectedCandidateId: pending['candidate_device_id'] as String,
                expectedFingerprint:
                    pending['public_key_fingerprint'] as String,
              );
        });
        expect(initial['active_count'], replacementTarget == null ? 1 : 2);
        expect(pending['status'], 'KEY_PROVEN');
        expect(biometric['stage'], 'COMPLETED_UNTRUSTED');
        expect(biometric['trusted'], isFalse);
        expect(active['status'], 'ACTIVE');
        expect(active['slot_number'], slot);
        // This is the actual production screen and automatic verification service,
        // reading the real HTTP API AFTER its committed MariaDB insertion.
        await tester.runAsync(() async {
          await tester.pumpWidget(
            RepaintBoundary(
              key: snapshot,
              child: MaterialApp(
                theme: appTheme(),
                debugShowCheckedModeBanner: false,
                home: MyDeviceScreen(
                  api: DeviceApi(client),
                  verificationService: DeviceVerificationService(
                    client: client,
                  ),
                ),
              ),
            ),
          );
        });
        for (var i = 0; i < 80; i++) {
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 100)),
          );
          await tester.pump();
          if (find
              .textContaining('Automatic device verification: PASS')
              .evaluate()
              .isNotEmpty) {
            break;
          }
        }
        expect(find.text('2 / 2 ACTIVE devices'), findsOneWidget);
        expect(find.text('Slot $slot: Integration tablet'), findsOneWidget);
        expect(
          find.text(
            slot == 1
                ? 'Slot 2: Existing tablet fixture'
                : 'Slot 1: Samsung fixture',
          ),
          findsOneWidget,
        );
        expect(
          find.textContaining('Automatic device verification: PASS'),
          findsOneWidget,
        );
        expect(find.text('This installation'), findsOneWidget);
        expect(keyCreations, 0);
        expect(signatures.where((p) => p == 'device_activation').length, 1);
        expect(signatures, contains(operation));
        expect(signatures, contains('device_verification'));
        expect(tester.takeException(), isNull);
        await tester.runAsync(() async {
          final image =
              await (snapshot.currentContext!.findRenderObject()
                      as RenderRepaintBoundary)
                  .toImage();
          final png = await image.toByteData(format: ui.ImageByteFormat.png);
          await File(
            '${manifest['output_dir']}/my-device-two-active.png',
          ).writeAsBytes(png!.buffer.asUint8List());
          image.dispose();
          await File(
            '${manifest['output_dir']}/flutter-evidence.json',
          ).writeAsString(
            jsonEncode({
              'initial_active_count': initial['active_count'],
              'pending_status': pending['status'],
              'biometric_status': biometric['stage'],
              'activation_status': active['status'],
              'displayed_active_count': 2,
              'retained_key_creations': keyCreations,
              'signed_purposes': signatures,
            }),
          );
        });
      } finally {
        await tester.pumpWidget(const SizedBox());
        await tester.pump();
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(DeviceKeyStore.channel, null);
        transport.close();
        ApiClient.instance = oldClient;
        HttpOverrides.global = oldHttp;
      }
    },
    skip: manifestPath == null,
  );
}
