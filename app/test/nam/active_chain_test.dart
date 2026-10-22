import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';
import 'package:mighty_plug_manager/nam/rig_editor.dart';

void main() {
  test('active order and membership survive wire, local save and FX round trip',
      () {
    final rig = HybridRig.initial();
    for (final b in rig.blocks) {
      b.enabled = b.slot == 'nam' || b.slot == 'reverb';
    }
    expect(rig.visibleBlocks(activeOnly: true).map((b) => b.slot),
        ['nam', 'reverb']);
    rig.moveVisible(1, 0, activeOnly: true);
    expect(rig.visibleBlocks(activeOnly: true).map((b) => b.slot),
        ['reverb', 'nam']);
    for (final slot in ['fxa', 'fxb']) {
      rig.addBlock(rig.blocks.singleWhere((b) => b.slot == slot));
    }
    final encoded = HybridRig.parse(rig.encode());
    final plan = StockControlPlan.fromRig(encoded, identity: 'NAMLNK20');
    final preset = List<int>.filled(128, 0)..[3] = 1;
    for (final cc in plan.controls) {
      preset[StockControlPlan.presetIndex(cc[0])!] = cc[1];
    }
    preset.setRange(90, 99, plan.order);
    final restored = StockControlPlan.readRig(encoded, preset,
        identity: 'NAMLNK20', fx: encoded.fxConfig());
    expect(restored.visibleBlocks(activeOnly: true).map((b) => b.slot),
        ['reverb', 'nam', 'fxa', 'fxb']);
    expect(restored.blocks.length, 11);
    expect(restored.fxConfig(), encoded.fxConfig());
  });
  for (final identity in ['NAMLNK20', 'NAMLNK21', 'NAMLNK22'])
    testWidgets(
        '$identity shows two nodes, removes either, adds with retained settings, and handles empty',
        (t) async {
      await t.binding.setSurfaceSize(const Size(1100, 1000));
      addTearDown(() => t.binding.setSurfaceSize(null));
      final rig = HybridRig.initial();
      for (final b in rig.blocks) {
        b.enabled = ['nam', 'reverb'].contains(b.slot);
      }
      var changes = 0;
      await t.pumpWidget(MaterialApp(
          home: Scaffold(
              body: SingleChildScrollView(
                  child: RigEditor(
                      rig: rig,
                      firmwareIdentity: identity,
                      namControls: const Text('Capture controls'),
                      onChanged: () => changes++)))));
      expect(find.byKey(const ValueKey('block-nam')), findsOneWidget);
      expect(find.byKey(const ValueKey('block-reverb')), findsOneWidget);
      expect(find.byKey(const ValueKey('block-drive')), findsNothing);
      await t.tap(find.byKey(const ValueKey('remove-nam')));
      await t.pumpAndSettle();
      expect(find.byKey(const ValueKey('block-nam')), findsNothing);
      await t.tap(find.byKey(const ValueKey('toggle-reverb')));
      await t.pumpAndSettle();
      expect(find.byKey(const ValueKey('block-reverb')), findsOneWidget);
      expect(rig.blocks.singleWhere((b) => b.slot == 'reverb').enabled, false);
      await t.tap(find.byKey(const ValueKey('remove-reverb')));
      await t.pumpAndSettle();
      expect(find.byKey(const ValueKey('selected-controls')), findsNothing);
      for (final slot in ['nam', 'reverb', 'fxa', 'fxb']) {
        await t.tap(find.byKey(const ValueKey('add-block')));
        await t.pumpAndSettle();
        await t.scrollUntilVisible(find.byKey(ValueKey('add-$slot')), 100,
            scrollable: find.byType(Scrollable).last);
        await t.tap(find.byKey(ValueKey('add-$slot')));
        await t.pumpAndSettle();
        expect(find.byKey(ValueKey('block-$slot')), findsOneWidget);
      }
      expect(changes, 7);
      expect(rig.visibleBlocks(activeOnly: true).length, 4);
      expect(t.takeException(), isNull);
    });
  test(
      'bypass presence survives local save; replace keeps position and settings',
      () {
    final rig = HybridRig.initial();
    final nam = rig.blocks.singleWhere((b) => b.slot == 'nam');
    final drive = rig.blocks.singleWhere((b) => b.slot == 'drive');
    final position = rig.blocks.indexOf(nam);
    rig.bypassBlock(nam, false);
    final copy = HybridRig.parse(rig.encode());
    expect(copy.visibleBlocks(activeOnly: true).map((b) => b.slot),
        contains('nam'));
    expect(copy.blocks.singleWhere((b) => b.slot == 'nam').enabled, false);
    rig.replaceBlock(nam, drive);
    expect(rig.blocks.indexOf(drive), position);
    expect(rig.visibleBlocks(activeOnly: true), contains(drive));
    expect(rig.visibleBlocks(activeOnly: true), isNot(contains(nam)));
    expect(drive.enabled, false);
    rig.removeBlock(drive);
    expect(rig.visibleBlocks(activeOnly: true), isNot(contains(drive)));
  });
}
