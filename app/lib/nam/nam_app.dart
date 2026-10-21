import 'dart:async';
import 'dart:convert';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import 'package:nam_link/nam_link.dart';
import 'package:nam_device/nam_device.dart';
import 'preset_store.dart' as storage;
import 'tone_browser.dart';
import 'tone_session_store.dart';
import 'stock/rig.dart';
import 'stock/control_plan.dart';
import 'rig_editor.dart';
import 'model_library.dart';
import 'onboard_presets.dart';
import 'fx_client.dart';
import 'stock/extra_fx.dart';
import 'tuner.dart';
import 'tuner_dialog.dart';
import 'plug_model_transport.dart';
import 'package:url_launcher/url_launcher.dart';

const ink = Color(0xff17191c),
    panel = Color(0xff202327),
    mint = Color(0xff8ebcef);

class NamLabApp extends StatelessWidget {
  final Tone3000Client? toneApi;
  final String bundledToneClientId;
  final bool autoConnect;
  const NamLabApp(
      {super.key,
      this.toneApi,
      this.autoConnect = true,
      this.bundledToneClientId =
          const String.fromEnvironment('TONE3000_CLIENT_ID')});
  @override
  Widget build(BuildContext context) => MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'NAM Plug',
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        scaffoldBackgroundColor: ink,
        colorScheme: ColorScheme.fromSeed(
            seedColor: mint, brightness: Brightness.dark, surface: panel),
        cardTheme: const CardTheme(
            color: panel,
            elevation: 0,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.all(Radius.circular(8)))),
        inputDecorationTheme: const InputDecorationTheme(
            border: OutlineInputBorder(), filled: true),
      ),
      home: NamHome(
          toneApi: toneApi,
          bundledToneClientId: bundledToneClientId,
          autoConnect: autoConnect));
}

class NamHome extends StatefulWidget {
  final Tone3000Client? toneApi;
  final String bundledToneClientId;
  final bool autoConnect;
  const NamHome(
      {super.key,
      this.toneApi,
      this.bundledToneClientId = '',
      this.autoConnect = true});
  @override
  State<NamHome> createState() => _NamHomeState();
}

class _NamHomeState extends State<NamHome> {
  final device = NamDevice();
  HybridRig rig = HybridRig.initial()..name = presetColorNames[0];
  ModelLibrary captures = ModelLibrary();
  final saved = <String, String>{};
  OnboardPresets onboard = OnboardPresets();
  final plugPresets = <int, PresetSnapshot>{};
  int? observedPreset;
  bool get hasPresetBank =>
      const [
        'NAMLNK10',
        'NAMLNK11',
        'NAMLNK12',
        'NAMLNK13',
        'NAMLNK14',
        'NAMLNK15',
        'NAMLNK16'
      ].contains(hardware?['identity']) &&
      hardware?['presetBank'] is Map;
  bool get hasExtraFx => supportsExtraFx(hardware?['identity'] as String?);
  FxClient get fxClient =>
      FxClient((frame) => device.exchangeFxFrame(selectedSource!, frame));
  Future<PresetSnapshot> readPresetWithFx(int slot) async {
    final snapshot = await presetClient.read(slot);
    if (hasExtraFx) snapshot.extraFx = await fxClient.read(savedSlot: slot);
    return snapshot;
  }

  PresetClient get presetClient => PresetClient(
      (frame) => device.exchangePresetFrame(selectedSource!, frame),
      identity: hardware?['identity'] as String?);
  Tone3000Client? api;
  Map<String, dynamic>? hardware;
  List<Map<String, dynamic>> devices = [];
  int tab = 0;
  int? selectedSource;
  double? transferProgress;
  bool busy = false, favoritesOnly = false, restoring = true;
  String search = '';
  String toneClientId = '', toneClientIdDraft = '';
  String status = 'Ready. Connect your plug by USB in normal mode.';
  String? updateSummary;
  Future<void> saveWork = Future.value();
  Timer? connectionTimer, controlsTimer;
  Future<void> backgroundWork = Future.value();
  bool polling = false, pendingControls = false, pendingModel = false;
  bool autoReloadBlocked = false;
  LiteModel? get model => captures.captures[rig.modelSha256];
  bool get canTransfer =>
      native &&
      defaultTargetPlatform == TargetPlatform.macOS &&
      selectedSource != null &&
      const [
        'NAMLNK01',
        'NAMLNK02',
        'NAMLNK03',
        'NAMLNK04',
        'NAMLNK05',
        'NAMLNK06',
        'NAMLNK07',
        'NAMLNK08',
        'NAMLNK09',
        'NAMLNK10',
        'NAMLNK11',
        'NAMLNK12',
        'NAMLNK13',
        'NAMLNK14',
        'NAMLNK15',
        'NAMLNK16'
      ].contains(hardware?['identity']) &&
      hardware?['modelTransfer'] == true;
  bool get hasStockChain =>
      const [
        'NAMLNK02',
        'NAMLNK03',
        'NAMLNK04',
        'NAMLNK05',
        'NAMLNK06',
        'NAMLNK07',
        'NAMLNK08',
        'NAMLNK09',
        'NAMLNK10',
        'NAMLNK11',
        'NAMLNK12',
        'NAMLNK13',
        'NAMLNK14',
        'NAMLNK15',
        'NAMLNK16'
      ].contains(hardware?['identity']) &&
      hardware?['stockChain'] == true;
  bool get hasListening =>
      const [
        'NAMLNK07',
        'NAMLNK08',
        'NAMLNK09',
        'NAMLNK10',
        'NAMLNK11',
        'NAMLNK12',
        'NAMLNK13',
        'NAMLNK14',
        'NAMLNK15',
        'NAMLNK16'
      ].contains(hardware?['identity']) &&
      hardware?['listeningSupported'] == true;
  bool get listening => (hardware?['listening'] as Map?)?['enabled'] == true;
  PresetSnapshot? get selectedOnboardCapture {
    if (!hasPresetBank) return null;
    final bank = hardware!['presetBank'] as Map;
    final active = bank['active'];
    if (active is! int || active != onboard.selected) return null;
    final saved = plugPresets[active];
    if (saved == null ||
        !saved.occupied ||
        ((bank['mask'] as int) & (1 << active)) == 0 ||
        saved.modelSha != rig.modelSha256) {
      return null;
    }
    return saved;
  }

  // A recalled capture can live only on the plug. Match its verified bank
  // metadata to the selected editor capture instead of requiring local weights.
  int? get selectedCaptureChecksum =>
      model?.checksum ?? selectedOnboardCapture?.modelCrc;
  bool get loadedAndHealthy {
    final words = hardware?['words'] as List?;
    final checksum = selectedCaptureChecksum;
    return words?.length == 12 &&
        words![4] == 0 &&
        words[10] == 0 &&
        checksum != null &&
        words[5] == checksum &&
        words[9] == 1;
  }

  bool get bundledToneConnection =>
      widget.bundledToneClientId.trim().isNotEmpty;
  bool get toneConfigured => toneClientId.startsWith('t3k_pub_');
  bool get native =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.macOS ||
          defaultTargetPlatform == TargetPlatform.iOS);
  @override
  void initState() {
    super.initState();
    api = widget.toneApi;
    toneClientId = api?.clientId ?? widget.bundledToneClientId.trim();
    toneClientIdDraft = toneClientId;
    restore().then((_) {
      if (!mounted || !native || !widget.autoConnect) return;
      unawaited(perform(refreshConnection));
      connectionTimer = Timer.periodic(const Duration(seconds: 3), (_) {
        if (!mounted || busy || restoring || polling) {
          return;
        }
        polling = true;
        backgroundWork = refreshConnection().catchError((Object error) {
          if (mounted) {
            setState(() {
              hardware = null;
              selectedSource = null;
              status =
                  'USB connection lost. Reconnect the plug in normal mode.';
            });
          }
        }).whenComplete(() => polling = false);
      });
    });
  }

  Future<void> restore() async {
    try {
      final text = await storage.loadLibrary();
      if (text == null) return;
      if (text.length > 2097152) {
        throw const FormatException('Library too large');
      }
      final j = jsonDecode(text);
      if (j is! Map || j['schema'] != 'nam-plug-library-2') {
        throw const FormatException('Unknown library');
      }
      final active = HybridRig.parse(j['active']);
      final entries = Map<String, String>.from(j['presets']);
      if (entries.length > 32) throw const FormatException('Too many chains');
      for (final value in entries.values) {
        HybridRig.parse(value);
      }
      final library = ModelLibrary.parse(j['models']);
      final bank = j['onboard'] == null
          ? OnboardPresets()
          : OnboardPresets.parse(j['onboard']);
      if (j['onboard'] == null) bank.edit(active);
      if (!mounted) return;
      setState(() {
        rig = active;
        saved.addAll(entries);
        captures = library;
        onboard = bank;
        // A saved draft (including an empty ID from older builds) must never
        // replace the app registration included in a release.
        if (widget.toneApi == null &&
            !bundledToneConnection &&
            j['tone_client_id'] is String) {
          toneClientId = (j['tone_client_id'] as String).trim();
          toneClientIdDraft = toneClientId;
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() => status =
            'Saved library could not be opened. Import a saved chain or start a new one.');
      }
    } finally {
      if (mounted) setState(() => restoring = false);
    }
  }

  Future<void> persist() {
    onboard.edit(rig);
    final value = jsonEncode({
      'schema': 'nam-plug-library-2',
      'active': rig.encode(),
      'presets': saved,
      'onboard': onboard.toJson(),
      'models': captures.toJson(),
      'tone_client_id': toneClientId
    });
    final next =
        saveWork.catchError((_) {}).then((_) => storage.saveLibrary(value));
    saveWork = next;
    return next;
  }

  void edited() {
    persist().catchError((_) {
      if (mounted) {
        setState(() => status =
            'Could not save your changes. Export this chain before closing.');
      }
    });
    pendingControls = true;
    scheduleControls();
  }

  void scheduleControls() {
    controlsTimer?.cancel();
    if (!mounted || !canTransfer || !pendingControls) return;
    controlsTimer = Timer(const Duration(milliseconds: 250), () {
      if (!busy) unawaited(perform(sendStockControls));
    });
  }

  Future<void> refreshConnection() async {
    final found = await device.devices();
    if (!mounted) return;
    setState(() => devices = found);
    if (found.isEmpty ||
        (selectedSource != null &&
            !found.any((d) => d['source'] == selectedSource))) {
      setState(() {
        hardware = null;
        selectedSource = null;
        observedPreset = null;
        plugPresets.clear();
        status =
            'Connect the plug by USB in normal mode. Your selected capture and chain are saved.';
      });
    }
    if (selectedSource == null) {
      if (found.length == 1) await inspect(found.single['source'] as int);
      return;
    }
    final result = await device.inspect(selectedSource!);
    if (!mounted) return;
    setState(() => hardware = result);
    final words = result['words'] as List?;
    if (words?.length == 12 && words![4] != 0) {
      if (hasListening && listening) {
        final muted = await device.setListening(selectedSource!, false);
        if (mounted) setState(() => hardware = muted);
      }
      setState(() => status =
          'The plug stopped processing. Restart it normally, then reconnect; reduce the effect load before listening.');
      return;
    }
    if (hasPresetBank) {
      await readOnboardBank();
      if (!onboard.dirty[onboard.selected] &&
          !pendingControls &&
          !pendingModel) {
        await readChainFromPlug();
      }
      return;
    }
    if (!autoReloadBlocked &&
        canTransfer &&
        model != null &&
        words?.length == 12 &&
        words![5] == 0) {
      await sendModel(); // A power cycle clears RAM. Reload muted, never resume listening automatically.
    } else if (hasStockChain && !pendingControls && !pendingModel) {
      await readChainFromPlug();
    }
  }

  Future<void> readChainFromPlug() async {
    final source = selectedSource;
    if (source == null || !hasStockChain) return;
    final snapshot = await device.readStockControls(source);
    late HybridRig next;
    try {
      next = StockControlPlan.readRig(
          rig, List<int>.from(snapshot['preset'] as List),
          identity: hardware?['identity'] as String?,
          fx: hasExtraFx ? await fxClient.read() : null);
    } on FormatException {
      if (mounted) {
        setState(() => status =
            'Connected, but some effect settings could not be read. Choose supported effects and sync your chain.');
      }
      return;
    }
    final words = hardware?['words'] as List?;
    if (!pendingModel && words?.length == 12 && words![5] != 0) {
      final matches =
          captures.captures.values.where((m) => m.checksum == words[5]);
      if (matches.isNotEmpty) next.modelSha256 = matches.first.sha256Hex;
    }
    if (!mounted || pendingControls) return;
    if (next.encode() != rig.encode()) {
      setState(() => rig = next);
      await persist();
    }
  }

  @override
  void dispose() {
    connectionTimer?.cancel();
    controlsTimer?.cancel();
    api?.close();
    super.dispose();
  }

  Widget card(Widget child) => Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(padding: const EdgeInsets.all(20), child: child));
  Future<void> perform(Future<void> Function() action) async {
    if (busy || restoring) return;
    setState(() => busy = true);
    try {
      await backgroundWork;
      if (!mounted) return;
      await action();
    } catch (error) {
      if (mounted) {
        setState(() => status = error is PlatformException
            ? (error.message ??
                'The operation could not finish. Check the connection and try again.')
            : '$error');
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
        scheduleControls();
      }
    }
  }

  Future<void> openTuner() async {
    try {
      final source = selectedSource;
      if (source == null ||
          !const ['NAMLNK12', 'NAMLNK13', 'NAMLNK14', 'NAMLNK15', 'NAMLNK16']
              .contains(hardware?['identity'])) {
        throw const FormatException(
            'The tuner needs NAMLNK12. Connect the plug after installing the tuner firmware.');
      }
      final muted = await device.setListening(source, false);
      if (!const ['NAMLNK12', 'NAMLNK13', 'NAMLNK14', 'NAMLNK15', 'NAMLNK16']
              .contains(muted['identity']) ||
          (muted['listening'] as Map?)?['enabled'] != false) {
        throw const FormatException(
            'Could not confirm that the plug is muted.');
      }
      if (!mounted) return;
      setState(() => hardware = muted);
      final failure = await showDialog<String>(
          context: context,
          barrierDismissible: false,
          builder: (_) => TunerDialog(
              client: TunerClient((op, page, nonce) =>
                  device.tunerFrame(source, op, page, nonce))));
      if (!mounted) return;
      hardware = await device.inspect(source);
      setState(() => status = failure ??
          'Tuner closed. Plug muted; press Listen on plug to resume.');
    } catch (error) {
      if (mounted) {
        final message = error is FormatException
            ? error.message.toString()
            : error is PlatformException
                ? (error.message ?? 'Tuner connection failed.')
                : 'Could not open the tuner. Check the USB connection.';
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(message)));
      }
      rethrow;
    }
  }

  Future<Tone3000Client> toneClient() async {
    if (!toneConfigured) {
      throw const FormatException(
          'TONE3000 sign-in is not enabled in this build yet. NAM Plug needs its one-time app registration. Your saved captures are available offline.');
    }
    api ??= Tone3000Client(toneClientId.trim(),
        sessionStore: NativeToneSessionStore());
    await api!.restoreSession();
    return api!;
  }

  Future<Tone3000Client> signInTone() async {
    final client = await toneClient();
    if (client.connected) return client;
    final redirect = kIsWeb
        ? Uri.base.resolve('auth.html')
        : Uri.parse('mighty-nam://oauth/callback');
    final flow = client.authorize(redirect);
    final callback = await FlutterWebAuth2.authenticate(
        url: '${flow.url}', callbackUrlScheme: 'mighty-nam');
    await client.complete(flow, Uri.parse(callback));
    if (!client.connected) throw const FormatException('Sign-in canceled.');
    return client;
  }

  Future<void> selectCapture(LiteModel next) async {
    controlsTimer?.cancel();
    captures.add(next);
    setState(() {
      rig.modelSha256 = next.sha256Hex;
      rig.blocks.singleWhere((b) => b.slot == 'nam').enabled = true;
      pendingModel = true;
      autoReloadBlocked = false;
      if (captureIncludesCabinet(next)) {
        rig.blocks.singleWhere((b) => b.slot == 'cab').enabled = false;
      }
      status =
          'Selected ${next.metadata['name'] ?? 'A2 Lite'}. Saved on this Mac.${canTransfer ? ' Loading it onto the plug.' : ' Connect the plug to load it.'}';
    });
    await persist();
    if (canTransfer) await sendModel();
  }

  Future<void> openToneBrowser() async {
    if (toneConfigured) await toneClient();
    if (!mounted) return;
    final next = await showModalBottomSheet<LiteModel>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        useSafeArea: true,
        constraints: const BoxConstraints(maxWidth: 1000),
        builder: (ctx) => FractionallySizedBox(
            heightFactor: .94,
            child: ToneBrowser(
                client: api,
                signIn: signInTone,
                officialPicker: () async {
                  final capture = await officialBrowse();
                  if (ctx.mounted && capture != null) {
                    Navigator.pop(ctx, capture);
                  }
                })));
    if (next != null && mounted) await selectCapture(next);
    if (mounted) setState(() {});
  }

  Future<LiteModel?> officialBrowse() async {
    final client = await toneClient();
    final redirect = kIsWeb
        ? Uri.base.resolve('auth.html')
        : Uri.parse('mighty-nam://oauth/callback');
    final flow = client.select(redirect);
    final callback = await FlutterWebAuth2.authenticate(
        url: '${flow.url}', callbackUrlScheme: 'mighty-nam');
    final id = await client.complete(flow, Uri.parse(callback));
    if (id == null || !mounted) return null;
    // Enter the same in-app detail view after the official picker has selected a tone.
    return showModalBottomSheet<LiteModel>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        constraints: const BoxConstraints(maxWidth: 1000),
        builder: (_) => FractionallySizedBox(
            heightFactor: .94,
            child: ToneBrowser(
                client: client,
                initialToneId: id,
                signIn: signInTone,
                officialPicker: () async {})));
  }

  Future<void> importFile() async {
    final file = await openFile(acceptedTypeGroups: const [
      XTypeGroup(
          label: 'NAM model',
          extensions: ['nam'],
          uniformTypeIdentifiers: ['public.data'])
    ]);
    if (file == null) return;
    if (await file.length() > LiteModel.maxJsonBytes) {
      throw const FormatException('Choose a .nam file smaller than 4 MiB');
    }
    final next = LiteModel.parse(await file.readAsBytes(),
        provenance: {'name': file.name, 'source': 'local import'});
    if (mounted) await selectCapture(next);
  }

  Future<void> favorite(String sha) async {
    setState(() => captures.toggleFavorite(sha));
    await persist();
  }

  Future<void> sendStockControls() async {
    try {
      await applyStockControls();
    } catch (_) {
      final source = selectedSource;
      if (source != null && hasListening) {
        try {
          final muted = await device.setListening(source, false);
          if (mounted) setState(() => hardware = muted);
        } catch (_) {
          if (mounted) {
            setState(() {
              hardware = null;
              selectedSource = null;
            });
          }
        }
      }
      rethrow;
    }
  }

  Future<void> applyStockControls() async {
    controlsTimer?.cancel();
    pendingControls = false;
    final source = selectedSource;
    if (!canTransfer || source == null) {
      throw StateError('Connect supported NAM Plug firmware first.');
    }
    final chain = HybridRig.parse(rig.encode());
    final plan = StockControlPlan.fromRig(chain,
        identity: hardware?['identity'] as String?);
    final before = await device.inspect(source);
    final beforeWords = (before['words'] as List?) ?? [];
    if (before['identity'] != hardware?['identity'] ||
        beforeWords.length != 12) {
      throw StateError('The connected firmware changed. Reconnect the plug.');
    }
    if (beforeWords[4] != 0 || beforeWords[10] != 0) {
      throw StateError(
          'The plug reports a fault. Restart it before sending controls.');
    }
    final result = await device.applyStockControls(
        source, plan.controls, plan.order,
        namEnabled: hasStockChain
            ? chain.blocks.singleWhere((b) => b.slot == 'nam').enabled
            : null);
    if (result['controlsVerified'] != true) {
      throw StateError('The plug did not confirm its effect controls.');
    }
    if (hasExtraFx) {
      final expected = chain.fxConfig();
      await fxClient.write(
          expected,
          (before['presetBank'] as Map)['active'] as int,
          beforeWords[5] as int);
      if ((await fxClient.read()).join(',') != expected.join(',')) {
        throw StateError('The plug did not confirm FX A/B.');
      }
    } else if (chain.blocks.any((b) => b.extra && b.enabled)) {
      throw StateError('FX A/B require NAMLNK13 or newer.');
    }
    await Future<void>.delayed(const Duration(milliseconds: 250));
    final after = await device.inspect(source);
    if (mounted) setState(() => hardware = after);
    final words = after['words'] as List;
    if (words.length != 12 ||
        words[4] != 0 ||
        words[10] != 0 ||
        words[5] != beforeWords[5] ||
        (beforeWords[9] == 1 &&
            (words[9] != 1 || words[7] <= beforeWords[7]))) {
      if (hasListening) await device.setListening(source, false);
      throw StateError(
          'Controls changed but the model check failed. Check Plug status.');
    }
    if (mounted) {
      setState(() {
        hardware = after;
        final processing = hasListening
            ? 'The full chain is configured. ${listening ? 'Listening resumes after the change settles.' : 'Ready for listening when you enable it.'}'
            : hasStockChain
                ? 'The full chain is configured; output stays silent.'
                : 'Stock effects are not processing yet; output stays silent.';
        status =
            'Effect choices, controls and order verified on the plug. $processing';
      });
    }
  }

  Future<void> savePreset() async {
    final controller = TextEditingController(text: rig.name);
    final name = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
                title: const Text('Save chain'),
                content: TextField(
                    controller: controller,
                    maxLength: 80,
                    autofocus: true,
                    decoration: const InputDecoration(labelText: 'Chain name')),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () =>
                          Navigator.pop(ctx, controller.text.trim()),
                      child: const Text('Save'))
                ]));
    if (name == null || name.isEmpty) return;
    if (saved.length >= 32 && !saved.containsKey(name)) {
      throw const FormatException(
          'Library holds 32 chains. Replace an existing name.');
    }
    setState(() {
      rig.name = name;
      saved[name] = rig.encode();
    });
    await persist();
    if (mounted) setState(() => status = 'Saved “$name” on this Mac.');
  }

  Future<void> importPreset() async {
    final file = await openFile(acceptedTypeGroups: const [
      XTypeGroup(
          label: 'NAM Plug chain',
          extensions: ['json'],
          uniformTypeIdentifiers: ['public.json'])
    ]);
    if (file == null) return;
    if (await file.length() > 65536) {
      throw const FormatException('Chain is too large');
    }
    final next = HybridRig.parse(await file.readAsString());
    if (mounted) {
      setState(() => rig = next);
      await persist();
      if (canTransfer) {
        if (model != null) {
          await sendModel();
        } else {
          await sendStockControls();
        }
      }
    }
  }

  Future<void> copyPreset() async {
    await Clipboard.setData(ClipboardData(text: rig.encode()));
    if (mounted) {
      setState(() => status =
          'Signal chain copied: block order, effect choices, controls, bypass and capture identity. Capture files are not shared.');
    }
  }

  String creatorName(LiteModel m) {
    final value = m.metadata['creator'];
    return value is Map
        ? '${value['username'] ?? 'Creator'}'
        : '${value ?? 'Local capture'}';
  }

  Widget get namControls =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(
                    '${model?.metadata['name'] ?? selectedOnboardCapture?.name ?? 'Find your next tone'}',
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.w500)),
                const SizedBox(height: 6),
                Text(
                    model == null
                        ? selectedOnboardCapture != null
                            ? 'A2 Lite · 48 kHz · Stored on plug'
                            : 'Browse TONE3000 or choose one of your saved captures.'
                        : '${creatorName(model!)} · A2 Lite · 48 kHz',
                    style:
                        const TextStyle(color: Colors.white60, fontSize: 12)),
                if (model != null || selectedOnboardCapture != null) ...[
                  const SizedBox(height: 6),
                  Text(
                      loadedAndHealthy
                          ? 'Loaded on plug'
                          : 'Selected on this Mac',
                      key: const ValueKey('capture-location'),
                      style: TextStyle(
                          color: loadedAndHealthy ? mint : Colors.white60,
                          fontSize: 12)),
                ],
              ])),
          if (model != null)
            IconButton(
                key: const ValueKey('favorite-loaded-model'),
                tooltip: captures.favorites.contains(model!.sha256Hex)
                    ? 'Remove favorite'
                    : 'Favorite capture',
                onPressed: busy
                    ? null
                    : () => perform(() => favorite(model!.sha256Hex)),
                icon: Icon(
                    captures.favorites.contains(model!.sha256Hex)
                        ? Icons.star
                        : Icons.star_border,
                    color: mint))
        ]),
        const SizedBox(height: 18),
        Wrap(spacing: 10, runSpacing: 10, children: [
          FilledButton.icon(
              onPressed: busy ? null : () => perform(openToneBrowser),
              icon: const Icon(Icons.travel_explore),
              label: const Text('Explore TONE3000')),
          OutlinedButton.icon(
              onPressed: busy
                  ? null
                  : () => setState(() {
                        tab = 1;
                        favoritesOnly = true;
                      }),
              icon: const Icon(Icons.star_outline),
              label: const Text('My favorites')),
          TextButton.icon(
              onPressed: busy ? null : () => perform(importFile),
              icon: const Icon(Icons.file_open_outlined),
              label: const Text('Import .nam')),
          if (canTransfer)
            FilledButton.tonalIcon(
                key: const ValueKey('send-model'),
                onPressed:
                    busy || model == null ? null : () => perform(sendModel),
                icon: const Icon(Icons.usb),
                label: Text(
                    hasListening ? 'Load on plug' : 'Send to plug · silent')),
        ]),
        if (transferProgress != null) ...[
          const SizedBox(height: 12),
          LinearProgressIndicator(value: transferProgress),
        ],
        if (canTransfer)
          const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Text(
                  'Your selection previews over USB. Save to plug keeps a colored preset after power off on NAMLNK10.',
                  style: TextStyle(color: Colors.white60, fontSize: 12))),
        if (rig.modelSha256 != null && model == null)
          const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Text(
                  'This capture is not in this Mac’s library. A saved onboard preset can still play; import the capture to upload a new copy.',
                  style: TextStyle(color: Colors.amber))),
      ]);

  Future<void> readOnboardBank() async {
    if (!hasPresetBank || selectedSource == null) return;
    final active = (hardware!['presetBank'] as Map)['active'] as int;
    final first = plugPresets.isEmpty;
    // Preserve the editor before replacing any clean slots with device data.
    onboard.edit(rig);
    if (first) {
      final snapshots = <PresetSnapshot>[];
      for (var i = 0; i < 7; i++) {
        snapshots.add(await readPresetWithFx(i));
      }
      // Commit the bank only when every read succeeds, so a failed initial
      // connection retries the whole bank rather than leaving a partial cache.
      for (var i = 0; i < 7; i++) {
        final snapshot = snapshots[i];
        plugPresets[i] = snapshot;
        onboard.generations[i] = snapshot.generation;
        if (!onboard.dirty[i]) {
          onboard.slots[i] = snapshot.rig(onboard.slots[i],
              identity: hardware?['identity'] as String?);
        }
      }
    }
    if (active < 7 && (first || observedPreset != active)) {
      final snapshot = await readPresetWithFx(active);
      plugPresets[active] = snapshot;
      onboard.selected = active;
      if (!onboard.dirty[active]) {
        onboard.slots[active] = snapshot.rig(onboard.slots[active],
            identity: hardware?['identity'] as String?);
      }
      if (!mounted) return;
      setState(() {
        rig = HybridRig.parse(onboard.slots[active].encode());
        observedPreset = active;
        pendingControls = false;
        pendingModel = false;
        status =
            '${presetColorNames[active]} preset is active on the plug.${onboard.dirty[active] ? ' Unsaved edits are kept in the editor.' : ''}';
      });
      await persist();
    } else if (first) {
      rig = HybridRig.parse(onboard.slots[onboard.selected].encode());
      await persist();
      if (mounted) {
        setState(() => status =
            'Seven preset slots are ready. Choose a capture, then Save to plug.');
      }
    }
  }

  Future<void> selectOnboard(int slot) async {
    controlsTimer?.cancel();
    onboard.edit(rig);
    setState(() {
      onboard.selected = slot;
      rig = HybridRig.parse(onboard.slots[slot].encode());
      pendingControls = false;
      pendingModel = false;
    });
    await persist();
    if (hasPresetBank &&
        plugPresets[slot]?.occupied == true &&
        !onboard.dirty[slot]) {
      final recalled = await presetClient.recall(slot);
      if (recalled.active != slot) {
        throw StateError('Preset selection was not confirmed.');
      }
      hardware = await device.inspect(selectedSource!);
      observedPreset = null;
      await readOnboardBank();
    } else {
      if (mounted) {
        setState(() => status =
            'Editing ${presetColorNames[slot]}. Choose a capture and Save to plug to keep it onboard.');
      }
    }
  }

  Future<void> saveOnboard() async {
    if (!hasPresetBank || model == null || selectedSource == null) {
      throw StateError(
          'Connect NAMLNK10 and choose an A2 Lite capture before saving onboard.');
    }
    final slot = onboard.selected, capture = model!;
    await sendModel(); // Muted upload, followed by verified complete effect plan.
    final snapshot = await device.readStockControls(selectedSource!);
    final effects = List<int>.from(snapshot['preset'] as List);
    final buffer = (hardware?['audioBuffer'] as Map?)?['samples'] as int? ?? 8;
    final saved =
        await presetClient.save(slot, capture, effects, rig.name, buffer);
    if (!saved.occupied ||
        saved.modelSha != capture.sha256Hex ||
        saved.modelCrc != capture.checksum ||
        saved.active != slot ||
        saved.effects!.join(',') != effects.join(',')) {
      throw StateError(
          'The plug did not confirm this complete preset. Your Mac copy is retained.');
    }
    // Read back independently. A successful send alone is never "Saved".
    final checked = await readPresetWithFx(slot);
    if (hasExtraFx && checked.extraFx?.join(',') != rig.fxConfig().join(',')) {
      throw StateError('Saved FX A/B did not match.');
    }
    if (checked.generation != saved.generation ||
        checked.modelSha != saved.modelSha ||
        checked.name != rig.name.trim() ||
        checked.effects!.join(',') != effects.join(',')) {
      throw StateError(
          'Saved preset readback did not match. Your Mac copy is retained.');
    }
    hardware = await device.inspect(selectedSource!);
    if ((hardware?['listening'] as Map?)?['enabled'] != false) {
      await device.setListening(selectedSource!, false);
      throw StateError(
          'Preset saved, but mute was not confirmed. Check the plug before listening.');
    }
    onboard.slots[slot] = HybridRig.parse(rig.encode());
    onboard.dirty[slot] = false;
    onboard.generations[slot] = saved.generation;
    plugPresets[slot] = checked;
    observedPreset = slot;
    await persist();
    if (mounted) {
      setState(() => status =
          '${presetColorNames[slot]} saved to the plug with its capture and effects. Output is muted now; saved presets play after power-on.');
    }
  }

  Future<void> renameOnboard() async {
    final text = TextEditingController(text: rig.name);
    final name = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
                title: Text('${presetColorNames[onboard.selected]} preset'),
                content: TextField(
                    controller: text,
                    autofocus: true,
                    maxLength: 40,
                    decoration:
                        const InputDecoration(labelText: 'Preset name')),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () => Navigator.pop(ctx, text.text.trim()),
                      child: const Text('Rename'))
                ]));
    text.dispose();
    if (name == null || name.isEmpty || !mounted) return;
    setState(() => rig.name = name);
    await persist();
  }

  Widget get presetStrip =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(
              child: Text('Onboard presets',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600))),
          TextButton.icon(
              onPressed: busy ? null : () => perform(renameOnboard),
              icon: const Icon(Icons.edit_outlined, size: 17),
              label: const Text('Rename'))
        ]),
        const SizedBox(height: 8),
        Wrap(
            spacing: 8,
            runSpacing: 8,
            children: List.generate(
                7,
                (i) => Semantics(
                    selected: onboard.selected == i,
                    label: 'Preset ${i + 1}, ${presetColorNames[i]}',
                    child: InkWell(
                        key: ValueKey('preset-color-$i'),
                        onTap:
                            busy ? null : () => perform(() => selectOnboard(i)),
                        borderRadius: BorderRadius.circular(8),
                        child: Container(
                            width: 112,
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                                color: onboard.selected == i
                                    ? Color(presetColors[i])
                                        .withValues(alpha: .12)
                                    : panel,
                                border: Border.all(
                                    color: onboard.selected == i
                                        ? Color(presetColors[i])
                                        : Colors.white24,
                                    width: onboard.selected == i ? 2 : 1),
                                borderRadius: BorderRadius.circular(8)),
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(children: [
                                    Container(
                                        width: 10,
                                        height: 10,
                                        decoration: BoxDecoration(
                                            color: Color(presetColors[i]),
                                            shape: BoxShape.circle)),
                                    const SizedBox(width: 6),
                                    Expanded(
                                        child: Text(
                                            '${i + 1} · ${presetColorNames[i]}',
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style:
                                                const TextStyle(fontSize: 12)))
                                  ]),
                                  const SizedBox(height: 7),
                                  Text(onboard.slots[i].name,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis),
                                  Text(
                                      hasPresetBank && observedPreset == i
                                          ? onboard.dirty[i]
                                              ? 'Active · unsaved'
                                              : 'Active on plug'
                                          : onboard.dirty[i]
                                              ? 'Unsaved edits'
                                              : plugPresets[i]?.occupied == true
                                                  ? 'Saved on plug'
                                                  : onboard.slots[i]
                                                              .modelSha256 !=
                                                          null
                                                      ? 'Mac draft'
                                                      : 'Empty',
                                      style: const TextStyle(
                                          fontSize: 11, color: Colors.white60))
                                ])))))),
        const SizedBox(height: 12),
        Wrap(
            spacing: 12,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              FilledButton.icon(
                  key: const ValueKey('save-onboard-preset'),
                  onPressed: busy || !hasPresetBank || model == null
                      ? null
                      : () => perform(saveOnboard),
                  icon: const Icon(Icons.save_outlined),
                  label: Text(
                      'Save ${presetColorNames[onboard.selected]} to plug')),
              Text(
                  hasPresetBank
                      ? 'Save keeps this capture and effects after power off.'
                      : 'Edit seven color presets here. Saving onboard requires NAMLNK10.',
                  style: const TextStyle(color: Colors.white60, fontSize: 12))
            ])
      ]);

  Widget get chain =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        presetStrip,
        const SizedBox(height: 20),
        Row(children: [
          const Expanded(
              child: Text('Plug signal chain',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w600))),
          IconButton(
              tooltip: 'Save chain',
              onPressed: busy ? null : () => perform(savePreset),
              icon: const Icon(Icons.bookmark_add_outlined))
        ]),
        const SizedBox(height: 8),
        Text(rig.name == 'My NAM rig' ? 'Untitled chain' : rig.name,
            style: const TextStyle(color: Colors.white60)),
        if (canTransfer)
          const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(
                  'Connected · effect controls and block order update the plug automatically',
                  style: TextStyle(color: Colors.white60, fontSize: 12))),
        if (hasListening) ...[
          const SizedBox(height: 18),
          Row(children: [
            listeningButton,
            const SizedBox(width: 12),
            const Expanded(
                child: Text('Reduced starting level · headphones on the plug',
                    style: TextStyle(color: Colors.white60, fontSize: 12)))
          ])
        ],
        const SizedBox(height: 26),
        RigEditor(
            rig: rig,
            firmwareIdentity: hardware?['identity'] as String?,
            modelName: model?.metadata['name']?.toString(),
            namControls: namControls,
            onChanged: edited),
        const SizedBox(height: 20),
        Wrap(spacing: 10, runSpacing: 10, children: [
          if (canTransfer)
            OutlinedButton.icon(
                key: const ValueKey('send-stock-controls'),
                onPressed: busy ? null : () => perform(sendStockControls),
                icon: const Icon(Icons.usb),
                label: Text(hasListening
                    ? 'Sync signal chain'
                    : 'Send effect controls · silent')),
          OutlinedButton.icon(
              onPressed: busy ? null : () => perform(importPreset),
              icon: const Icon(Icons.file_open_outlined),
              label: const Text('Import chain')),
          OutlinedButton.icon(
              onPressed: busy ? null : () => perform(copyPreset),
              icon: const Icon(Icons.ios_share),
              label: const Text('Share chain')),
          if (saved.isNotEmpty)
            PopupMenuButton<String>(
                tooltip: 'Saved chains',
                onSelected: (name) => perform(() async {
                      setState(() => rig = HybridRig.parse(saved[name]!));
                      await persist();
                      if (canTransfer) {
                        if (model != null) {
                          await sendModel();
                        } else {
                          await sendStockControls();
                        }
                      }
                    }),
                itemBuilder: (_) => saved.keys
                    .map(
                        (name) => PopupMenuItem(value: name, child: Text(name)))
                    .toList(),
                child: const Padding(
                    padding: EdgeInsets.all(12), child: Text('Saved chains'))),
        ]),
      ]);
  Widget get library {
    final rows = captures.captures.values
        .where((m) =>
            (!favoritesOnly || captures.favorites.contains(m.sha256Hex)) &&
            '${m.metadata['name']} ${m.metadata['creator']}'
                .toLowerCase()
                .contains(search.toLowerCase()))
        .toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('Your captures', style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 8),
      const Text('Saved on this Mac, ready to recall without signing in.',
          style: TextStyle(color: Colors.white60)),
      const SizedBox(height: 20),
      Wrap(spacing: 10, runSpacing: 10, children: [
        FilledButton.icon(
            onPressed: busy ? null : () => perform(openToneBrowser),
            icon: const Icon(Icons.travel_explore),
            label: const Text('Explore TONE3000')),
        OutlinedButton.icon(
            onPressed: busy ? null : () => perform(importFile),
            icon: const Icon(Icons.file_open_outlined),
            label: const Text('Import .nam')),
        ChoiceChip(
            label: Text('All saved (${captures.captures.length})'),
            selected: !favoritesOnly,
            onSelected: (_) => setState(() => favoritesOnly = false)),
        ChoiceChip(
            label: Text('Favorites (${captures.favorites.length})'),
            selected: favoritesOnly,
            onSelected: (_) => setState(() => favoritesOnly = true)),
      ]),
      const SizedBox(height: 20),
      TextField(
          decoration: const InputDecoration(
              labelText: 'Search saved captures',
              prefixIcon: Icon(Icons.search)),
          onChanged: (v) => setState(() => search = v)),
      const SizedBox(height: 20),
      if (rows.isEmpty)
        card(const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.bookmarks_outlined, size: 30, color: mint),
              SizedBox(height: 12),
              Text('A home for your favorite tones',
                  style: TextStyle(fontSize: 21)),
              SizedBox(height: 8),
              Text(
                  'Choose a capture in TONE3000 or import a compatible .nam file, then tap its star. Audio previews stay off.'),
            ])),
      for (final m in rows)
        card(Row(children: [
          IconButton(
              tooltip: captures.favorites.contains(m.sha256Hex)
                  ? 'Remove favorite'
                  : 'Favorite capture',
              onPressed:
                  busy ? null : () => perform(() => favorite(m.sha256Hex)),
              icon: Icon(
                  captures.favorites.contains(m.sha256Hex)
                      ? Icons.star
                      : Icons.star_outline,
                  color: mint)),
          const SizedBox(width: 10),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text('${m.metadata['name'] ?? 'A2 Lite'}',
                    style: const TextStyle(fontSize: 18)),
                Text(
                    '${creatorName(m)} · ${m.metadata['license'] ?? 'See source license'}',
                    style:
                        const TextStyle(fontSize: 12, color: Colors.white60)),
              ])),
          TextButton(
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        await selectCapture(m);
                        if (mounted) setState(() => tab = 0);
                      }),
              child: Text(
                  rig.modelSha256 == m.sha256Hex ? 'Selected' : 'Use capture')),
          IconButton(
              tooltip: 'Remove saved capture',
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        if (onboard.slots
                            .any((r) => r.modelSha256 == m.sha256Hex)) {
                          throw StateError(
                              'This capture is used by a colored preset. Choose a different capture there before removing it.');
                        }
                        setState(() => captures.remove(m.sha256Hex));
                        await persist();
                      }),
              icon: const Icon(Icons.delete_outline, size: 20)),
        ])),
    ]);
  }

  Future<void> scan() async {
    if (!native) {
      setState(() => status =
          'Open NAM Plug for Mac to connect over USB. This browser shows the editor and library.');
      return;
    }
    final found = await device.devices();
    if (mounted) {
      setState(() {
        devices = found;
        status = found.isEmpty
            ? 'No plug found. Connect USB or open Bluetooth, then refresh.'
            : 'Select your plug to read its status.';
      });
    }
  }

  Future<void> inspect(int source) async {
    setState(() {
      hardware = null;
      selectedSource = null;
    });
    final result = await device.inspect(source);
    if (mounted) {
      setState(() {
        hardware = result;
        selectedSource = source;
        status = result['compatible'] == true
            ? result['modelTransfer'] == true
                ? result['listeningSupported'] == true
                    ? 'Connected. Choose a capture; effects and signal-chain changes update the plug automatically.'
                    : 'Connected. Select a capture in the NAM block and send it for a silent test.'
                : 'Connected to ${result['identity']}. Status read only; audio stays muted.'
            : 'Device reports ${result['identity']}. No custom commands were sent.';
      });
      if (hasPresetBank) {
        observedPreset = null;
        plugPresets.clear();
        await readOnboardBank();
        if (!onboard.dirty[onboard.selected] &&
            !pendingControls &&
            !pendingModel) {
          await readChainFromPlug();
        }
        return;
      }
      if (widget.autoConnect && canTransfer) {
        final words = result['words'] as List?;
        if (!autoReloadBlocked &&
            model != null &&
            words?.length == 12 &&
            words![4] == 0 &&
            (pendingModel || words[5] == 0)) {
          await sendModel();
        } else if (hasStockChain) {
          await readChainFromPlug();
          if (pendingControls) await sendStockControls();
        }
      }
    }
  }

  Future<void> sendModel() async {
    autoReloadBlocked = false;
    final capture = model, source = selectedSource;
    if (!canTransfer || capture == null || source == null) {
      throw StateError(
          'Connect link firmware and choose an A2 Lite capture first.');
    }
    if (captureIncludesCabinet(capture)) {
      setState(
          () => rig.blocks.singleWhere((b) => b.slot == 'cab').enabled = false);
      await persist();
    }
    await persist();
    setState(() {
      transferProgress = 0;
      status = 'Sending capture. Output remains silent.';
    });
    try {
      if (hasListening) await device.setListening(source, false);
      await TransferClient(PlugModelTransport(device, source)).upload(capture,
          progress: (done, total) {
        if (mounted) setState(() => transferProgress = done / total);
      });
      final result = await device.inspect(source);
      final words = result['words'] as List?;
      if (!mounted) return;
      setState(() => hardware = result);
      if (!const [
            'NAMLNK01',
            'NAMLNK02',
            'NAMLNK03',
            'NAMLNK04',
            'NAMLNK05',
            'NAMLNK06',
            'NAMLNK07',
            'NAMLNK08',
            'NAMLNK09',
            'NAMLNK10',
            'NAMLNK11',
            'NAMLNK12',
            'NAMLNK13',
            'NAMLNK14',
            'NAMLNK15',
            'NAMLNK16'
          ].contains(result['identity']) ||
          words?.length != 12 ||
          words![4] != 0 ||
          words[5] != capture.checksum ||
          words[9] != 1) {
        throw StateError(
            'Transfer finished, but the plug did not confirm the capture is running. Check Plug status.');
      }
      if (captureIncludesCabinet(capture) && hasStockChain) {
        final cabinet = await device.setCabinetBypassed(source, true);
        if (cabinet['controlsVerified'] != true) {
          throw StateError('The plug did not confirm cabinet bypass.');
        }
        final checked = await device.inspect(source);
        final state = checked['words'] as List?;
        if (checked['identity'] != result['identity'] ||
            state?.length != 12 ||
            state![4] != 0 ||
            state[5] != capture.checksum ||
            state[9] != 1) {
          throw StateError('Check Plug status before using the new capture.');
        }
        if (mounted) setState(() => hardware = checked);
      }
      if (hasStockChain) await sendStockControls();
      if (!mounted) return;
      pendingModel = false;
      setState(() => status = hasListening
          ? '${capture.metadata['name'] ?? 'A2 Lite'} is loaded. Choose Listen on plug when ready; output is muted.'
          : '${capture.metadata['name'] ?? 'A2 Lite'} is running on the plug. Output is silent; resend after a restart.');
    } catch (_) {
      autoReloadBlocked = true;
      if (hasListening) {
        try {
          await device.setListening(source, false);
        } catch (_) {}
      }
      if (mounted) {
        setState(() {
          hardware = null;
          selectedSource = null;
        });
      }
      rethrow;
    } finally {
      if (mounted) setState(() => transferProgress = null);
    }
  }

  Future<void> setListening(bool enabled) async {
    final source = selectedSource;
    final expectedChecksum = selectedCaptureChecksum;
    final expectedIdentity = hardware?['identity'];
    if (!hasListening || source == null || (enabled && !loadedAndHealthy)) {
      throw StateError('Load a model on the listening firmware first.');
    }
    final result = await device.setListening(source, enabled);
    final confirmed = result['words'] as List?;
    if (enabled &&
        (result['identity'] != expectedIdentity ||
            expectedChecksum == null ||
            confirmed?.length != 12 ||
            confirmed![5] != expectedChecksum ||
            confirmed[4] != 0 ||
            confirmed[10] != 0 ||
            confirmed[9] != 1)) {
      final muted = await device.setListening(source, false);
      if (mounted) setState(() => hardware = muted);
      throw StateError(
          'The loaded capture changed. Reload your selection before listening.');
    }
    if (!mounted) return;
    setState(() {
      hardware = result;
      status = enabled
          ? 'Listening enabled on the plug. Mac audio is unchanged.'
          : 'Plug output muted.';
    });
  }

  Future<void> setOutputBuffer(int samples) async {
    final source = selectedSource;
    if (source == null ||
        !const [
          'NAMLNK09',
          'NAMLNK10',
          'NAMLNK11',
          'NAMLNK12',
          'NAMLNK13',
          'NAMLNK14',
          'NAMLNK15',
          'NAMLNK16'
        ].contains(hardware?['identity']) ||
        !const [8, 16, 32].contains(samples)) {
      throw StateError('Connect NAMLNK09 to adjust output buffering.');
    }
    try {
      final result = await device.setOutputBuffer(source, samples);
      if (!const [
            'NAMLNK09',
            'NAMLNK10',
            'NAMLNK11',
            'NAMLNK12',
            'NAMLNK13',
            'NAMLNK14',
            'NAMLNK15',
            'NAMLNK16'
          ].contains(result['identity']) ||
          (result['audioBuffer'] as Map?)?['samples'] != samples ||
          (result['listening'] as Map?)?['enabled'] != false) {
        throw StateError('The plug did not confirm its buffer and mute state.');
      }
      if (mounted) {
        setState(() {
          hardware = result;
          status =
              'Output buffer set to $samples samples. Output is muted; choose Listen on plug when ready.';
        });
      }
    } catch (_) {
      try {
        final muted = await device.setListening(source, false);
        if (mounted) setState(() => hardware = muted);
      } catch (_) {
        if (mounted) {
          setState(() {
            hardware = null;
            selectedSource = null;
          });
        }
      }
      rethrow;
    }
  }

  Widget get latencySettings {
    final adjustable = const [
          'NAMLNK09',
          'NAMLNK10',
          'NAMLNK11',
          'NAMLNK12',
          'NAMLNK13',
          'NAMLNK14',
          'NAMLNK15',
          'NAMLNK16'
        ].contains(hardware?['identity']) &&
        hardware?['audioBuffer'] is Map &&
        selectedSource != null;
    final samples =
        adjustable ? (hardware!['audioBuffer'] as Map)['samples'] as int : 8;
    return card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Latency & buffer', style: TextStyle(fontSize: 20)),
      const SizedBox(height: 12),
      DropdownButtonFormField<int>(
        key: const ValueKey('output-buffer'),
        value: samples,
        decoration: const InputDecoration(labelText: 'Output buffer'),
        items: const [
          DropdownMenuItem(
              value: 8, child: Text('8 samples · 0.17 ms · Lowest')),
          DropdownMenuItem(value: 16, child: Text('16 samples · 0.33 ms')),
          DropdownMenuItem(value: 32, child: Text('32 samples · 0.67 ms')),
        ],
        onChanged: adjustable && !busy
            ? (value) {
                if (value != null) perform(() => setOutputBuffer(value));
              }
            : null,
      ),
      const SizedBox(height: 10),
      Text(adjustable
          ? hasPresetBank
              ? 'Confirmed on plug. Changing the buffer mutes output. Save to plug keeps this setting with the selected preset.'
              : 'Confirmed on plug. Changing the buffer mutes output; restart restores 8 samples.'
          : hardware?['identity'] == 'NAMLNK08'
              ? 'NAMLNK08 uses a fixed 8-sample buffer. NAMLNK09 adds this control.'
              : 'Connect a plug running NAMLNK09 or newer to adjust this setting.'),
      const SizedBox(height: 12),
      const Text('Sample rate: 48 kHz · matched to the NAM capture'),
      const SizedBox(height: 8),
      const Text(
          '8 samples matches NAMLNK08. Larger values add output delay for comparison; they do not increase processing capacity. Stock effects still process 8 samples at a time.'),
      const SizedBox(height: 8),
      const Text(
          'These times describe output buffering, not total guitar-to-headphone latency. Total latency has not been measured. USB controls the plug; the Mac does not process your guitar audio.',
          style: TextStyle(fontSize: 12, color: Colors.white60)),
    ]));
  }

  Widget get listeningButton => FilledButton.icon(
      key: const ValueKey('plug-listening'),
      onPressed: busy || (!listening && !loadedAndHealthy)
          ? null
          : () => perform(() => setListening(!listening)),
      icon: Icon(listening ? Icons.volume_off_outlined : Icons.headphones),
      label: Text(listening ? 'Mute plug' : 'Listen on plug'));

  Widget get listeningControls =>
      card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(
            spacing: 12,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              listeningButton,
              Text(listening
                  ? 'Listening enabled · reduced starting level'
                  : 'Plug output muted'),
            ]),
        const SizedBox(height: 10),
        const Text(
            'Connect headphones to the plug and start with its volume low. Loading a capture stops listening.',
            style: TextStyle(color: Colors.white60, fontSize: 12)),
        const SizedBox(height: 6),
        const Text(
            'Experimental: demanding effect combinations may mute the plug and require a restart.',
            style: TextStyle(color: Colors.white60, fontSize: 12)),
      ]));

  Widget get devicePage {
    final words = (hardware?['words'] as List?) ?? [];
    final timing = hardware?['irqTiming'] as Map?;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Your plug',
          style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      const Text(
          'Connect the plug to this Mac over USB in normal mode. Read its connection and processing status here.'),
      const SizedBox(height: 20),
      Wrap(spacing: 10, runSpacing: 10, children: [
        FilledButton.icon(
            onPressed: busy ? null : () => perform(scan),
            icon: const Icon(Icons.refresh),
            label: const Text('Find plug')),
        OutlinedButton.icon(
            onPressed: busy
                ? null
                : () => perform(() async {
                      if (!native) {
                        setState(() => status =
                            'Pair Bluetooth MIDI in Audio MIDI Setup on the Mac, then refresh. USB connects directly.');
                        return;
                      }
                      await device.bluetooth();
                    }),
            icon: const Icon(Icons.bluetooth),
            label: const Text('Bluetooth'))
      ]),
      const SizedBox(height: 16),
      for (final d in devices)
        card(ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('${d['name']}'),
            subtitle: const Text('Read identity and test status'),
            trailing: const Icon(Icons.chevron_right),
            onTap: busy
                ? null
                : () => perform(() => inspect(d['source'] as int)))),
      if (hardware != null)
        card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${hardware!['identity']}',
              style: const TextStyle(fontSize: 24)),
          const Text('Live device read · no audio stream'),
          if (words.length == 12 && hardware!['modelTransfer'] == true) ...[
            const SizedBox(height: 16),
            Text(
                'Capture: ${words[9] == 1 ? (hasListening ? 'running' : 'running silently') : words[4] != 0 ? 'stopped after a test fault' : 'waiting for upload'}'),
            Text('Model changes: ${words[6]} · processed blocks: ${words[7]}'),
            Text(
                'Faults: ${words[4]} · peak processing timer: ${words[8]} ticks'),
            if (timing != null) ...[
              const SizedBox(height: 10),
              Text(timing['usable'] == true
                  ? 'Audio callback: peak ${timing['maximumCycles']} raw counter cycles'
                  : 'Audio callback timing: no clean measurement available'),
              Text(
                  'Accepted: ${timing['accepted']} · rejected: ${timing['rejected']}'),
              const Text(
                  'Diagnostic counter only; real-time performance still needs verification.',
                  style: TextStyle(color: Colors.white60)),
            ],
            const SizedBox(height: 10),
            Text(
                hasPresetBank
                    ? 'Choose a color to recall its saved capture and effects. Save to plug keeps edits after power off. Connecting reads the active preset without replacing it.'
                    : 'Choose a capture in the NAM block to load it. Reconnecting reloads your saved selection if the plug restarted.',
                style: const TextStyle(color: Colors.white60)),
          ],
          if (words.length == 62) ...[
            const SizedBox(height: 16),
            Text(
                'Test phase: ${words[17] == 2 ? 'completed' : words[17] == 1 ? 'running' : 'waiting or stopped'}'),
            Text('Processed blocks: ${words[8]}'),
            Text('Peak body timer: ${words[25]} ticks'),
            Text(
                'Input peak: ${(words[59] / 2147483648 * 100).toStringAsFixed(2)}% of full scale'),
            const SizedBox(height: 10),
            const Text(
                'This installed test build exposes read-only status. Model and chain uploads require the next firmware protocol.',
                style: TextStyle(color: Colors.white60))
          ]
        ])),
      if (hasListening) listeningControls,
      if (!hasListening)
        card(const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Current hardware milestone',
                  style: TextStyle(fontSize: 18)),
              SizedBox(height: 10),
              Text(
                  'A2 Lite processed live guitar input. Two 30-second tests and a normal restart passed. These are saved test results, not a live connection indicator.'),
              SizedBox(height: 10),
              Text(
                  'Custom firmware remains silent. The controller does not enable audio.',
                  style: TextStyle(color: mint))
            ]))
    ]);
  }

  Future<void> checkUpdate() async {
    final file = await openFile(acceptedTypeGroups: const [
      XTypeGroup(
          label: 'NAM Plug release manifest',
          extensions: ['json'],
          uniformTypeIdentifiers: ['public.json'])
    ]);
    if (file == null) return;
    if (await file.length() > 32768) {
      throw const FormatException('Manifest too large');
    }
    final j = jsonDecode(await file.readAsString());
    if (j is! Map ||
        j['schema'] != 'nam-plug-release-1' ||
        j['target'] != 'NUX-MP3' ||
        j['firmware'] is! Map) {
      throw const FormatException('Wrong target or release format');
    }
    final f = j['firmware'];
    if (f['sha256'] is! String ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(f['sha256']) ||
        f['identity'] is! String ||
        f['bytes'] is! int) {
      throw const FormatException('Incomplete firmware identity');
    }
    if (mounted) {
      setState(() => updateSummary =
          '${f['identity']} · ${f['bytes']} bytes\nManifest parsed. Binary verification and installation take place in the Mac updater tool.');
    }
  }

  Widget get updates =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Firmware & workspace',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        latencySettings,
        card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Silent local check', style: TextStyle(fontSize: 20)),
          const SizedBox(height: 8),
          const Text(
              'A synthetic zero-output fixture checks capture storage and favorites. It is not a guitar tone.'),
          TextButton(
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        await selectCapture(LiteModel.fixture());
                      }),
              child: const Text('Add silent test fixture')),
        ])),
        card(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('NAM Plug updater', style: TextStyle(fontSize: 21)),
          const SizedBox(height: 8),
          const Text(
              'Review a release manifest here. The Mac companion verifies the image, target and restore file before handing installation to the tested NUX loader.'),
          const SizedBox(height: 12),
          OutlinedButton.icon(
              onPressed: busy ? null : () => perform(checkUpdate),
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('Review release')),
          if (updateSummary != null)
            Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(updateSummary!)),
          const SizedBox(height: 12),
          const Text(
              'Model transfer and firmware flashing are separate operations. This app does not flash the plug.',
              style: TextStyle(fontSize: 12, color: Colors.white54))
        ])),
        card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('TONE3000 connection', style: TextStyle(fontSize: 20)),
          const SizedBox(height: 8),
          const Text(
              'Sign in to browse tones, your favorites and downloads. This Mac remembers your session securely in Keychain.'),
          const SizedBox(height: 12),
          FilledButton.icon(
              onPressed: busy ? null : () => perform(openToneBrowser),
              icon: const Icon(Icons.library_music_outlined),
              label: const Text('Open TONE3000')),
          if (!toneConfigured)
            const Padding(
                padding: EdgeInsets.only(top: 10),
                child: Text(
                    'Sign-in is waiting for NAM Plug’s one-time app registration.',
                    style: TextStyle(color: Colors.white60))),
          if (!bundledToneConnection)
            ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Developer setup'),
                children: [
                  const Text(
                      'For builds without an included app registration. Use only the publishable ID, never a secret key. Register mighty-nam://oauth/callback with TONE3000.'),
                  TextButton.icon(
                      onPressed: () => launchUrl(
                          Uri.parse('https://www.tone3000.com/settings'),
                          mode: LaunchMode.externalApplication),
                      icon: const Icon(Icons.open_in_new),
                      label: const Text('Open TONE3000 account settings')),
                  TextFormField(
                      initialValue: toneClientIdDraft,
                      decoration: const InputDecoration(
                          labelText: 'Publishable client ID',
                          hintText: 't3k_pub_…'),
                      onChanged: (value) => toneClientIdDraft = value),
                  TextButton(
                      onPressed: busy
                          ? null
                          : () => perform(() async {
                                final next = toneClientIdDraft.trim();
                                if (next.isNotEmpty &&
                                    !next.startsWith('t3k_pub_')) {
                                  throw const FormatException(
                                      'Use a publishable client ID');
                                }
                                if (next != toneClientId) {
                                  api?.close();
                                  setState(() {
                                    api = null;
                                    toneClientId = next;
                                  });
                                }
                                await persist();
                                if (mounted) {
                                  setState(
                                      () => status = 'App connection saved.');
                                }
                              }),
                      child: const Text('Save app connection'))
                ])
        ])),
        card(const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Open project', style: TextStyle(fontSize: 20)),
              SizedBox(height: 8),
              Text(
                  'Controller source, preset format, effect extension API, portable DSP and updater tools are editable. The factory loader remains a separate component. Custom effects are compiled into firmware; arbitrary code is not downloaded into the running audio interrupt.'),
              SizedBox(height: 10),
              Text(
                  'Based on Mightier Amp by Dian Iliev (Tuntorius), MIT license.',
                  style: TextStyle(fontSize: 12, color: Colors.white54))
            ]))
      ]);
  Widget get pageContent => Center(
      child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1180),
          child: ListView(
              padding: const EdgeInsets.fromLTRB(28, 24, 28, 24),
              children: [
                tab == 0
                    ? chain
                    : tab == 1
                        ? library
                        : tab == 2
                            ? devicePage
                            : updates,
                const SizedBox(height: 22),
                if (busy || restoring) const LinearProgressIndicator(),
                const SizedBox(height: 8),
                Text(status,
                    key: const ValueKey('status'),
                    style: const TextStyle(color: Colors.white60, fontSize: 12))
              ])));

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, size) {
        final desktop = size.maxWidth >= 850;
        return Scaffold(
            appBar: AppBar(
                backgroundColor: ink,
                surfaceTintColor: Colors.transparent,
                title: const Text('NAM Plug',
                    style:
                        TextStyle(fontWeight: FontWeight.w600, fontSize: 18)),
                actions: [
                  TextButton.icon(
                      key: const ValueKey('open-tuner'),
                      onPressed: busy || restoring || !native
                          ? null
                          : () => perform(openTuner),
                      icon: const Icon(Icons.graphic_eq, size: 18),
                      label: const Text('Tuner')),
                  const SizedBox(width: 18),
                  const Icon(Icons.volume_off_outlined,
                      size: 16, color: Colors.white54),
                  Padding(
                      padding: const EdgeInsets.only(left: 8, right: 24),
                      child: Center(
                          child: Text(
                              hardware?['compatible'] == true
                                  ? canTransfer
                                      ? (hasListening
                                          ? (listening
                                              ? 'Plug listening enabled'
                                              : 'Connected · muted')
                                          : 'Connected · silent')
                                      : 'Connected · status only'
                                  : 'Not connected',
                              style: const TextStyle(
                                  fontSize: 12, color: Colors.white60))))
                ]),
            body: desktop
                ? Row(children: [
                    NavigationRail(
                        backgroundColor: ink,
                        extended: true,
                        minExtendedWidth: 156,
                        useIndicator: true,
                        indicatorColor: const Color(0xff30363e),
                        selectedIndex: tab,
                        onDestinationSelected: (value) =>
                            setState(() => tab = value),
                        destinations: const [
                          NavigationRailDestination(
                              icon: Icon(Icons.route_outlined),
                              label: Text('Signal chain')),
                          NavigationRailDestination(
                              icon: Icon(Icons.library_music_outlined),
                              label: Text('Captures')),
                          NavigationRailDestination(
                              icon: Icon(Icons.cable), label: Text('Plug')),
                          NavigationRailDestination(
                              icon: Icon(Icons.settings_outlined),
                              label: Text('Settings')),
                        ]),
                    const VerticalDivider(width: 1, color: Color(0xff303338)),
                    Expanded(child: pageContent)
                  ])
                : pageContent,
            bottomNavigationBar: desktop
                ? null
                : NavigationBar(
                    height: 64,
                    backgroundColor: ink,
                    indicatorColor: const Color(0xff30363e),
                    selectedIndex: tab,
                    onDestinationSelected: (value) =>
                        setState(() => tab = value),
                    destinations: const [
                        NavigationDestination(
                            icon: Icon(Icons.route_outlined),
                            label: 'Signal chain'),
                        NavigationDestination(
                            icon: Icon(Icons.library_music_outlined),
                            label: 'Captures'),
                        NavigationDestination(
                            icon: Icon(Icons.cable), label: 'Plug'),
                        NavigationDestination(
                            icon: Icon(Icons.settings_outlined),
                            label: 'Settings')
                      ]));
      });
}
