import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';

void main() {
  test('older chains gain neutral cut defaults without losing saved settings',
      () {
    final old = jsonDecode(HybridRig.initial().encode()) as Map;
    final eq = (old['blocks'] as List).firstWhere((b) => b['slot'] == 'eq');
    eq['settings'].remove('4');
    final rig = HybridRig.parse(jsonEncode(old));
    final block = rig.blocks.singleWhere((b) => b.slot == 'eq');
    expect(block.effect!.nuxIndex, 1);
    final cut = block.choices.singleWhere((e) => e.nuxIndex == 4);
    expect(cut.parameters.map((p) => p.midiValue), [0, 0]);
    expect(cut.parameters.first.formatter.toLabel(0), 'Off');
    expect(cut.parameters.first.formatter.toLabel(1), '20 Hz');
    expect(cut.parameters.last.formatter.toLabel(100), '20.00 kHz');
  });
  test(
      'NAMLNK14 cut controls survive snapshot and storage; old firmware refuses writes',
      () {
    final rig = HybridRig.initial();
    final eq = rig.blocks.singleWhere((b) => b.slot == 'eq');
    eq.choice = eq.choices.indexWhere((e) => e.nuxIndex == 4);
    eq.enabled = true;
    eq.effect!.parameters[0].midiValue = 37;
    eq.effect!.parameters[1].midiValue = 81;
    expect(() => StockControlPlan.fromRig(rig, identity: 'NAMLNK13'),
        throwsFormatException);
    final plan = StockControlPlan.fromRig(rig, identity: 'NAMLNK14');
    final preset = List<int>.filled(128, 0)..[3] = 1;
    for (final p in plan.controls) {
      preset[StockControlPlan.presetIndex(p[0])!] = p[1];
    }
    preset.setRange(90, 99, plan.order);
    final restored =
        StockControlPlan.readRig(rig, preset, identity: 'NAMLNK14');
    expect(
        HybridRig.parse(restored.encode())
            .blocks
            .singleWhere((b) => b.slot == 'eq')
            .effect!
            .parameters
            .map((p) => p.midiValue),
        [37, 81]);
  });
}
