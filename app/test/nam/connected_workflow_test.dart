import 'dart:async';
import 'dart:convert';
import 'package:crypto/crypto.dart' as crypto;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/control_plan.dart';
import 'package:nam_link/nam_link.dart';
import 'tone_browser_test.dart' show CatalogFixture, mockOfficialPicker;

LiteModel capture(String name, double scale) {
  final record = LiteModel.fixture().toRecord(),
      slot = LiteModel.fixture().slot;
  final view = ByteData.sublistView(slot);
  view.setFloat32(32 + 4 * (LiteModel.weightCount - 1), scale, Endian.little);
  view.setUint32(20, crc32(slot.sublist(32, 7516)), Endian.little);
  record['slot'] = base64Encode(slot);
  record['sha256'] = crypto.sha256.convert(slot).toString();
  record['metadata'] = {
    'name': name,
    'tone_metadata': {'gear': 'amp-cab'}
  };
  return LiteModel.restore(record);
}

class UsbFixture {
  String identity = 'NAMLNK08';
  int bufferSamples = 8;
  final bufferCommands = <int>[];
  bool connected = true, listening = false, failTransfer = false, fault = false;
  int generation = 0, runs = 0, transfers = 0, applies = 0;
  SimulatedPlug receiver = SimulatedPlug();
  final preset = List<int>.filled(128, 0), listenCommands = <bool>[];
  String? library;
  Completer<void>? holdApply;
  UsbFixture() {
    apply(StockControlPlan.fromRig(HybridRig.initial()).controls,
        StockControlPlan.fromRig(HybridRig.initial()).order, true);
  }
  void apply(List<List<int>> controls, List<int> order, bool? nam) {
    for (final pair in controls) {
      preset[StockControlPlan.presetIndex(pair[0])!] = pair[1];
    }
    preset.setRange(90, 99, order);
    preset[3] = 1 | ((nam ?? true) ? 0 : 64);
  }

  Map<String, dynamic> status() => {
        'identity': identity,
        if (identity == 'NAMLNK09' ||
            ['NAMLNK18', 'NAMLNK19', 'NAMLNK20', 'NAMLNK21', 'NAMLNK22']
                .contains(identity))
          'audioBuffer': {
            'samples': bufferSamples,
            'sampleRate': 48000,
            'processingSamples': 8
          },
        'compatible': true,
        'modelTransfer': true,
        'stockChain': true,
        'listeningSupported': true,
        'listening': {'enabled': listening, 'settling': false},
        'words': [
          0x4e4c4b31,
          1,
          1,
          ++runs,
          fault ? 1 : 0,
          receiver.activeSlot == null ? 0 : crc32(receiver.activeSlot!),
          generation,
          runs,
          85,
          receiver.activeSlot == null || fault ? 0 : 1,
          0,
          0
        ],
        'audioStreamOpened': false,
      };
  Future<dynamic> call(MethodCall c) async {
    if (c.method == 'openToneBrowser') {
      final u = Uri.parse(c.arguments as String);
      return 'mighty-nam://oauth/callback?state=${u.queryParameters['state']}&tone_id=42&code=fixture';
    }
    if (c.method == 'nextToneSelection' || c.method == 'toneBrowserStatus')
      return null;

    if (c.method == 'loadLibrary') return library;
    if (c.method == 'saveLibrary') {
      library = c.arguments as String;
      return null;
    }
    if (c.method == 'devices') {
      return connected
          ? [
              {'source': 1, 'name': 'MIGHTY PLUG PRO USB'}
            ]
          : [];
    }
    if (c.method == 'disconnect') return null;
    if (!connected) throw PlatformException(code: 'disconnected');
    final a = c.arguments as Map;
    if (c.method == 'inspect') return status();
    if (c.method == 'setOutputBuffer') {
      bufferSamples = a['samples'] as int;
      bufferCommands.add(bufferSamples);
      if (!['NAMLNK18', 'NAMLNK19', 'NAMLNK20', 'NAMLNK21', 'NAMLNK22']
          .contains(identity)) listening = false;
      return status();
    }
    if (c.method == 'readStockControls') {
      return {'identity': 'NAMLNK08', 'preset': List<int>.from(preset)};
    }
    if (c.method == 'setListening') {
      listening = a['enabled'] as bool;
      listenCommands.add(listening);
      return status();
    }
    if (c.method == 'exchangeModelFrame') {
      transfers++;
      if (failTransfer) throw PlatformException(code: 'transfer-rejected');
      listening = false;
      final frame = a['frame'] as Uint8List;
      final reply = await receiver.exchange(frame);
      if (frame[5] == 4) generation++;
      return reply;
    }
    if (c.method == 'setCabinetBypassed') {
      preset[9] |= 64;
      return {'controlsVerified': true};
    }
    if (c.method == 'applyStockControls') {
      applies++;
      if (holdApply != null) await holdApply!.future;
      apply(
          (a['controls'] as List)
              .map((p) => List<int>.from(p as List))
              .toList(),
          List<int>.from(a['order'] as List),
          a['namEnabled'] as bool?);
      return {
        'identity': 'NAMLNK08',
        'controlsVerified': true,
        'stockChain': true,
        'preset': List<int>.from(preset)
      };
    }
    throw StateError('Unexpected method ${c.method}');
  }

  void seed(List<LiteModel> models, {LiteModel? selected}) {
    final list = ModelLibrary();
    for (final m in models) {
      list.add(m);
      list.toggleFavorite(m.sha256Hex);
    }
    library = jsonEncode({
      'schema': 'nam-plug-library-2',
      'active':
          (HybridRig.initial()..modelSha256 = selected?.sha256Hex).encode(),
      'presets': {},
      'models': list.toJson(),
      'tone_client_id': ''
    });
  }
}

void main() {
  late UsbFixture usb;
  setUp(() {
    mockOfficialPicker();
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    usb = UsbFixture();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
            const MethodChannel('nam_plug/device'), usb.call);
  });
  tearDown(() => debugDefaultTargetPlatformOverride = null);
  Future<void> start(WidgetTester t, {CatalogFixture? api}) async {
    await t.binding.setSurfaceSize(const Size(1120, 1100));
    addTearDown(() async {
      await t.pumpWidget(const SizedBox.shrink());
      await t.pump();
      await t.binding.setSurfaceSize(null);
    });
    await t.pumpWidget(NamLabApp(toneApi: api));
    await t.pumpAndSettle();
  }

  Future<void> tick(WidgetTester t) async {
    await t.pump(const Duration(seconds: 3));
    await t.pumpAndSettle();
  }

  testWidgets(
      'output buffer preserves playback using firmware readback without losing model',
      (t) async {
    usb.identity = 'NAMLNK09';
    final a = capture('First', 1);
    usb.seed([a], selected: a);
    await start(t);
    final crc = crc32(usb.receiver.activeSlot!);
    usb.listening = true;
    await t.tap(find.text('Settings'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('output-buffer')));
    await t.pumpAndSettle();
    await t.tap(find.text('32 samples · 0.67 ms').last);
    await t.pumpAndSettle();
    expect(usb.bufferCommands, [32]);
    expect(usb.listening, true);
    expect(crc32(usb.receiver.activeSlot!), crc);
    final dynamic home = t.state(find.byType(NamHome));
    expect(home.hardware['audioBuffer']['samples'], 32);
    expect(home.hardware['listening']['enabled'], true);
    final work = home.perform(() async {
      await home.setOutputBuffer(8);
    });
    await t.pumpAndSettle();
    await work;
    expect(usb.bufferCommands, [32, 8]);
    expect(usb.listenCommands.where((v) => v), hasLength(3));
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'NAMLNK08 keeps its fixed buffer and receives no unsupported setting',
      (t) async {
    await start(t);
    await t.tap(find.text('Settings'));
    await t.pumpAndSettle();
    final field = t.widget<DropdownButtonFormField<int>>(
        find.byKey(const ValueKey('output-buffer')));
    expect(field.onChanged, isNull);
    final dynamic home = t.state(find.byType(NamHome));
    await expectLater(home.setOutputBuffer(16), throwsStateError);
    expect(usb.bufferCommands, isEmpty);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'USB auto-connect, Tone browser choice, NAM activation and favorite stay consistent',
      (t) async {
    final api = CatalogFixture()..captureGear = 'amp-cab';
    usb.preset[3] |= 64; // New selection must enable a previously bypassed NAM.
    await start(t, api: api);
    expect(find.byTooltip('Connected'), findsOneWidget);
    await t.tap(find.text('Explore TONE3000'));
    await t.pumpAndSettle();
    expect(find.byTooltip('Close tone browser'), findsNothing);
    await t.pumpAndSettle();
    final saved = HybridRig.parse(jsonDecode(usb.library!)['active']);
    expect(saved.modelSha256, LiteModel.fixture().sha256Hex);
    expect(crc32(usb.receiver.activeSlot!), LiteModel.fixture().checksum);
    expect(usb.preset[3] & 64, 0);
    expect(usb.preset[9] & 64, 64);
    expect(find.text('Loaded on plug'), findsOneWidget);
    expect(usb.listening, true);
    await t.tap(find.byKey(const ValueKey('favorite-loaded-model')));
    await t.pumpAndSettle();
    expect(
        jsonDecode(usb.library!)['models']['favorites'], [saved.modelSha256]);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'offline selection loads on reconnect and after restart, favorites preserved',
      (t) async {
    final a = capture('First', 1), b = capture('Second', .5);
    usb.seed([a, b], selected: a);
    usb.connected = false;
    await start(t);
    final dynamic home = t.state(find.byType(NamHome));
    home.rig.blocks.singleWhere((b) => b.slot == 'delay').enabled = true;
    home.edited(); // Offline edits must not prevent later USB discovery.
    final selection = home.perform(() async {
      await home.selectCapture(b);
    });
    await t.pumpAndSettle();
    await selection;
    expect(usb.transfers, 0);
    expect(find.text('Selected on this Mac'), findsOneWidget);
    usb.connected = true;
    await tick(t);
    expect(crc32(usb.receiver.activeSlot!), b.checksum);
    expect(usb.preset[7] & 64, 0);
    expect(find.text('Loaded on plug'), findsOneWidget);
    expect(jsonDecode(usb.library!)['models']['favorites'].toSet(),
        {a.sha256Hex, b.sha256Hex});
    usb.receiver = SimulatedPlug();
    usb.generation = 0;
    await tick(t);
    expect(crc32(usb.receiver.activeSlot!), b.checksum);
    expect(usb.listening, true);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('block toggle and order changes apply without an Apply button',
      (t) async {
    final a = capture('First', 1);
    usb.seed([a], selected: a);
    await start(t);
    final before = usb.applies;
    await t.tap(find.byKey(const ValueKey('toggle-drive')));
    await t.pump(const Duration(milliseconds: 300));
    await t.pumpAndSettle();
    expect(usb.applies, greaterThan(before));
    expect(usb.preset[2] & 64, 0);
    await t.tap(find.byTooltip('Move later'));
    await t.pump(const Duration(milliseconds: 300));
    await t.pumpAndSettle();
    final saved = HybridRig.parse(jsonDecode(usb.library!)['active']);
    expect(usb.preset.sublist(90, 99), StockControlPlan.fromRig(saved).order);
    expect(usb.listening, true);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('rapid edits during an in-flight apply deliver the latest values',
      (t) async {
    final a = capture('First', 1);
    usb.seed([a], selected: a);
    await start(t);
    final dynamic home = t.state(find.byType(NamHome));
    usb.holdApply = Completer<void>();
    home.rig.blocks.singleWhere((b) => b.slot == 'drive').enabled = true;
    home.edited();
    await t.pump(const Duration(milliseconds: 300));
    await t.pump();
    home.rig.blocks.singleWhere((b) => b.slot == 'drive').enabled = false;
    home.edited();
    usb.holdApply!.complete();
    usb.holdApply = null;
    await t.pumpAndSettle();
    await t.pump(const Duration(milliseconds: 300));
    await t.pumpAndSettle();
    expect(usb.preset[2] & 64, 64);
    expect(home.pendingControls, false);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'failed transfer never reports loaded and does not loop automatic retries',
      (t) async {
    final a = capture('First', 1);
    usb.seed([a], selected: a);
    usb.failTransfer = true;
    await start(t);
    expect(find.text('Loaded on plug'), findsNothing);
    expect(find.text('Selected on this Mac'), findsOneWidget);
    final count = usb.transfers;
    await tick(t);
    await tick(t);
    expect(usb.transfers, count);
    expect(usb.listening, false);
    expect(usb.listenCommands, isNot(contains(true)));
    usb.failTransfer = false;
    await t.tap(find.byKey(const ValueKey('send-model')));
    await t.pumpAndSettle();
    expect(find.text('Loaded on plug'), findsOneWidget);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets(
      'USB disconnect clears active status and preserves chosen capture',
      (t) async {
    final a = capture('First', 1);
    usb.seed([a], selected: a);
    await start(t);
    usb.connected = false;
    await tick(t);
    expect(find.byTooltip('Disconnected'), findsOneWidget);
    expect(find.text('Loaded on plug'), findsNothing);
    expect(HybridRig.parse(jsonDecode(usb.library!)['active']).modelSha256,
        a.sha256Hex);
    usb.connected = true;
    await tick(t);
    expect(find.text('Loaded on plug'), findsOneWidget);
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump();
    debugDefaultTargetPlatformOverride = null;
  });
}
