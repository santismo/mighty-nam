import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';

void main() {
  for (final identity in ['NAMLNK24', 'NAMLNK25', 'NAMLNK26']) {
    test(
        'Touch Wah type and parameters survive Mac storage and $identity readback',
        () {
      final rig = HybridRig.initial();
      final drive = rig.blocks.singleWhere((b) => b.slot == 'drive');
      drive.choice = drive.choices.indexWhere((e) => e.nuxIndex == 14);
      drive.enabled = true;
      expect(drive.effect!.parameters.map((p) => p.midiValue),
          [1, 35, 90, 100, 0]);
      final values = [3, 60, 75, 65, 1];
      for (var i = 0; i < values.length; i++) {
        drive.effect!.parameters[i].midiValue = values[i];
      }
      expect(() => StockControlPlan.fromRig(rig, identity: 'NAMLNK23'),
          throwsFormatException);
      final plan = StockControlPlan.fromRig(rig, identity: identity);
      final preset = List<int>.filled(128, 0)..[3] = 1;
      for (final p in plan.controls) {
        preset[StockControlPlan.presetIndex(p[0])!] = p[1];
      }
      preset.setRange(90, 99, plan.order);
      expect(preset.sublist(20, 25), [3, 60, 75, 1, 65]);
      final restored =
          StockControlPlan.readRig(rig, preset, identity: identity);
      final saved = HybridRig.parse(restored.encode())
          .blocks
          .singleWhere((b) => b.slot == 'drive');
      expect(saved.effect!.nuxIndex, 14);
      expect(saved.effect!.parameters.map((p) => p.midiValue), values);
      expect(StockControlPlan.maximumType('drive', 'NAMLNK23'), 13);
      expect(StockControlPlan.maximumType('drive', identity), 14);
    });
  }
}
