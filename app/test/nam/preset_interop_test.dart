import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/onboard_presets.dart';
import 'package:nam_link/nam_link.dart';
import 'connected_workflow_test.dart' show capture;
import 'onboard_presets_test.dart' show BankFixture;

void main() {
  test('Dart preset client exports and consumes the native ARM trace',
      () async {
    final dir = Platform.environment['NAM_PRESET_INTEROP'];
    if (dir == null) {
      return; // The ordinary suite runs separate controller cases.
    }
    final prefix = '$dir/preset-wire';
    final actual = File('$prefix.replies.json');
    final replies = actual.existsSync()
        ? jsonDecode(actual.readAsStringSync()) as List
        : null;
    final usb = BankFixture(), model = capture('Interop A2', .7);
    usb.catalog.add(model);
    await TransferClient(usb.receiver).upload(model);
    final requests = <List<int>>[];
    final client = PresetClient((raw) async {
      requests.add(raw.toList());
      if (replies != null) {
        return Uint8List.fromList(List<int>.from(replies[requests.length - 1]));
      }
      return await usb.call(MethodCall('exchangePresetFrame', {'frame': raw}))
          as Uint8List;
    })
      ..nonce = 123;
    final saved = await client.save(0, model, usb.preset, 'Green Interop', 8);
    final read = await client.read(0), recall = await client.recall(0);
    for (final result in [saved, read, recall]) {
      expect(result.modelSha, model.sha256Hex);
      expect(result.modelCrc, model.checksum);
      expect(result.name, 'Green Interop');
      expect(result.generation, 1);
      expect(result.active, 0);
      expect(result.effects, usb.preset);
    }
    File('$prefix.requests.json').writeAsStringSync(jsonEncode(requests));
    File('$prefix.slot').writeAsBytesSync(model.slot);
    File('$prefix.effects').writeAsBytesSync(usb.preset);
    if (replies != null) {
      File('$prefix.dart-result.json').writeAsStringSync(jsonEncode({
        'status': 'PASS_DART_PRESET_ARM_REPLIES',
        'operations': 3,
        'audioAccess': false
      }));
    }
  }, skip: Platform.environment['NAM_PRESET_INTEROP'] == null);
}
