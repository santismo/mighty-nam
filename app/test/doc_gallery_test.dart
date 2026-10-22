// Opt-in rendering of the actual Mac widgets with a simulated connection.
// No device, user library, network, microphone or audio APIs are available.
import 'dart:io';
import 'dart:convert';
import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';
import 'package:nam_link/nam_link.dart';

void main() {
  final output = Platform.environment['MIGHTY_NAM_GALLERY'];
  testWidgets('render documented Mac examples', (t) async {
    final fonts = Platform.environment['MIGHTY_NAM_FONT_DIR']!;
    for (final family in ['Roboto', '.SF Pro Text', '.SF Pro Display', '.AppleSystemUIFont']) {
      final loader = FontLoader(family)
        ..addFont(Future.value(ByteData.sublistView(
            File(family == '.AppleSystemUIFont' ? '/System/Library/Fonts/SFNS.ttf' : '$fonts/Roboto-Regular.ttf').readAsBytesSync())));
      await loader.load();
    }
    final icons = FontLoader('MaterialIcons')
      ..addFont(Future.value(ByteData.sublistView(
          File('$fonts/MaterialIcons-Regular.otf').readAsBytesSync())));
    await icons.load();
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    await t.binding.setSurfaceSize(const Size(1440, 1280));
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
      t.binding.setSurfaceSize(null);
    });
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('nam_plug/device'),
            (call) async {
      if (call.method == 'loadLibrary') return null;
      throw StateError('Unexpected gallery device call: ${call.method}');
    });
    final key = GlobalKey();
    final raw =
        jsonDecode(File('assets/starter-captures.json').readAsStringSync());
    final model =
        LiteModel.restore(Map<String, dynamic>.from(raw['models'][0]));
    for (final full in [false, true]) {
      await t.pumpWidget(const SizedBox());
      await t.pumpWidget(RepaintBoundary(
          key: key, child: const NamLabApp(autoConnect: false)));
      await t.pumpAndSettle();
      final dynamic state = t.state(find.byType(NamHome));
      final rig = HybridRig.initial()
        ..name = 'RiffSmith Clean'
        ..modelSha256 = model.sha256Hex
        ..masterVolume = 37;
      final enabled = full
          ? {
              'gate',
              'comp',
              'fxa',
              'fxb',
              'drive',
              'nam',
              'eq',
              'delay',
              'reverb'
            }
          : {'nam', 'reverb'};
      for (final b in rig.blocks) b.enabled = enabled.contains(b.slot);
      state.setState(() {
        state.rig = rig;
        state.captures = ModelLibrary()..add(model);
        state.hardware = {'identity': 'NAMLNK23', 'compatible': true};
        state.status = '';
      });
      await t.pumpAndSettle();
      if (full) {
        await t.tap(find.byKey(const ValueKey('block-fxa')));
        await t.pumpAndSettle();
      }
      expect(t.takeException(), isNull);
      await t.runAsync(() async {
        final image = await (key.currentContext!.findRenderObject()
                as RenderRepaintBoundary)
            .toImage(pixelRatio: 1);
        final png = await image.toByteData(format: ui.ImageByteFormat.png);
        File('$output/mac-${full ? 'full' : 'small'}.png')
            .writeAsBytesSync(png!.buffer.asUint8List());
        image.dispose();
      });
    }
    await t.pumpWidget(const SizedBox());
    debugDefaultTargetPlatformOverride = null;
  }, skip: output == null);
}
