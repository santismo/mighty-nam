import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/catalog.dart';

void main() {
  test(
      'live snapshot preserves every supported effect and exact control values',
      () {
    final rig = HybridRig.initial();
    for (final block in rig.blocks.where((b) => b.slot != 'nam' && !b.extra)) {
      for (var choice = 0; choice < block.choices.length; choice++) {
        block.choice = choice;
        if (block.effect!.nuxIndex >
            StockControlPlan.supportedTypes[block.slot]!) {
          continue;
        }
        for (final raw in [0, 1, 37, 50, 99, 100]) {
          final plan = StockControlPlan.fromRig(rig);
          final preset = List<int>.filled(128, 0)..[3] = 1;
          for (final pair in plan.controls) {
            preset[StockControlPlan.presetIndex(pair[0])!] = pair[1];
          }
          preset.setRange(90, 99, plan.order.reversed);
          for (final p in block.effect!.parameters) {
            preset[p.devicePresetIndex] = p.formatter is SwitchFormatter
                ? (p.formatter as SwitchFormatter).midiValues.first
                : raw;
          }
          final next =
              StockControlPlan.fromRig(StockControlPlan.readRig(rig, preset));
          expect(next.order, plan.order.reversed.toList());
          for (final pair in next.controls) {
            expect(pair[1], preset[StockControlPlan.presetIndex(pair[0])!],
                reason:
                    '${block.slot} ${block.effect!.name}, CC ${pair[0]}, value $raw');
          }
        }
      }
      block.choice = 0;
    }
  });
  test('every supported effect compiles only scoped volatile control messages',
      () {
    final rig = HybridRig.initial();
    for (final block in rig.blocks.where((b) => b.slot != 'nam' && !b.extra)) {
      for (var i = 0; i < block.choices.length; i++) {
        block.choice = i;
        if (block.effect!.nuxIndex >
            StockControlPlan.supportedTypes[block.slot]!) {
          expect(() => StockControlPlan.fromRig(rig), throwsFormatException);
        } else {
          final plan = StockControlPlan.fromRig(rig);
          expect(plan.order.toSet(), {1, 2, 3, 4, 5, 6, 7, 8, 9});
          expect(plan.controls.map((p) => p[0]).toSet().length,
              plan.controls.length);
          expect(
              plan.controls.any(
                  (p) => p[0] == 3 || (p[0] >= 23 && p[0] <= 30) || p[0] >= 71),
              false);
          final preset = List<int>.filled(128, 0);
          for (final p in plan.controls) {
            preset[StockControlPlan.presetIndex(p[0])!] = p[1];
          }
          preset.setRange(90, 99, plan.order);
          final restored = StockControlPlan.fromSnapshot(preset);
          for (final p in plan.controls) {
            expect(
                restored.controls.singleWhere((value) => value[0] == p[0]), p);
          }
        }
      }
      block.choice = 0;
    }
  });
  test('invalid snapshots cannot be used to restore physical settings', () {
    expect(() => StockControlPlan.fromSnapshot([]), throwsFormatException);
    expect(() => StockControlPlan.fromSnapshot(List.filled(128, 0)),
        throwsFormatException);
  });
}
