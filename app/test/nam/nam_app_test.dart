import 'dart:convert';
import 'package:crypto/crypto.dart' as crypto;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/catalog.dart';
import 'package:nam_link/nam_link.dart';
import 'tone_browser_test.dart' show CatalogFixture;

void main() {
  String? library, clipboard;
  final calls = <String>[];
  var link = false, fault = false, chainFirmware = false, listening = false;
  var modelMismatch = false;
  var chainIdentity = 'NAMLNK02';
  Map? lastControls;
  var receiver = SimulatedPlug();
  setUp(() {
    library = null;
    link = fault = chainFirmware = listening = false;
    modelMismatch = false;
    lastControls = null;
    chainIdentity = 'NAMLNK02';
    receiver = SimulatedPlug();
    clipboard = null;
    calls.clear();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('nam_plug/device'),
            (call) async {
      calls.add(call.method);
      if (call.method == 'loadLibrary') return library;
      if (call.method == 'saveLibrary') {
        library = call.arguments as String;
        return null;
      }
      if (call.method == 'devices') {
        return [
          {'source': 1, 'name': 'MIGHTY PLUG PRO USB'}
        ];
      }
      if (call.method == 'exchangeModelFrame') {
        listening = false;
        modelMismatch = false;
        expect(link, true);
        expect((call.arguments as Map)['source'], 1);
        return receiver.exchange((call.arguments as Map)['frame'] as Uint8List);
      }
      if (call.method == 'inspect' || call.method == 'setListening') {
        if (call.method == 'setListening') {
          expect(['NAMLNK07', 'NAMLNK08', 'NAMLNK09'], contains(chainIdentity));
          if ((call.arguments as Map)["enabled"] == true) {
            expect(fault, false);
            expect(receiver.activeSlot, isNotNull);
          }
          listening = (call.arguments as Map)['enabled'] as bool;
        }
        if (link) {
          final slot = receiver.activeSlot;
          return {
            'identity': chainFirmware ? chainIdentity : 'NAMLNK01',
            'compatible': true,
            'modelTransfer': true,
            'stockChain': chainFirmware,
            if (['NAMLNK07', 'NAMLNK08', 'NAMLNK09']
                .contains(chainIdentity)) ...{
              'listeningSupported': true,
              'listening': {'enabled': listening, 'settling': false},
            },
            if (['NAMLNK06', 'NAMLNK07', 'NAMLNK08', 'NAMLNK09']
                .contains(chainIdentity))
              'irqTiming': {
                'usable': !fault,
                'maximumCycles': 45678,
                'accepted': 25,
                'rejected': fault ? 1 : 0,
              },
            'words': [
              0x4e4c4b31,
              1,
              1,
              100,
              fault ? 1 : 0,
              slot == null ? 0 : crc32(slot) ^ (modelMismatch ? 1 : 0),
              slot == null ? 0 : 1,
              calls.length * 10,
              85,
              slot == null || fault ? 0 : 1,
              0,
              0
            ]
          };
        }
        return {
          'identity': 'NAMA2I01',
          'compatible': true,
          'words': List.filled(62, 0)
        };
      }
      if (call.method == 'applyStockControls') {
        lastControls = call.arguments as Map;
        expect(lastControls!['source'], 1);
        return {'controlsVerified': true, 'stockChain': chainFirmware};
      }
      if (call.method == 'setCabinetBypassed') {
        expect((call.arguments as Map)['source'], 1);
        expect((call.arguments as Map)['bypassed'], true);
        expect(receiver.activeSlot, isNotNull);
        expect(listening, false);
        return {'controlsVerified': true};
      }
      return null;
    });
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        clipboard = (call.arguments as Map)['text'];
      }
      return null;
    });
  });
  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });
  for (final identity in [
    'NAMLNK01',
    'NAMLNK02',
    'NAMLNK03',
    'NAMLNK04',
    'NAMLNK05',
    'NAMLNK06',
    'NAMLNK07',
    'NAMLNK08',
    'NAMLNK09'
  ]) {
    final stockChain = identity != 'NAMLNK01';
    testWidgets('NAM bypass is sent only for chain firmware: $identity',
        (t) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
      await t.binding.setSurfaceSize(const Size(1120, 950));
      addTearDown(() => t.binding.setSurfaceSize(null));
      link = true;
      chainFirmware = stockChain;
      chainIdentity = identity;
      await t.pumpWidget(const NamLabApp(autoConnect: false));
      await t.pumpAndSettle();
      await t.tap(find.text('Plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('Find plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('MIGHTY PLUG PRO USB'));
      await t.pumpAndSettle();
      if (identity == 'NAMLNK06') {
        expect(find.text('Audio callback: peak 45678 raw counter cycles'),
            findsOneWidget);
      }
      await t.tap(find.text('Signal chain'));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('toggle-nam')));
      await t.pumpAndSettle();
      final send = find.byKey(const ValueKey('send-stock-controls'));
      await t.ensureVisible(send);
      await t.pumpAndSettle();
      await t.tap(send);
      await t.pumpAndSettle();
      expect(lastControls, isNotNull);
      expect(lastControls!.containsKey('namEnabled'), stockChain);
      if (stockChain) expect(lastControls!['namEnabled'], false);
      expect((lastControls!['controls'] as List).any((c) => c[0] == 3), false);
      expect((lastControls!['order'] as List).toSet(),
          {1, 2, 3, 4, 5, 6, 7, 8, 9});
      final text = (t.state(find.byType(NamHome)) as dynamic).status as String;
      expect(
          text,
          contains(
              stockChain ? 'full chain is configured' : 'not processing yet'));
      debugDefaultTargetPlatformOverride = null;
    });
  }
  for (final listenIdentity in ['NAMLNK07', 'NAMLNK08', 'NAMLNK09']) {
    testWidgets(
        'listening requires explicit first click and verified model reload resumes: $listenIdentity',
        (t) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
      link = chainFirmware = true;
      chainIdentity = listenIdentity;
      await t.binding.setSurfaceSize(const Size(1120, 1100));
      addTearDown(() => t.binding.setSurfaceSize(null));
      final capture = LiteModel.fixture();
      final rig = HybridRig.initial()..modelSha256 = capture.sha256Hex;
      library = jsonEncode({
        'schema': 'nam-plug-library-2',
        'active': rig.encode(),
        'presets': {},
        'models': (ModelLibrary()..add(capture)).toJson(),
        'tone_client_id': ''
      });
      await t.pumpWidget(const NamLabApp(autoConnect: false));
      await t.pumpAndSettle();
      await t.tap(find.text('Plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('Find plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('MIGHTY PLUG PRO USB'));
      await t.pumpAndSettle();
      await t.tap(find.text('Signal chain'));
      await t.pumpAndSettle();
      expect(
          t
              .widget<FilledButton>(
                  find.byKey(const ValueKey('plug-listening')))
              .onPressed,
          isNull);
      await t.tap(find.byKey(const ValueKey('send-model')));
      await t.pumpAndSettle();
      expect(listening, false);
      expect(find.text('Loaded on plug'), findsOneWidget);
      // A connected, healthy plug can still hold a different capture.
      modelMismatch = true;
      await t.tap(find.text('Plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('MIGHTY PLUG PRO USB'));
      await t.pumpAndSettle();
      await t.tap(find.text('Signal chain'));
      await t.pumpAndSettle();
      expect(find.text('Selected on this Mac'), findsOneWidget);
      expect(
          t
              .widget<FilledButton>(
                  find.byKey(const ValueKey('plug-listening')))
              .onPressed,
          isNull);
      await t.tap(find.byKey(const ValueKey('send-model')));
      await t.pumpAndSettle();
      expect(find.text('Loaded on plug'), findsOneWidget);
      expect(find.text('Listen on plug'), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('plug-listening')));
      await t.pumpAndSettle();
      expect(listening, true);
      expect(find.text('Mute plug'), findsOneWidget);
      await t.ensureVisible(find.byKey(const ValueKey('send-stock-controls')));
      await t.ensureVisible(find.byKey(const ValueKey('send-stock-controls')));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('send-stock-controls')));
      await t.pumpAndSettle();
      expect(listening, true);
      await t.ensureVisible(find.byKey(const ValueKey('plug-listening')));
      await t.tap(find.byKey(const ValueKey('plug-listening')));
      await t.pumpAndSettle();
      expect(listening, false);
      await t.tap(find.byKey(const ValueKey('plug-listening')));
      await t.pumpAndSettle();
      expect(listening, true);
      await t.ensureVisible(find.byKey(const ValueKey('send-model')));
      await t.tap(find.byKey(const ValueKey('send-model')));
      await t.pumpAndSettle();
      expect(listening, true);
      expect(find.text('Mute plug'), findsOneWidget);
      expect(t.takeException(), isNull);
      debugDefaultTargetPlatformOverride = null;
    });
  }
  for (final gear in ['amp-cab', 'amp']) {
    testWidgets(
        'capture selection $gear applies only the required cabinet bypass',
        (t) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
      link = chainFirmware = true;
      chainIdentity = 'NAMLNK07';
      final api = CatalogFixture()..captureGear = gear;
      await t.binding.setSurfaceSize(const Size(1120, 1100));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(NamLabApp(autoConnect: false, toneApi: api));
      await t.pumpAndSettle();
      await t.tap(find.text('Plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('Find plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('MIGHTY PLUG PRO USB'));
      await t.pumpAndSettle();
      await t.tap(find.text('Signal chain'));
      await t.pumpAndSettle();
      await t.tap(find.text('Explore TONE3000'));
      // The parent remains busy while its modal is open.
      await t.pump();
      await t.pump(const Duration(seconds: 1));
      await t.ensureVisible(find.text('Test amp'));
      await t.tap(find.text('Test amp'));
      await t.pump();
      await t.pump(const Duration(seconds: 1));
      await t.ensureVisible(find.text('Test Lite capture'));
      await t.tap(find.text('Test Lite capture'));
      await t.pumpAndSettle();
      final selected = HybridRig.parse(jsonDecode(library!)['active']);
      expect(selected.blocks.singleWhere((b) => b.slot == 'cab').enabled,
          gear == 'amp');
      expect(selected.blocks.length, 11);
      expect(calls.where((c) => c == 'setCabinetBypassed').length,
          gear == 'amp-cab' ? 1 : 0);
      expect(lastControls!['namEnabled'], true);
      expect(listening, false);
      expect(find.text('Loaded on plug'), findsOneWidget);
      expect(t.takeException(), isNull);
      debugDefaultTargetPlatformOverride = null;
    });
  }
  testWidgets('rejected timing is not presented as a valid performance result',
      (t) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    await t.binding.setSurfaceSize(const Size(1120, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    link = chainFirmware = fault = true;
    chainIdentity = 'NAMLNK06';
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    await t.tap(find.text('Plug'));
    await t.pumpAndSettle();
    await t.tap(find.text('Find plug'));
    await t.pumpAndSettle();
    await t.tap(find.text('MIGHTY PLUG PRO USB'));
    await t.pumpAndSettle();
    expect(find.text('Audio callback timing: no clean measurement available'),
        findsOneWidget);
    expect(find.textContaining('peak 45678'), findsNothing);
    debugDefaultTargetPlatformOverride = null;
  });
  testWidgets('bundled app registration survives old empty settings',
      (t) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    await t.binding.setSurfaceSize(const Size(1120, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    library = jsonEncode({
      'schema': 'nam-plug-library-2',
      'active': HybridRig.initial().encode(),
      'presets': <String, String>{},
      'models': ModelLibrary().toJson(),
      'tone_client_id': ''
    });
    await t.pumpWidget(const NamLabApp(
        autoConnect: false, bundledToneClientId: 't3k_pub_bundled_test'));
    await t.pumpAndSettle();
    await t.tap(find.text('Settings'));
    await t.pumpAndSettle();
    expect(find.text('Developer setup'), findsNothing);
    expect(find.text('Publishable client ID'), findsNothing);
    expect(find.textContaining('Sign-in is waiting'), findsNothing);
    await t.ensureVisible(find.text('Open TONE3000'));
    await t.pumpAndSettle();
    await t.tap(find.text('Open TONE3000'));
    // The parent shows a busy indicator until its modal browser closes.
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    expect(calls, contains('loadToneSession'));
    expect(find.text('Sign in to TONE3000'), findsOneWidget);
    expect(find.textContaining('not enabled in this build'), findsNothing);
    await t.tap(find.byTooltip('Close tone browser'));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Add silent test fixture'));
    await t.pumpAndSettle();
    await t.tap(find.text('Add silent test fixture'));
    await t.pumpAndSettle();
    expect(jsonDecode(library!)['tone_client_id'], 't3k_pub_bundled_test');
    expect(t.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
    debugDefaultTargetPlatformOverride = null;
  });
  test('all stock choices preserve defaults and choice-specific settings', () {
    final rig = HybridRig.initial();
    expect(rig.blocks.fold<int>(0, (n, b) => n + b.choices.length), 95);
    for (final b in rig.blocks) {
      expect(b.choices.map((e) => e.nuxIndex).toSet().length, b.choices.length);
      for (var n = 0; n < b.choices.length; n++) {
        b.choice = n;
        for (final p in b.effect!.parameters) {
          if (p.formatter is SwitchFormatter) {
            p.value =
                (p.formatter as SwitchFormatter).midiValues.last.toDouble();
          } else {
            p.value = p.formatter.min.toDouble();
          }
        }
        expect(HybridRig.parse(rig.encode()).encode(), rig.encode());
      }
    }
  });
  test(
      'hybrid presets reject duplicates, missing slots, bad types and bad ranges',
      () {
    final rig = HybridRig.initial();
    expect(HybridRig.parse(rig.encode()).encode(), rig.encode());
    for (final mutation in <void Function(Map<String, dynamic>)>[
      (j) => j['blocks'].removeLast(),
      (j) => j['blocks'][1] = j['blocks'][0],
      (j) => j['blocks'][0]['choice'] = 999,
      (j) => j['blocks'][0]['settings']['1'][0] = 1000,
      (j) => j['blocks'][0]['enabled'] = 1,
      (j) => j['model_sha256'] = 'invalid',
    ]) {
      final j = jsonDecode(rig.encode()) as Map<String, dynamic>;
      mutation(j);
      expect(() => HybridRig.parse(jsonEncode(j)), throwsFormatException);
    }
  });
  test(
      'offline favorites deduplicate, persist attribution and reject corrupt capture',
      () {
    final m = LiteModel.fixture(), lib = ModelLibrary();
    lib.add(m);
    lib.add(m);
    lib.toggleFavorite(m.sha256Hex);
    final next = ModelLibrary.parse(jsonDecode(jsonEncode(lib.toJson())));
    expect(next.captures.length, 1);
    expect(next.favorites, {m.sha256Hex});
    expect(next.captures.values.single.metadata['license'], 'CC0-1.0');
    final broken = m.toRecord();
    final bytes = m.slot..[100] ^= 1;
    broken['slot'] = base64Encode(bytes);
    expect(() => LiteModel.restore(broken), throwsFormatException);
    next.remove(m.sha256Hex);
    expect(next.favorites, isEmpty);
  });
  testWidgets(
      'Mac drag changes order, controls stay below, bypass and preset round-trip',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1120, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    final chain = find.byKey(const ValueKey('signal-chain'));
    expect(
        t.getBottomLeft(chain).dy,
        lessThan(
            t.getTopLeft(find.byKey(const ValueKey('selected-controls'))).dy));
    expect(find.text('NAM amplifier'), findsOneWidget);
    final start = t.getCenter(find.byKey(const ValueKey('drag-drive')));
    final gesture = await t.startGesture(start);
    await gesture.moveBy(const Offset(20, 0));
    await t.pump();
    await gesture.moveBy(const Offset(160, 0));
    await t.pump(const Duration(milliseconds: 600));
    await gesture.up();
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('bypass-drive')));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Share chain'));
    await t.pumpAndSettle();
    await t.tap(find.text('Share chain'));
    await t.pumpAndSettle();
    final rig = HybridRig.parse(clipboard!);
    expect(rig.blocks[6].slot, 'drive');
    expect(rig.blocks.singleWhere((b)=>b.slot=='drive').enabled, true);
    await t.ensureVisible(find.byTooltip('Save chain'));
    await t.tap(find.byTooltip('Save chain'));
    await t.pump(const Duration(milliseconds: 400));
    await t.tap(find.text('Save'));
    await t.pumpAndSettle();
    expect(jsonDecode(library!)['presets'].length, 1);
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    expect(find.text('Saved chains'), findsOneWidget);
    expect(t.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
  });
  testWidgets('effect types expose matching controls and no stock amp selector',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1120, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('block-drive')));
    await t.pumpAndSettle();
    expect(find.text('Sensitivity'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('choose-effect-drive')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const ValueKey('search-effects')), 'screamer');
    await t.pumpAndSettle();
    await t.tap(find.text('T Screamer').last);
    await t.pumpAndSettle();
    expect(find.text('Tone'), findsOneWidget);
    expect(t.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
    await t.tap(find.byKey(const ValueKey('block-nam')));
    await t.pumpAndSettle();
    expect(find.byType(DropdownButtonFormField<int>), findsNothing);
    expect(find.text('Explore TONE3000'), findsOneWidget);
  });
  testWidgets('long cabinet list scrolls inside a compact dismissible picker',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1120, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('block-cab')));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('choose-effect-cab')));
    await t.pumpAndSettle();
    final picker = find.byKey(const ValueKey('effect-picker'));
    expect(t.getSize(picker).height, lessThan(650));
    final close = find.byKey(const ValueKey('close-effect-picker'));
    final closePosition = t.getCenter(close);
    final list = find.byKey(const ValueKey('effect-options'));
    await t.drag(list, const Offset(0, -1600));
    await t.pumpAndSettle();
    expect(t.getCenter(close), closePosition);
    await t.tap(close);
    await t.pumpAndSettle();
    expect(picker, findsNothing);
    await t.tap(find.byKey(const ValueKey('choose-effect-cab')));
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.escape);
    await t.pumpAndSettle();
    expect(picker, findsNothing);
    expect(t.takeException(), isNull);
  });
  testWidgets(
      'two favorites and the active capture survive switching and app restart',
      (t) async {
    LiteModel capture(String name, double scale) {
      final record = LiteModel.fixture().toRecord();
      final slot = LiteModel.fixture().slot;
      final view = ByteData.sublistView(slot);
      view.setFloat32(
          32 + 4 * (LiteModel.weightCount - 1), scale, Endian.little);
      view.setUint32(20, crc32(slot.sublist(32, 7516)), Endian.little);
      record['slot'] = base64Encode(slot);
      record['sha256'] = crypto.sha256.convert(slot).toString();
      record['metadata'] = {'name': name, 'creator': 'Test', 'license': 'CC0'};
      return LiteModel.restore(record);
    }

    final first = capture('First favorite', 1),
        second = capture('Second favorite', .5);
    final rig = HybridRig.initial()..modelSha256 = first.sha256Hex;
    library = jsonEncode({
      'schema': 'nam-plug-library-2',
      'active': rig.encode(),
      'presets': <String, String>{},
      'models': (ModelLibrary()
            ..add(first)
            ..add(second))
          .toJson(),
      'tone_client_id': '',
    });
    await t.binding.setSurfaceSize(const Size(1120, 1100));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('favorite-loaded-model')));
    await t.pumpAndSettle();
    await t.tap(find.text('My favorites'));
    await t.pumpAndSettle();
    await t.tap(find.text('All saved (2)'));
    await t.pumpAndSettle();
    final secondCard = find.ancestor(
        of: find.text('Second favorite'), matching: find.byType(Card));
    await t.tap(find.descendant(
        of: secondCard, matching: find.byTooltip('Favorite capture')));
    await t.pumpAndSettle();
    expect(jsonDecode(library!)['models']['favorites'].toSet(),
        {first.sha256Hex, second.sha256Hex});
    await t.tap(
        find.descendant(of: secondCard, matching: find.text('Use capture')));
    await t.pumpAndSettle();
    expect(HybridRig.parse(jsonDecode(library!)['active']).modelSha256,
        second.sha256Hex);
    expect(
        find.descendant(
            of: find.byKey(const ValueKey('selected-controls')),
            matching: find.text('Second favorite')),
        findsOneWidget);
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    expect(
        find.descendant(
            of: find.byKey(const ValueKey('selected-controls')),
            matching: find.text('Second favorite')),
        findsOneWidget);
    await t.tap(find.text('My favorites'));
    await t.pumpAndSettle();
    expect(find.text('Favorites (2)'), findsOneWidget);
    expect(find.text('First favorite'), findsOneWidget);
    expect(find.text('Second favorite'), findsOneWidget);
    final firstCard = find.ancestor(
        of: find.text('First favorite'), matching: find.byType(Card));
    await t.tap(find.descendant(
        of: firstCard, matching: find.byTooltip('Remove favorite')));
    await t.pumpAndSettle();
    expect(jsonDecode(library!)['models']['favorites'], [second.sha256Hex]);
    expect(HybridRig.parse(jsonDecode(library!)['active']).modelSha256,
        second.sha256Hex);
    expect(calls.where((m) => !['loadLibrary', 'saveLibrary'].contains(m)),
        isEmpty);
    expect(t.takeException(), isNull);
  });
  testWidgets(
      'capture favorite survives app restart and can be recalled offline',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1120, 1100));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    await t.tap(find.text('Settings'));
    await t.pumpAndSettle();
    await t.tap(find.text('Add silent test fixture'));
    await t.pumpAndSettle();
    await t.tap(find.text('Signal chain'));
    await t.pumpAndSettle();
    await t.tap(find.byTooltip('Favorite capture'));
    await t.pumpAndSettle();
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    expect(find.text('Silent test model'), findsWidgets);
    await t.tap(find.text('My favorites'));
    await t.pumpAndSettle();
    expect(find.text('Favorites (1)'), findsOneWidget);
    expect(find.text('Silent test model'), findsOneWidget);
    expect(jsonDecode(library!)['models']['favorites'].length, 1);
    expect(calls.where((m) => !['loadLibrary', 'saveLibrary'].contains(m)),
        isEmpty);
    expect(t.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
  });
  testWidgets('Mac USB reads cannot imply chain writes or play audio',
      (t) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    await t.binding.setSurfaceSize(const Size(1000, 950));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    await t.tap(find.text('Plug'));
    await t.pumpAndSettle();
    await t.tap(find.text('Find plug'));
    await t.pumpAndSettle();
    await t.tap(find.text('MIGHTY PLUG PRO USB'));
    await t.pumpAndSettle();
    expect(find.text('Connected · status only'), findsOneWidget);
    expect(calls, ['loadLibrary', 'devices', 'inspect']);
    expect(t.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
    debugDefaultTargetPlatformOverride = null;
  });
  for (final mode in [
    (false, false),
    (false, true),
    (true, false),
    (true, true)
  ]) {
    final stockChain = mode.$1, stopped = mode.$2;
    testWidgets(
        'RAM upload verifies activation: stockChain=$stockChain stopped=$stopped',
        (t) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
      link = true;
      chainFirmware = stockChain;
      fault = stopped;
      await t.binding.setSurfaceSize(const Size(1120, 1100));
      addTearDown(() => t.binding.setSurfaceSize(null));
      final capture = LiteModel.fixture(),
          models = ModelLibrary()..add(LiteModel.fixture());
      final rig = HybridRig.initial()..modelSha256 = capture.sha256Hex;
      library = jsonEncode({
        'schema': 'nam-plug-library-2',
        'active': rig.encode(),
        'presets': {},
        'models': models.toJson(),
        'tone_client_id': ''
      });
      await t.pumpWidget(const NamLabApp(autoConnect: false));
      await t.pumpAndSettle();
      expect(find.byKey(const ValueKey('send-model')), findsNothing);
      await t.tap(find.text('Plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('Find plug'));
      await t.pumpAndSettle();
      await t.tap(find.text('MIGHTY PLUG PRO USB'));
      await t.pumpAndSettle();
      expect(find.text('Connected · silent'), findsOneWidget);
      await t.tap(find.text('Signal chain'));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('send-model')));
      await t.pumpAndSettle();
      expect(receiver.activeSlot, capture.slot);
      expect(calls.where((s) => s == 'exchangeModelFrame').length, 35);
      expect(calls.where((s) => s == 'inspect').length,
          stopped || !stockChain ? 3 : 5); // Fresh playback intent read before upload.
      if (stopped) {
        expect(find.textContaining('did not confirm the capture is running'),
            findsOneWidget);
        expect(find.byKey(const ValueKey('send-model')), findsNothing);
      } else {
        await t.drag(find.byType(ListView).first, const Offset(0, -600));
        await t.pumpAndSettle();
        expect(find.textContaining('is running on the plug. Output is silent'),
            findsOneWidget);
        // Choosing a capture while connected sends it automatically.
        await t.tap(find.text('Settings'));
        await t.pumpAndSettle();
        await t.tap(find.text('Add silent test fixture'));
        await t.pumpAndSettle();
        expect(calls.where((s) => s == 'exchangeModelFrame').length, 70);
        await t.tap(find.text('Signal chain'));
        await t.pumpAndSettle();
        await t.tap(find.byKey(const ValueKey('favorite-loaded-model')));
        await t.pumpAndSettle();
        expect(
            jsonDecode(library!)['models']['favorites'], [capture.sha256Hex]);
        // A normal restart loses the volatile model; the next read reports it.
        receiver.reset();
        await t.tap(find.text('Plug'));
        await t.pumpAndSettle();
        await t.tap(find.text('MIGHTY PLUG PRO USB'));
        await t.pumpAndSettle();
        expect(find.text('Capture: waiting for upload'), findsOneWidget);
      }
      expect(t.takeException(), isNull);
      debugDefaultTargetPlatformOverride = null;
    });
  }
  testWidgets(
      'block symbols toggle and chosen tone fills NAM with a saved favorite',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1280, 1000));
    addTearDown(() => t.binding.setSurfaceSize(null));
    final api = CatalogFixture();
    await t.pumpWidget(NamLabApp(autoConnect: false, toneApi: api));
    await t.pumpAndSettle();
    expect(find.text('Plug signal chain'), findsOneWidget);
    await t.tap(find.byKey(const ValueKey('toggle-drive')));
    await t.pumpAndSettle();
    expect(
        HybridRig.parse(jsonDecode(library!)['active'])
            .blocks
            .firstWhere((b) => b.slot == 'drive')
            .enabled,
        true);
    await t.tap(find.byKey(const ValueKey('toggle-drive')));
    await t.pumpAndSettle();
    expect(
        HybridRig.parse(jsonDecode(library!)['active'])
            .blocks
            .firstWhere((b) => b.slot == 'drive')
            .enabled,
        false);
    await t.tap(find.byKey(const ValueKey('block-nam')));
    await t.pumpAndSettle();
    await t.tap(find.text('Explore TONE3000'));
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    await t.tap(find.text('Test amp'));
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    await t.tap(find.text('Test Lite capture'));
    await t.pumpAndSettle();
    expect(
        find.descendant(
            of: find.byKey(const ValueKey('block-nam')),
            matching: find.text('Silent test model')),
        findsOneWidget);
    await t.tap(find.byKey(const ValueKey('favorite-loaded-model')));
    await t.pumpAndSettle();
    final stored = jsonDecode(library!);
    expect(stored['models']['favorites'], [LiteModel.fixture().sha256Hex]);
    expect(HybridRig.parse(stored['active']).modelSha256,
        LiteModel.fixture().sha256Hex);
    await t.tap(find.byKey(const ValueKey('toggle-nam')));
    await t.pumpAndSettle();
    expect(
        HybridRig.parse(jsonDecode(library!)['active'])
            .blocks
            .firstWhere((b) => b.slot == 'nam')
            .enabled,
        false);
    expect(find.byKey(const ValueKey('favorite-loaded-model')), findsOneWidget);
    expect(calls.where((m) => m == 'exchangeModelFrame'), isEmpty);
    expect(t.takeException(), isNull);
  });
}
