import 'dart:convert';
import 'package:mighty_plug_manager/nam/stock/nam_tone.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/onboard_presets.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:nam_link/nam_link.dart';
import 'package:mighty_plug_manager/nam/stock/extra_fx.dart';
import 'connected_workflow_test.dart' show UsbFixture, capture;

// Emulates only the transport/storage boundary. The controller, model upload,
// effect plans, bank protocol and library serialization are production code.
class BankFixture extends UsbFixture {
  final headers = <int, Uint8List>{};
  final models = <int, LiteModel>{};
  final catalog = <LiteModel>[];
  List<int> fx = defaultFx();
  final savedFx = <int, List<int>>{};
  int active = 255, saves = 0, reads = 0, recalls = 0;
  bool failSave = false, badReadback = false;
  Future<void> Function()? beforeListen;
  BankFixture() {
    identity = 'NAMLNK10';
  }
  @override
  Map<String, dynamic> status() => {
        ...super.status(),
        'audioBuffer': {
          'samples': bufferSamples,
          'sampleRate': 48000,
          'processingSamples': 8,
          'global': [
            'NAMLNK18',
            'NAMLNK19',
            'NAMLNK20',
            'NAMLNK21',
            'NAMLNK22',
            'NAMLNK23',
            'NAMLNK24',
            'NAMLNK25',
            'NAMLNK26'
          ].contains(identity),
          'storageError': 0
        },
        'presetBank': {
          'active': active,
          'mask': headers.keys.fold<int>(0, (a, b) => a | (1 << b)),
          'slots': 7
        },
      };
  Future<void> button(int slot) async {
    final h = headers[slot]!;
    active = slot;
    fx = List<int>.from(savedFx[slot] ?? defaultFx());
    receiver = SimulatedPlug();
    await TransferClient(receiver).upload(models[slot]!);
    preset.setAll(0, h.sublist(128));
    if (![
      'NAMLNK18',
      'NAMLNK19',
      'NAMLNK20',
      'NAMLNK21',
      'NAMLNK22',
      'NAMLNK23',
      'NAMLNK24',
      'NAMLNK25',
      'NAMLNK26'
    ].contains(identity)) {
      bufferSamples = ByteData.sublistView(h).getUint32(24, Endian.little);
    }
    listening = true;
  }

  @override
  Future<dynamic> call(MethodCall c) async {
    if (c.method == 'exchangeFxFrame') {
      final q = (c.arguments as Map)['frame'] as Uint8List;
      var error = 0;
      if (q[7] == 86) {
        if (q[9] == 1) {
          final crc = List.generate(5, (i) => q[14 + i] << (7 * i))
              .fold<int>(0, (a, b) => a | b);
          expectSync(crc, crc32(receiver.activeSlot!));
          expectSync(q[10], active == 255 ? 127 : active);
          final controls = readNamTone(preset);
          preset.setRange(27, 33, controls);
          preset[33] = 78;
          preset[34] = 2;
          preset[35] = q[19];
        }
        return Uint8List.fromList([
          ...q.take(9),
          q[9] | 64,
          ...q.sublist(10, 13),
          0,
          active == 255 ? 127 : active,
          preset[33] == 78 && preset[34] == 2 ? preset[35] : 48,
          247
        ]);
      }
      if (q[7] == 71) {
        expectSync(
            [
              'NAMLNK21',
              'NAMLNK22',
              'NAMLNK23',
              'NAMLNK24',
              'NAMLNK25',
              'NAMLNK26'
            ].contains(identity),
            true);
        if (q[9] == 1) {
          final crc = List.generate(5, (i) => q[14 + i] << (7 * i))
              .fold<int>(0, (a, b) => a | b);
          expectSync(crc, crc32(receiver.activeSlot!));
          expectSync(q[10], active == 255 ? 127 : active);
          preset.setRange(27, 33, q.sublist(19, 25));
          preset[33] = 78;
          if (preset[34] != 2) preset[34] = 1;
        }
        return Uint8List.fromList([
          ...q.take(9),
          q[9] | 64,
          ...q.sublist(10, 13),
          0,
          active == 255 ? 127 : active,
          ...readNamTone(preset),
          247
        ]);
      }
      if (q[9] == 1) {
        final model = List.generate(5, (i) => q[14 + i] << (7 * i))
            .fold<int>(0, (a, b) => a | b);
        if (q[10] != (active == 255 ? 127 : active) ||
            model !=
                (receiver.activeSlot == null
                    ? 0
                    : crc32(receiver.activeSlot!))) {
          error = 2;
        } else {
          fx = q.sublist(19, 51);
        }
      }
      return Uint8List.fromList([
        ...q.take(9),
        q[9] | 64,
        q[10],
        q[11],
        q[12],
        error,
        active == 255 ? 127 : active,
        ...(q[9] == 2 ? savedFx[q[10]] ?? defaultFx() : fx),
        247
      ]);
    }
    if (c.method == 'setListening' && (c.arguments as Map)['enabled'] == true) {
      await beforeListen?.call();
    }
    if (c.method != 'exchangePresetFrame') return super.call(c);
    final raw = (c.arguments as Map)['frame'] as Uint8List;
    final request = ByteData.sublistView(raw), op = raw[5], slot = raw[6];
    expectSync(request.getUint32(raw.length - 4, Endian.little),
        crc32(raw.sublist(0, raw.length - 4)));
    int error = 0;
    if (op == 2) {
      saves++;
      if (failSave) {
        error = 3;
      } else {
        expectSync(
            request.getUint32(16, Endian.little), crc32(receiver.activeSlot!));
        expectSync(request.getUint32(20, Endian.little), crc32(preset));
        final h = Uint8List(256), w = ByteData.sublistView(h);
        w.setUint32(0, 0x3142504e, Endian.little);
        w.setUint32(4, 1, Endian.little);
        w.setUint32(8, slot, Endian.little);
        w.setUint32(
            12,
            headers.containsKey(slot)
                ? ByteData.sublistView(headers[slot]!)
                        .getUint32(12, Endian.little) +
                    1
                : 1,
            Endian.little);
        w.setUint32(16, request.getUint32(16, Endian.little), Endian.little);
        w.setUint32(20, request.getUint32(24, Endian.little), Endian.little);
        w.setUint32(24, request.getUint32(28, Endian.little), Endian.little);
        h.setRange(32, 128, raw.sublist(32, 128));
        h.setRange(128, 256, preset);
        headers[slot] = h;
        savedFx[slot] = List<int>.from(fx);
        models[slot] = catalog
            .singleWhere((m) => m.checksum == crc32(receiver.activeSlot!));
        active = slot;
        if (![
          'NAMLNK18',
          'NAMLNK19',
          'NAMLNK20',
          'NAMLNK21',
          'NAMLNK22',
          'NAMLNK23',
          'NAMLNK24',
          'NAMLNK25',
          'NAMLNK26'
        ].contains(identity)) listening = false;
      }
    } else if (op == 3) {
      recalls++;
      await button(slot);
    } else {
      reads++;
    }
    final reply = Uint8List(276), w = ByteData.sublistView(reply);
    reply.setRange(0, 16, raw.sublist(0, 16));
    reply[5] = op | 128;
    reply[7] = error;
    w.setUint16(12, 256, Endian.little);
    reply[14] = active;
    reply[15] = headers.keys.fold<int>(0, (a, b) => a | (1 << b));
    if (headers.containsKey(slot)) reply.setRange(16, 272, headers[slot]!);
    if ([
          'NAMLNK18',
          'NAMLNK19',
          'NAMLNK20',
          'NAMLNK21',
          'NAMLNK22',
          'NAMLNK23',
          'NAMLNK24',
          'NAMLNK25',
          'NAMLNK26'
        ].contains(identity) &&
        headers.containsKey(slot)) {
      w.setUint32(16 + 24, bufferSamples, Endian.little);
    }
    if (badReadback && op == 1 && saves > 0) reply[80] ^= 1;
    w.setUint32(272, crc32(reply.sublist(0, 272)), Endian.little);
    return reply;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('seven independent captures, names and effects survive serialization',
      () {
    final bank = OnboardPresets();
    for (var i = 0; i < 7; i++) {
      bank.selected = i;
      final rig = HybridRig.initial()
        ..name = 'Preset $i'
        ..modelSha256 = capture('Capture $i', i + 1).sha256Hex;
      rig.blocks.first.enabled = i.isEven;
      bank.edit(rig);
    }
    final restored =
        OnboardPresets.parse(jsonDecode(jsonEncode(bank.toJson())));
    expect(restored.slots.map((r) => r.modelSha256).toSet().length, 7);
    for (var i = 0; i < 7; i++) {
      expect(restored.slots[i].name, 'Preset $i');
      expect(restored.slots[i].blocks.first.enabled, i.isEven);
      expect(restored.dirty[i], true);
    }
    restored.slots[0].name = 'Edited';
    expect(restored.slots[1].name, 'Preset 1');
    expect(presetColorNames,
        ['Green', 'Orange', 'Red', 'Blue', 'Cyan', 'Pink', 'Lilac']);
    expect(presetColors.toSet().length, 7);
    expect(() => OnboardPresets.parse({'schema': 1}), throwsFormatException);
  });

  test('preset protocol rejects wrong nonce, CRC, slot and incomplete reply',
      () async {
    final usb = BankFixture(), a = capture('One', 1);
    usb.catalog.add(a);
    for (final change in [0, 8, 272]) {
      final client = PresetClient((raw) async {
        final r =
            await usb.call(MethodCall('exchangePresetFrame', {'frame': raw}))
                as Uint8List;
        r[change] ^= 1;
        if (change != 272) {
          ByteData.sublistView(r)
              .setUint32(272, crc32(r.sublist(0, 272)), Endian.little);
        }
        return r;
      });
      await expectLater(client.read(0), throwsFormatException);
    }
    await expectLater(
        PresetClient((_) async => Uint8List(0)).read(0), throwsFormatException);
    await expectLater(
        PresetClient((_) async => Uint8List(0)).read(7), throwsFormatException);
    final client = PresetClient((_) async => throw StateError('must not send'));
    expect(() => client.save(0, a, usb.preset, 'x' * 64, 8),
        throwsFormatException);
    expect(
        () => client.save(0, a, usb.preset, 'Fine', 4), throwsFormatException);
  });

  late BankFixture usb;
  setUp(() {
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    usb = BankFixture();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
            const MethodChannel('nam_plug/device'), usb.call);
  });
  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });
  Future<dynamic> start(WidgetTester t) async {
    await t.binding.setSurfaceSize(const Size(1120, 1100));
    addTearDown(() async {
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      await t.binding.setSurfaceSize(null);
    });
    await t.pumpWidget(const NamLabApp());
    await t.pumpAndSettle();
    return t.state(find.byType(NamHome));
  }

  Future<void> work(
      WidgetTester t, dynamic home, Future<void> Function() job) async {
    var complete = false;
    final task = home.perform(job).whenComplete(() => complete = true);
    for (var i = 0; i < 100 && !complete; i++) {
      await t.pump(const Duration(milliseconds: 100));
    }
    expect(complete, true, reason: home.status);
    await task;
    await t.pumpAndSettle();
  }

  Future<void> save(WidgetTester t, dynamic home, int slot, LiteModel model,
      String name) async {
    await work(t, home, () async {
      await home.selectOnboard(slot);
      await home.selectCapture(model);
      home.rig.name = name;
      await home.saveOnboard();
    });
    expect(home.onboard.dirty[slot], false, reason: home.status);
  }

  for (final firmware in ['NAMLNK23', 'NAMLNK25', 'NAMLNK26']) {
    for (final playing in [false, true]) {
      testWidgets('$firmware startup and refresh preserve playback=$playing',
          (t) async {
        usb.identity = firmware;
        final a = capture('Local fallback', 1);
        usb.catalog.add(a);
        usb.seed([a], selected: a);
        usb.listening = playing;
        final dynamic home = await start(t);
        expect(home.hardware['identity'], firmware);
        await work(t, home, () => home.refreshConnection());
        expect(usb.listenCommands, isEmpty);
        expect(usb.listening, playing);
        expect(usb.transfers, 0);
        expect(usb.saves, 0);
        expect(t.takeException(), isNull);
        await t.pumpWidget(const SizedBox.shrink());
        await t.pump();
        debugDefaultTargetPlatformOverride = null;
      });
    }
  }

  for (final firmware in [
    'NAMLNK21',
    'NAMLNK22',
    'NAMLNK23',
    'NAMLNK24',
    'NAMLNK25',
    'NAMLNK26'
  ])
    testWidgets(
        '$firmware direct color selection jumps to saved slot and USB gain stays independent',
        (t) async {
      usb.identity = firmware;
      final a = capture('Green', 1), b = capture('Pink', .5);
      usb.catalog.addAll([a, b]);
      usb.seed([a, b], selected: a);
      final dynamic home = await start(t);
      await save(t, home, 0, a, 'Green');
      await save(t, home, 5, b, 'Pink');
      for (final slot in [0, 5, 0, 5]) {
        await t.ensureVisible(find.byKey(ValueKey('preset-color-$slot')));
        await t.tap(find.byKey(ValueKey('preset-color-$slot')));
        for (var i = 0; i < 40; i++) {
          await t.pump(const Duration(milliseconds: 100));
          if (!home.busy) break;
        }
        await t.pumpAndSettle();
        expect(usb.active, slot);
        expect(home.onboard.selected, slot);
        expect(crc32(usb.receiver.activeSlot!),
            slot == 0 ? a.checksum : b.checksum);
      }
      final master = usb.preset[84], muting = usb.listenCommands.length;
      t
          .widget<Slider>(find.byKey(const ValueKey('usb-record-gain')))
          .onChanged!(60);
      await t.pump(const Duration(milliseconds: 400));
      await t.pumpAndSettle();
      expect(usb.preset[35], 60);
      expect(usb.preset[84], master);
      expect(usb.listenCommands.length, muting);
      await work(t, home, () async {
        await home.saveOnboard();
      });
      expect(usb.headers[5]![128 + 35], 60);
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      debugDefaultTargetPlatformOverride = null;
    });

  for (final firmware in [
    'NAMLNK21',
    'NAMLNK22',
    'NAMLNK23',
    'NAMLNK24',
    'NAMLNK25',
    'NAMLNK26'
  ])
    testWidgets(
        '$firmware NAM sliders apply live, retain bypass and save/recall',
        (t) async {
      usb.identity = firmware;
      final a = capture('NAM controls', 1);
      usb.catalog.add(a);
      usb.seed([a], selected: a);
      final dynamic home = await start(t);
      await save(t, home, 0, a, 'NAM controls');
      final saves = usb.saves, muting = usb.listenCommands.length;
      final slider = find.byKey(const ValueKey('nam-tone-0'));
      expect(slider, findsOneWidget);
      t.widget<Slider>(slider).onChanged!(54);
      await t.pump(const Duration(milliseconds: 400));
      await t.pumpAndSettle();
      expect(readNamTone(usb.preset)[0], 54, reason: home.status);
      expect(usb.saves, saves);
      expect(usb.listenCommands.length, muting);
      expect(usb.listening, true);
      await work(t, home, () async {
        await home.saveOnboard();
      });
      expect(readNamTone(usb.headers[0]!.sublist(128))[0], 54);
      await work(t, home, () async {
        await usb.button(0);
        await home.inspect(1);
      });
      expect(home.rig.namTone[0], 54);
      expect(find.byKey(const ValueKey('add-block')), findsOneWidget);
      await t.ensureVisible(find.byKey(const ValueKey('toggle-nam')));
      await t.tap(find.byKey(const ValueKey('toggle-nam')));
      await t.pump(const Duration(milliseconds: 400));
      await t.pumpAndSettle();
      expect(find.byKey(const ValueKey('block-nam')), findsOneWidget);
      expect(usb.preset[3] & 64, 64, reason: home.status);
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      debugDefaultTargetPlatformOverride = null;
    });

  testWidgets('buffer resume rejects a concurrent capture change', (t) async {
    usb.identity = 'NAMLNK17';
    final a = capture('First', 1), b = capture('Changed', 2);
    usb.catalog.addAll([a, b]);
    usb.seed([a], selected: a);
    final dynamic home = await start(t);
    await save(t, home, 0, a, 'First');
    usb.listening = true;
    usb.beforeListen = () async => TransferClient(usb.receiver).upload(b);
    await work(t, home, () => home.setOutputBuffer(16));
    expect(usb.listening, false);
    expect(home.status, contains('Playback could not be confirmed'));
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  for (final identity in [
    'NAMLNK18',
    'NAMLNK19',
    'NAMLNK20',
    'NAMLNK21',
    'NAMLNK22',
    'NAMLNK23',
    'NAMLNK24',
    'NAMLNK25',
    'NAMLNK26'
  ])
    for (final playing in [false, true]) {
      testWidgets(
          '$identity global buffer preserves playback=$playing; saving resumes playback',
          (t) async {
        usb.identity = identity;
        final a = capture('Fender', 1);
        usb.catalog.add(a);
        usb.seed([a], selected: a);
        final dynamic home = await start(t);
        await save(t, home, 0, a, 'Green');
        usb.listening = playing;
        final saves = usb.saves;
        final stored = List<int>.from(usb.headers[0]!);
        await work(t, home, () => home.setOutputBuffer(16));
        expect(usb.listening, playing);
        expect(home.hardware['audioBuffer']['global'], true);
        expect(home.status, contains('saved globally'));
        expect(usb.saves, saves);
        expect(
            usb.headers[0], stored); // No preset overwrite for a global change.
        await usb.button(0);
        expect(usb.bufferSamples, 16);
        usb.listening = playing;
        await work(t, home, () => home.saveOnboard());
        expect(usb.listening, true);
        expect(home.onboard.dirty[0], false, reason: home.status);
        expect(home.hardware['audioBuffer']['samples'], 16);
        await work(t, home, () => home.setOutputBuffer(8));
        expect(usb.listening, true);
        expect(usb.bufferSamples, 8);
        expect(t.takeException(), isNull);
        await t.pumpWidget(const SizedBox.shrink());
        await t.pump();
        debugDefaultTargetPlatformOverride = null;
      });
    }

  for (final identity in [
    'NAMLNK10',
    'NAMLNK11',
    'NAMLNK12',
    'NAMLNK14',
    'NAMLNK15',
    'NAMLNK16',
    'NAMLNK17',
    'NAMLNK18',
    'NAMLNK19',
    'NAMLNK20'
  ]) {
    testWidgets(
        '$identity: save colored captures, button recall, reconnect and app restart',
        (t) async {
      usb.identity = identity;
      final a = capture('Fender', 1), b = capture('Marshall', 2);
      usb.catalog.addAll([a, b]);
      usb.seed([a, b]);
      dynamic home = await start(t);
      for (var i = 0; i < 7; i++) {
        expect(find.byKey(ValueKey('preset-color-$i')), findsOneWidget);
      }
      await save(t, home, 0, a, 'Clean Fender');
      final firstFx = List<int>.from(usb.preset);
      await work(t, home, () async {
        await home.selectOnboard(3);
        await home.selectCapture(b);
        home.rig.blocks.first.enabled = !home.rig.blocks.first.enabled;
        home.rig.name = 'Crunch Marshall';
        if (supportsExtraFx(identity)) {
          final extra = home.rig.blocks.singleWhere((b) => b.slot == 'fxa');
          extra.enabled = true;
          extra.choice = 2;
          extra.effect.parameters.first.value = 71.0;
          home.rig.reorder(home.rig.blocks.indexOf(extra), 9);
        }
        await home.saveOnboard();
      });
      expect(home.onboard.dirty[3], false, reason: home.status);
      expect(usb.models[0]!.sha256Hex, a.sha256Hex);
      expect(usb.models[3]!.sha256Hex, b.sha256Hex);
      expect(usb.saves, 2);
      expect(usb.listening, true);
      if (supportsExtraFx(identity)) {
        expect(usb.savedFx[3]![0], 3);
        expect(usb.savedFx[3]![1], 1);
        expect(usb.savedFx[3]![2], 9);
        expect(usb.savedFx[3]![5], 71);
      }
      final uploads = usb.transfers;
      await usb.button(0);
      await t.pump(const Duration(seconds: 3));
      await t.pumpAndSettle();
      expect(home.onboard.selected, 0);
      expect(home.rig.modelSha256, a.sha256Hex);
      expect(usb.preset, firstFx);
      if (supportsExtraFx(identity)) {
        expect(home.rig.fxConfig(), usb.savedFx[0]);
      }
      expect(usb.transfers, uploads,
          reason: 'Reading an onboard recall must not upload over it');
      await work(t, home, () async {
        await home.selectOnboard(3);
      });
      expect(home.rig.modelSha256, b.sha256Hex);
      expect(usb.recalls, 1);
      if (supportsExtraFx(identity)) {
        expect(home.rig.fxConfig(), usb.savedFx[3]);
      }
      usb.connected = false;
      await t.pump(const Duration(seconds: 3));
      await t.pumpAndSettle();
      await usb.button(0);
      usb.connected = true;
      await t.pump(const Duration(seconds: 3));
      await t.pumpAndSettle();
      expect(home.rig.modelSha256, a.sha256Hex);
      expect(usb.transfers, uploads);
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      await t.pumpWidget(const NamLabApp());
      await t.pumpAndSettle();
      home = t.state(find.byType(NamHome));
      expect(home.onboard.slots[3].name, 'Crunch Marshall');
      expect(home.onboard.slots[0].modelSha256, a.sha256Hex);
      expect(home.captures.favorites.length, 2);
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      debugDefaultTargetPlatformOverride = null;
    });
  }

  testWidgets(
      'master volume edits a saved onboard capture missing from the Mac library',
      (t) async {
    final a = capture('Fender on plug', .7);
    usb.catalog.add(a);
    await TransferClient(usb.receiver).upload(a);
    final client = PresetClient((raw) async => await usb
        .call(MethodCall('exchangePresetFrame', {'frame': raw})) as Uint8List);
    await client.save(2, a, usb.preset, 'Red Fender Spring', 8);
    usb.seed([]);
    final home = await start(t);
    expect(home.model, isNull);
    expect(home.loadedAndHealthy, true);
    expect(home.rig.modelSha256, a.sha256Hex);
    expect(home.onboard.selected, 2);
    expect(find.text('A2 Lite · 48 kHz · Stored on plug'), findsOneWidget);
    expect(find.text('Loaded on plug'), findsOneWidget);
    final uploads = usb.transfers, saves = usb.saves;
    final volume = find.byKey(const ValueKey('master-volume'));
    await t.ensureVisible(volume);
    expect(t.widget<Slider>(volume).onChanged, isNotNull);
    t.widget<Slider>(volume).onChanged!(27);
    await t.pump(const Duration(milliseconds: 300));
    await t.pumpAndSettle();
    expect(usb.preset[84], 27, reason: home.status);
    expect(find.text('Mute plug'), findsNothing);
    expect(find.text('Listen on plug'), findsNothing);
    expect(usb.transfers, uploads);
    expect(usb.saves, saves);
    expect(home.captures.captures, isEmpty);
    expect(home.captures.favorites, isEmpty);

    // A different unsent draft must not authorize the onboard capture.
    home.rig.modelSha256 = capture('Different unsent draft', .8).sha256Hex;
    await work(t, home, () async => home.persist());
    expect(home.loadedAndHealthy, false);
    await expectLater(home.setListening(true), throwsStateError);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('onboard listening rechecks capture and faults before accepting',
      (t) async {
    final a = capture('Saved Fender', .7), b = capture('Changed capture', .8);
    usb.catalog.add(a);
    await TransferClient(usb.receiver).upload(a);
    final client = PresetClient((raw) async => await usb
        .call(MethodCall('exchangePresetFrame', {'frame': raw})) as Uint8List);
    await client.save(2, a, usb.preset, 'Red Fender', 8);
    usb.seed([]);
    final home = await start(t);
    usb.beforeListen = () async => TransferClient(usb.receiver).upload(b);
    await work(t, home, () => home.setListening(true));
    expect(usb.listenCommands, [true, false]);
    expect(usb.listening, false);
    expect(home.status, contains('capture changed'));

    await TransferClient(usb.receiver).upload(a);
    usb.beforeListen = () async {
      usb.fault = true;
    };
    await work(t, home, home.refreshConnection);
    expect(home.loadedAndHealthy, true);
    await work(t, home, () => home.setListening(true));
    expect(usb.listenCommands, [true, false, true, false]);
    expect(usb.listening, false);
    expect(home.loadedAndHealthy, false);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'failed save and reconnect keep edited draft and previous onboard capture',
      (t) async {
    final a = capture('First', 1), b = capture('Second', 2);
    usb.catalog.addAll([a, b]);
    usb.seed([a, b]);
    final home = await start(t);
    await save(t, home, 0, a, 'Saved');
    usb.failSave = true;
    await work(t, home, () async {
      await home.selectCapture(b);
      home.rig.name = 'Unsaved';
      await home.persist();
      await home.saveOnboard();
    });
    expect(home.onboard.dirty[0], true);
    expect(usb.models[0]!.sha256Hex, a.sha256Hex);
    usb.connected = false;
    await t.pump(const Duration(seconds: 3));
    await t.pumpAndSettle();
    await usb.button(0);
    usb.connected = true;
    await t.pump(const Duration(seconds: 3));
    await t.pumpAndSettle();
    expect(home.rig.modelSha256, b.sha256Hex);
    expect(home.rig.name, 'Unsaved');
    expect(home.onboard.dirty[0], true);
    expect(home.status, contains('Unsaved edits'));
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('mismatched independent readback never marks preset saved',
      (t) async {
    final a = capture('First', 1);
    usb.catalog.add(a);
    usb.seed([a]);
    final home = await start(t);
    usb.badReadback = true;
    await work(t, home, () async {
      await home.selectCapture(a);
      await home.saveOnboard();
    });
    expect(home.onboard.dirty[0], true);
    expect(home.onboard.generations[0], 0);
    expect(home.status, contains('readback did not match'));
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'older firmware can edit all seven drafts but cannot save onboard',
      (t) async {
    usb.identity = 'NAMLNK08';
    final home = await start(t);
    final button = t.widget<FilledButton>(
        find.byKey(const ValueKey('save-onboard-preset')));
    expect(button.onPressed, isNull);
    await work(t, home, () async {
      await home.selectOnboard(6);
    });
    expect(home.onboard.selected, 6);
    expect(usb.saves, 0);
    expect(usb.reads, 0);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });
}
