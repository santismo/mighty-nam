import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';
import 'package:nam_link/nam_link.dart';

// Opt-in physical trial using the real desktop UI and native USB plugin.
// Test models are provided locally at build time, never committed or fetched.
// No host audio APIs, volume controls, firmware writer, or account changes.
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;
  testWidgets('Mac capture selection uploads to the physical silent plug',
      (t) async {
    const channel = MethodChannel('nam_plug/device');
    debugPrint('NAM_MAC_UI_STEP: read library');
    final original = await channel
        .invokeMethod<String>('loadLibrary')
        .timeout(const Duration(seconds: 10));
    debugPrint('NAM_MAC_UI_STEP: library read');
    final empty = jsonEncode({
      'schema': 'nam-plug-library-2',
      'active': HybridRig.initial().encode(),
      'presets': {},
      'models': ModelLibrary().toJson(),
      'tone_client_id': ''
    });
    final models = [
      LiteModel.parse(
          base64Decode(const String.fromEnvironment('TEST_MODEL_ONE')),
          provenance: {
            'name': 'BE100 Lite hardware check',
            'source': 'local test'
          }),
      LiteModel.parse(
          base64Decode(const String.fromEnvironment('TEST_MODEL_TWO')),
          provenance: {
            'name': 'Marshall Lite hardware check',
            'source': 'local test'
          }),
    ];
    int? connectedSource;
    List<int>? originalControls;
    Future<void> until(bool Function() ready) async {
      final end = DateTime.now().add(const Duration(seconds: 30));
      while (!ready() && DateTime.now().isBefore(end)) {
        await t.pump(const Duration(milliseconds: 100));
      }
      expect(ready(), isTrue, reason: 'Desktop operation did not finish');
    }

    Future<void> press(Finder target) async {
      await t.ensureVisible(target);
      await t.tap(target);
      await t.pump();
    }

    Future<List> read(int source) async {
      final result = await channel
          .invokeMapMethod<String, dynamic>('inspect', {'source': source});
      expect(result!['identity'], 'NAMLNK01');
      expect(result['audioStreamOpened'], false);
      return result['words'] as List;
    }

    try {
      final library = ModelLibrary();
      for (final model in models) {
        library.add(model);
      }
      await channel.invokeMethod(
          'saveLibrary',
          jsonEncode({
            'schema': 'nam-plug-library-2',
            'active': HybridRig.initial().encode(),
            'presets': {},
            'models': library.toJson(),
            'tone_client_id': ''
          }));
      debugPrint('NAM_MAC_UI_STEP: test captures seeded');
      await t.pumpWidget(const NamLabApp(autoConnect: false));
      await t.pumpAndSettle();
      debugPrint('NAM_MAC_UI_STEP: app ready');
      await press(find.text('Plug'));
      await t.pumpAndSettle();
      await press(find.text('Find plug'));
      await until(() => find.text('MIGHTY PLUG PRO USB').evaluate().isNotEmpty);
      await press(find.text('MIGHTY PLUG PRO USB'));
      await until(() => find.text('Connected · silent').evaluate().isNotEmpty);
      final devices = await channel.invokeListMethod('devices');
      expect(devices!.length, 1);
      final source = devices.single['source'] as int;
      connectedSource = source;
      final stock = await channel.invokeMapMethod<String, dynamic>(
          'readStockControls', {'source': source});
      originalControls = List<int>.from(stock!['preset']);
      // Refuse any physical setting changes unless the original is restorable.
      StockControlPlan.fromSnapshot(originalControls);
      debugPrint('NAM_MAC_UI_STEP: connected');
      var previous = await read(source);
      expect(previous[4], 0);
      final evidence = <Map<String, dynamic>>[];
      for (final model in models) {
        debugPrint('NAM_MAC_UI_STEP: select ${model.metadata['name']}');
        await press(find.text('Captures'));
        await t.pumpAndSettle();
        final row = find.ancestor(
            of: find.text(model.metadata['name'] as String),
            matching: find.byType(Card));
        await press(
            find.descendant(of: row, matching: find.text('Use capture')));
        await until(() => (t.state(find.byType(NamHome)) as dynamic)
            .status
            .toString()
            .contains('${model.metadata['name']} is running on the plug.'));
        expect(find.text('NAM amplifier'), findsOneWidget);
        final after = await read(source);
        expect(after[4], 0);
        expect(after[5], model.checksum);
        expect(after[6], previous[6] + 1);
        expect(after[9], 1);
        expect(after[10], 0);
        await press(find.byKey(const ValueKey('favorite-loaded-model')));
        await t.pumpAndSettle();
        final saved =
            jsonDecode((await channel.invokeMethod<String>('loadLibrary'))!);
        expect(saved['models']['favorites'], contains(model.sha256Hex));
        expect(HybridRig.parse(saved['active']).modelSha256, model.sha256Hex);
        await t.pump(const Duration(seconds: 2));
        final later = await read(source);
        expect(later[4], 0);
        expect(later[7], greaterThan(after[7]));
        expect(later[9], 1);
        evidence.add({
          'model': model.metadata['name'],
          'crc': model.checksum,
          'generation': later[6],
          'runs': later[7],
          'timerMax': later[8],
          'faults': later[4],
          'favoriteSaved': true
        });
        previous = later;
      }
      expect(t.takeException(), isNull);
      await press(find.byKey(const ValueKey('block-drive')));
      await t.pumpAndSettle();
      await press(find.byKey(const ValueKey('choose-effect-drive')));
      await t.pumpAndSettle();
      await t.enterText(
          find.byKey(const ValueKey('search-effects')), 'screamer');
      await t.pumpAndSettle();
      await press(find.text('T Screamer'));
      await t.pumpAndSettle();
      await press(find.byKey(const ValueKey('toggle-drive')));
      await t.pumpAndSettle();
      await press(find.byTooltip('Move later'));
      await t.pumpAndSettle();
      await press(find.byKey(const ValueKey('send-stock-controls')));
      await until(() => (t.state(find.byType(NamHome)) as dynamic)
          .status
          .toString()
          .contains(
              'Effect choices, controls and order verified on the plug.'));
      final saved =
          jsonDecode((await channel.invokeMethod<String>('loadLibrary'))!);
      final plan = StockControlPlan.fromRig(HybridRig.parse(saved['active']));
      final actual = await channel.invokeMapMethod<String, dynamic>(
          'readStockControls', {'source': source});
      final preset = List<int>.from(actual!['preset']);
      for (final control in plan.controls) {
        expect(preset[StockControlPlan.presetIndex(control[0])!], control[1]);
      }
      expect(preset.sublist(90, 99), plan.order);
      expect(preset[2], 0x45); // T Screamer, bypassed.
      expect(
          preset[3], originalControls[3]); // Retired stock amp never written.
      final afterControls = await read(source);
      expect(afterControls[4], 0);
      expect(afterControls[5], models.last.checksum);
      expect(afterControls[9], 1);
      debugPrint('NAM_MAC_PHYSICAL_UI: ${jsonEncode({
            'status': 'PASS',
            'models': evidence,
            'audioStreams': 0,
            'macAudioSettingsChanged': false,
            'teamsSettingsChanged': false,
            'productionWidgets': true,
            'nativePlugin': true,
            'build': 'instrumented Mac integration build',
            'stockControlFieldsVerified': plan.controls.length,
            'stockOrderVerified': plan.order,
            'stockDSPActive': false
          })}');
    } finally {
      await t.pumpWidget(const SizedBox.shrink());
      if (connectedSource != null && originalControls != null) {
        final restore = StockControlPlan.fromSnapshot(originalControls);
        final restored = await channel.invokeMapMethod<String, dynamic>(
            'applyStockControls', {
          'source': connectedSource,
          'controls': restore.controls,
          'order': restore.order
        });
        expect(restored!['controlsVerified'], isTrue);
        debugPrint(
            'NAM_MAC_UI_STEP: original hardware controls restored and verified');
      }
      await channel.invokeMethod('disconnect');
      await channel.invokeMethod('saveLibrary', original ?? empty);
      expect(
          await channel.invokeMethod<String>('loadLibrary'), original ?? empty);
    }
  },
      skip: !const bool.fromEnvironment('RUN_PHYSICAL_NAM_LINK'),
      timeout: const Timeout(Duration(minutes: 3)));
}
