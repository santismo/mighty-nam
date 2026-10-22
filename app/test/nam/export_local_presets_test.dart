// Explicit local export only. No platform channels, MIDI, audio or credentials.
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/onboard_presets.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';

void main() {
  final source = Platform.environment['MIGHTY_NAM_LIBRARY_EXPORT_SOURCE'];
  final destination = Platform.environment['MIGHTY_NAM_LIBRARY_EXPORT_DEST'];
  test('export seven local colors through production model and chain validation',
      () async {
    final json = jsonDecode(await File(source!).readAsString());
    expect(json['schema'], 'nam-plug-library-2');
    final bank = OnboardPresets.parse(json['onboard']);
    final models = ModelLibrary.parse(json['models']);
    final rows = <Map<String, dynamic>>[];
    for (var color = 0; color < 7; color++) {
      final rig = bank.slots[color];
      final model = models.captures[rig.modelSha256];
      expect(model, isNotNull, reason: 'Missing capture for color $color');
      final plan = StockControlPlan.fromRig(rig, identity: 'NAMLNK23');
      rows.add({
        'color': color,
        'name': rig.name,
        'controls': plan.controls,
        'model': model!.toRecord(),
        'effects': {
          for (final cc in plan.controls)
            '${StockControlPlan.presetIndex(cc[0])!}': cc[1]
        },
        'order': plan.order,
        'nam_enabled': rig.blocks.singleWhere((b) => b.slot == 'nam').enabled,
        'nam_tone': rig.namTone,
        'usb_record_gain': rig.usbRecordGain,
        'fx': rig.fxConfig(),
      });
    }
    await File(destination!).writeAsString(jsonEncode({
      'schema': 'mighty-nam-local-preset-export-1',
      'selected': bank.selected,
      'presets': rows,
    }));
  }, skip: source == null || destination == null);
}
