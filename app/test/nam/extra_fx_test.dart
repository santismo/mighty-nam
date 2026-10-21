import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/fx_client.dart';
import 'package:mighty_plug_manager/nam/rig_editor.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/extra_fx.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';

void main() {
  test('nine-block libraries migrate without changing stock choices or order',
      () {
    final rig = HybridRig.initial();
    final old = jsonDecode(rig.encode()) as Map;
    (old['blocks'] as List)
        .removeWhere((b) => ['fxa', 'fxb'].contains(b['slot']));
    final imported = HybridRig.parse(jsonEncode(old));
    expect(imported.blocks.length, 11);
    expect(imported.fxConfig(), defaultFx());
    expect(
        StockControlPlan.fromRig(imported).order, [5, 1, 2, 3, 9, 4, 6, 7, 8]);
  });
  test(
      'all FX types and placements round-trip through live data and local presets',
      () {
    final rig = HybridRig.initial();
    final plan = StockControlPlan.fromRig(rig);
    final stock = List<int>.filled(128, 0)..[3] = 1;
    for (final p in plan.controls) {
      stock[StockControlPlan.presetIndex(p[0])!] = p[1];
    }
    stock.setRange(90, 99, plan.order.reversed);
    for (var a = 0; a < 11; a++) {
      for (var b = 0; b < 11; b++) {
        if (a != b) {
          for (var mode = 1; mode <= 7; mode++) {
            final config = defaultFx();
            config[0] = mode;
            config[16] = 8 - mode;
            config[1] = config[17] = 1;
            config[2] = a;
            config[18] = b;
            config[3] = 24;
            config[19] = 0;
            for (final i in [4, 5, 6, 7, 8, 9, 20, 21, 22, 23, 24, 25]) {
              config[i] = 37;
            }
            final next = StockControlPlan.readRig(rig, stock,
                identity: 'NAMLNK15', fx: config);
            expect(next.fxConfig(), config);
            expect(HybridRig.parse(next.encode()).fxConfig(), config);
            expect(StockControlPlan.fromRig(next, identity: 'NAMLNK15').order,
                plan.order.reversed.toList());
          }
        }
      }
    }
  });
  test(
      'USB FX writes validate echoed config, active preset, nonce and independent read',
      () async {
    var live = defaultFx();
    var active = 3;
    var corrupt = false;
    final requests = <Uint8List>[];
    final client = FxClient((q) async {
      requests.add(q);
      if (q[9] == 1) live = q.sublist(19, 51);
      return Uint8List.fromList([
        ...q.take(9),
        q[9] | 64,
        q[10],
        q[11],
        q[12],
        0,
        corrupt ? 2 : active,
        ...live,
        247
      ]);
    });
    final config = defaultFx()
      ..[1] = 1
      ..[3] = 19
      ..[18] = 9;
    expect(await client.write(config, active, 1854512385), config);
    expect(await client.read(), config);
    expect(requests.first.length, 52);
    expect(requests.first.sublist(14, 19), [1, 58, 38, 116, 6]);
    corrupt = true;
    await expectLater(
        client.write(config, active, 1854512385), throwsFormatException);
  });
  testWidgets(
      'FX A/B select, toggle, choose mode and expose editable controls below chain',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1200, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    final rig = HybridRig.initial();
    var edits = 0;
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: RigEditor(
                    rig: rig,
                    firmwareIdentity: 'NAMLNK14',
                    namControls: const Text('NAM'),
                    onChanged: () => edits++)))));
    for (final slot in ['fxa', 'fxb']) {
      await t.tap(find.byKey(ValueKey('block-$slot')));
      await t.pumpAndSettle();
      expect(
          t.getBottomLeft(find.byKey(const ValueKey('signal-chain'))).dy,
          lessThan(t
              .getTopLeft(find.byKey(const ValueKey('selected-controls')))
              .dy));
      await t.tap(find.byKey(ValueKey('bypass-$slot')));
      await t.pumpAndSettle();
      expect(rig.blocks.singleWhere((b) => b.slot == slot).enabled, true);
      await t.tap(find.byKey(ValueKey('choose-effect-$slot')));
      await t.pumpAndSettle();
      await t.enterText(
          find.byKey(const ValueKey('search-effects')), 'Tremolo');
      await t.pumpAndSettle();
      await t.tap(find.text('Tremolo').last);
      await t.pumpAndSettle();
      expect(rig.blocks.singleWhere((b) => b.slot == slot).effect!.name,
          'Tremolo');
      expect(find.text('Rate'), findsOneWidget);
      expect(find.text('Depth'), findsOneWidget);
    }
    expect(edits, greaterThanOrEqualTo(4));
  });
}
