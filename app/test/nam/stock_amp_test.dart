import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:mighty_plug_manager/nam/rig_editor.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/extra_fx.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';

void main() {
  test('Stock amp choices round trip, stay movable and leave NAM available',
      () {
    stockAmpsAvailable = true;
    availableStockAmpIds = stockAmpIds;
    for (final id in stockAmpIds) {
      final rig = HybridRig.initial(), b = HybridRig.initial();
      final block = rig.blocks.singleWhere((b) => b.slot == 'fxa');
      block.choice = 7;
      block.enabled = true;
      block.effect!.parameters.first.midiValue = id;
      rig.reorder(rig.blocks.indexOf(block), 0);
      final config = rig.fxConfig();
      expect(config[0], 8);
      expect(config[3], id);
      expect(config[2], 0);
      final restored = HybridRig.parse(rig.encode());
      expect(restored.fxConfig(), config);
      expect(restored.blocks.singleWhere((b) => b.slot == 'nam').enabled, true);
      expect(StockControlPlan.maximumType('fxa', 'NAMLNK29'), 8);
      block.choice = 2;
      block.fxWire = config.sublist(0, 16);
      expect(() => rig.fxConfig(), returnsNormally);
      expect(b.fxConfig()[0], 1);
    }
    stockAmpsAvailable = false;
    expect(StockControlPlan.maximumType('fxa', 'NAMLNK29'), 7);
  });
  test('pre-stock-amp Mac library preserves all its existing settings', () {
    final encoded = jsonDecode(HybridRig.initial().encode());
    for (final b in encoded['blocks']) {
      if (['fxa', 'fxb'].contains(b['slot'])) b['settings'].remove('8');
    }
    final restored = HybridRig.parse(jsonEncode(encoded));
    expect(restored.fxConfig(), HybridRig.initial().fxConfig());
  });
  testWidgets(
      'Add Amp is direct, shows the model and bypass retains the Amp tile',
      (t) async {
    stockAmpsAvailable = true;
    availableStockAmpIds = stockAmpIds;
    final rig = HybridRig.initial();
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: RigEditor(
                    rig: rig,
                    firmwareIdentity: 'NAMLNK30',
                    namControls: const SizedBox(),
                    onChanged: () {})))));
    await t.tap(find.byKey(const ValueKey('add-block')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('add-amp')));
    await t.pumpAndSettle();
    final amp = rig.blocks.singleWhere((b) => b.isAmp);
    expect(amp.name, 'Amp');
    expect(amp.modelLabel, 'Jazz Clean');
    expect(find.text('Amp'), findsWidgets);
    expect(find.text('Jazz Clean'), findsWidgets);
    expect(rig.availableAmpSlot, isNull);
    await t.ensureVisible(find.byKey(ValueKey('toggle-${amp.slot}')));
    await t.tap(find.byKey(ValueKey('toggle-${amp.slot}')));
    await t.pumpAndSettle();
    expect(amp.enabled, false);
    expect(find.byKey(ValueKey('block-${amp.slot}')), findsOneWidget);
    expect(t.takeException(), isNull);
    stockAmpsAvailable = false;
    availableStockAmpIds = [];
  });
  test('two stock engines and unsafe models cannot be sent', () {
    final c = defaultFx();
    c[0] = 8;
    c[3] = 30;
    expect(() => validateFx(c), throwsFormatException);
    c[3] = 1;
    c[16] = 8;
    c[19] = 26;
    expect(() => validateFx(c), throwsFormatException);
  });
}
