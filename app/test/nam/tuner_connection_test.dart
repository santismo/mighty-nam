import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'connected_workflow_test.dart' show UsbFixture;
import 'package:nam_link/nam_link.dart';
import 'tuner_test.dart' show Fixture;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => debugDefaultTargetPlatformOverride = TargetPlatform.macOS);
  tearDown(() => debugDefaultTargetPlatformOverride = null);
  for (final identity in ['NAMLNK10', 'NAMLNK12', 'NAMLNK13']) {
    testWidgets('tuner transport gate and mute lifecycle: $identity',
        (t) async {
      final usb = UsbFixture()
        ..identity = identity
        ..listening = true;
      await TransferClient(usb.receiver).upload(LiteModel.fixture());
      final tuner = Fixture();
      var refusedMute = false;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel('nam_plug/device'),
              (c) async {
        if (c.method == 'tunerFrame') {
          expect(usb.listening, false);
          final a = c.arguments as Map;
          return tuner.call(
              a['operation'] as int, a['page'] as int, a['nonce'] as int);
        }
        if (c.method == 'readStockControls') {
          return {'identity': identity, 'preset': usb.preset};
        }
        if (c.method == 'setListening' && refusedMute) return usb.status();
        return usb.call(c);
      });
      await t.binding.setSurfaceSize(const Size(1120, 1100));
      addTearDown(() async {
        await t.pumpWidget(const SizedBox.shrink());
        await t.pump();
        await t.binding.setSurfaceSize(null);
      });
      await t.pumpWidget(const NamLabApp());
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('open-tuner')));
      await t.pump();
      await t.pump(const Duration(milliseconds: 220));
      await t.pump();
      if (identity == 'NAMLNK10') {
        expect(tuner.starts, 0);
        expect(usb.listenCommands, isEmpty);
        expect(find.textContaining('The tuner needs NAMLNK12'), findsOneWidget);
      } else {
        expect(tuner.starts, greaterThan(0));
        expect(usb.listenCommands, [false]);
        expect(find.text('A4'), findsOneWidget);
        await t.tap(find.byKey(const ValueKey('close-tuner')));
        await t.pump(const Duration(milliseconds: 220));
        await t.pumpAndSettle();
        expect(tuner.stops, 1);
        expect(usb.listenCommands, [false, true]);
        expect(usb.listening, true);
        expect(usb.transfers, 0);
        expect(usb.applies, 0);
        final starts = tuner.starts;
        // Refusing a mute acknowledgment must prevent starting another capture.
        refusedMute = true;
        usb.listening = true;
        await t.tap(find.byKey(const ValueKey('open-tuner')));
        await t.pumpAndSettle();
        expect(tuner.starts, starts);
        expect(find.textContaining('Could not confirm'), findsOneWidget);
      }
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      debugDefaultTargetPlatformOverride = null;
    });
  }
}
