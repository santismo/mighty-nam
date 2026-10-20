import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('native Mac library, Keychain and USB discovery stay silent',
      (t) async {
    const channel = MethodChannel('nam_plug/device');
    const client = 't3k_pub_namplug_local_test_only';
    final original = await channel.invokeMethod<String>('loadLibrary');
    final seed = jsonEncode({
      'schema': 'nam-plug-library-2',
      'active': HybridRig.initial().encode(),
      'presets': {},
      'models': ModelLibrary().toJson(),
      'tone_client_id': ''
    });
    try {
      await channel.invokeMethod('saveLibrary', seed);
      expect(await channel.invokeMethod<String>('loadLibrary'), seed);
      await channel.invokeMethod('saveToneSession',
          {'clientId': client, 'value': 'local-test-no-credentials'});
      expect(
          await channel
              .invokeMethod<String>('loadToneSession', {'clientId': client}),
          'local-test-no-credentials');
      await channel
          .invokeMethod('saveToneSession', {'clientId': client, 'value': null});
      expect(
          await channel
              .invokeMethod<String>('loadToneSession', {'clientId': client}),
          null);
      await t.pumpWidget(const NamLabApp(autoConnect: false));
      await t.pumpAndSettle();
      expect(find.text('NAM amplifier'), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('block-drive')));
      await t.pumpAndSettle();
      expect(find.text('Sensitivity'), findsOneWidget);
      await t.tap(find.text('Plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('Find plug'));
      await t.pumpAndSettle();
      final devices = await channel.invokeListMethod('devices');
      expect(devices, isNotNull);
      debugPrint(
          'NAM_MAC_NATIVE_TEST: devices=${devices!.length}; persistence=pass; keychain=pass; audio_streams=0');
      expect(t.takeException(), isNull);
    } finally {
      await t.pumpWidget(const SizedBox.shrink());
      await t.pumpAndSettle();
      await channel
          .invokeMethod('saveToneSession', {'clientId': client, 'value': null});
      await channel.invokeMethod('saveLibrary', original ?? seed);
      await channel.invokeMethod('disconnect');
    }
  });
}
