import 'dart:convert';
import 'nam_tone.dart';
import 'catalog.dart';
import 'extra_fx.dart';

const slotNames = {
  'gate': 'Gate',
  'comp': 'Compressor',
  'fxa': 'FX A',
  'fxb': 'FX B',
  'drive': 'Drive',
  'nam': 'NAM',
  'cab': 'Cabinet',
  'eq': 'EQ',
  'mod': 'Modulation',
  'delay': 'Delay',
  'reverb': 'Reverb',
};

/// Editable hybrid rig. Deliberately distinct from the portable NPC1 program:
/// these are stock NUX effect definitions, not copies of their DSP algorithms.
class RigBlock {
  final String slot;
  final List<Processor> choices;
  List<int>? fxWire;
  int choice = 0;
  bool enabled = true;
  RigBlock(this.slot) : choices = slot == 'nam' ? [] : stockEffects(slot) {
    if (slot == 'fxb') choice = 1;
  }
  bool get extra => slot == 'fxa' || slot == 'fxb';
  Processor? get effect => choices.isEmpty ? null : choices[choice];
  bool get isAmp => extra && effect?.nuxIndex == 8;
  String get name => isAmp ? 'Amp' : slotNames[slot]!;
  String? get modelLabel => isAmp
      ? stockAmpNames[stockAmpIds.indexOf(effect!.parameters.first.midiValue)]
      : effect?.name;
  Map<String, dynamic> toJson() => {
        'slot': slot,
        if (extra && fxWire != null) 'fx_wire': fxWire,
        'enabled': enabled,
        'choice': effect?.nuxIndex,
        // Remember settings when switching between effect types.
        'settings': {
          for (final e in choices)
            '${e.nuxIndex}': e.parameters.map((p) => p.value).toList()
        },
      };
}

class HybridRig {
  String name;
  String? modelSha256;
  int masterVolume;
  int usbRecordGain = 48;
  List<int> namTone = neutralNamTone();
  final Set<String> visibleSlots = {};
  final List<RigBlock> blocks;
  HybridRig(this.name, this.blocks, {this.modelSha256, this.masterVolume = 50});
  factory HybridRig.initial() => HybridRig(
      'Untitled chain',
      slotNames.keys
          .map((slot) =>
              RigBlock(slot)..enabled = (slot == 'nam' || slot == 'cab'))
          .toList());
  List<int> fxConfig() {
    final config = defaultFx();
    for (var j = 0; j < 2; j++) {
      final b = blocks.singleWhere((b) => b.slot == (j == 0 ? 'fxa' : 'fxb'));
      final i = j * 16;
      if (b.fxWire != null) config.setRange(i, i + 16, b.fxWire!);
      config[i] = b.effect!.nuxIndex;
      config[i + 1] = b.enabled ? 1 : 0;
      config[i + 2] = blocks.indexOf(b);
      if (config[i] < 8) {
        for (var k = 10; k < 16; k++) config[i + k] = 0;
        if (b.fxWire?[0] == 8 && config[i] != 1) config[i + 3] = 12;
      }
      for (final p in b.effect!.parameters) {
        config[i + p.devicePresetIndex] = p.midiValue;
      }
    }
    validateFx(config);
    return config;
  }

  List<RigBlock> visibleBlocks({required bool activeOnly}) => activeOnly
      ? blocks.where((b) => b.enabled || visibleSlots.contains(b.slot)).toList()
      : blocks;

  RigBlock? get availableAmpSlot {
    if (!stockAmpsAvailable || availableStockAmpIds.isEmpty) return null;
    final visible = visibleBlocks(activeOnly: true);
    for (final block in blocks.where((b) => b.isAmp)) {
      return visible.contains(block) ? null : block;
    }
    for (final block in blocks.where((b) => b.extra && !visible.contains(b))) {
      return block;
    }
    return null;
  }

  RigBlock addAmpBlock() {
    final block = availableAmpSlot;
    if (block == null)
      throw StateError('Amp is already in the chain or no effect slot is free');
    if (!block.isAmp) {
      block.choice = block.choices.indexWhere((e) => e.nuxIndex == 8);
      block.fxWire = null;
      block.effect!.parameters.first.midiValue = availableStockAmpIds.first;
    }
    addBlock(block);
    return block;
  }

  void addBlock(RigBlock block) {
    if (!blocks.contains(block)) throw ArgumentError('Unknown block');
    if (block.enabled) return;
    block.enabled = true;
    visibleSlots.add(block.slot);
    reorder(blocks.indexOf(block), blocks.length - 1);
  }

  void bypassBlock(RigBlock block, bool enabled) {
    visibleSlots.add(block.slot);
    block.enabled = enabled;
  }

  void removeBlock(RigBlock block) {
    block.enabled = false;
    visibleSlots.remove(block.slot);
  }

  void replaceBlock(RigBlock before, RigBlock after) {
    if (!blocks.contains(before) ||
        !blocks.contains(after) ||
        visibleBlocks(activeOnly: true).contains(after)) {
      throw ArgumentError('Choose an available block');
    }
    final position = blocks.indexOf(before), enabled = before.enabled;
    removeBlock(before);
    after.enabled = enabled;
    visibleSlots.add(after.slot);
    reorder(blocks.indexOf(after), position);
  }

  void moveVisible(int oldIndex, int newIndex, {required bool activeOnly}) {
    final visible = visibleBlocks(activeOnly: activeOnly);
    reorder(
        blocks.indexOf(visible[oldIndex]), blocks.indexOf(visible[newIndex]));
  }

  void reorder(int oldIndex, int newIndex) {
    if (oldIndex < 0 ||
        oldIndex >= blocks.length ||
        newIndex < 0 ||
        newIndex >= blocks.length) {
      throw RangeError('Invalid block position');
    }
    blocks.insert(newIndex, blocks.removeAt(oldIndex));
  }

  String encode() => jsonEncode({
        'schema': 'nam-plug-hybrid-rig-1',
        'name': name,
        'model_sha256': modelSha256,
        'master_volume': masterVolume,
        'usb_record_gain': usbRecordGain,
        'nam_tone': namTone,
        'visible_slots': visibleSlots.toList(),
        'blocks': blocks.map((b) => b.toJson()).toList(),
      });
  factory HybridRig.parse(String text) {
    if (text.length > 65536) throw const FormatException('Chain is too large');
    final j = jsonDecode(text);
    if (j is! Map ||
        j['schema'] != 'nam-plug-hybrid-rig-1' ||
        j['name'] is! String ||
        j['name'].trim().isEmpty ||
        j['name'].length > 80 ||
        j['blocks'] is! List ||
        ![9, 11].contains(j['blocks'].length) ||
        (j['model_sha256'] != null &&
            (j['model_sha256'] is! String ||
                !RegExp(r'^[a-f0-9]{64}$').hasMatch(j['model_sha256'])))) {
      throw const FormatException('Invalid mighty-nam chain');
    }
    final volume = j['master_volume'] ?? 50;
    if (volume is! int || volume < 0 || volume > 100) {
      throw const FormatException('Invalid master volume');
    }
    final recording = j['usb_record_gain'] ?? 48;
    if (recording is! int || recording < 0 || recording > 96)
      throw const FormatException('Invalid USB recording gain');
    final seen = <String>{}, blocks = <RigBlock>[];
    for (final item in j['blocks']) {
      if (item is! Map ||
          !slotNames.containsKey(item['slot']) ||
          !seen.add(item['slot']) ||
          item['enabled'] is! bool ||
          item['settings'] is! Map) {
        throw const FormatException('Invalid or duplicate signal-chain block');
      }
      final b = RigBlock(item['slot'])..enabled = item['enabled'];
      if (b.extra && item['fx_wire'] != null) {
        if (item['fx_wire'] is! List ||
            (item['fx_wire'] as List).any((v) => v is! int) ||
            item['fx_wire'].length != 16) {
          throw const FormatException('Invalid FX state');
        }
        b.fxWire = List<int>.from(item['fx_wire']);
        final probe = defaultFx();
        probe.setRange(
            b.slot == 'fxa' ? 0 : 16, b.slot == 'fxa' ? 16 : 32, b.fxWire!);
        probe[2] = 2;
        probe[18] = 3;
        validateFx(probe);
      }
      if (b.slot == 'nam') {
        if (item['choice'] != null || item['settings'].isNotEmpty) {
          throw const FormatException('Invalid NAM block');
        }
      } else {
        b.choice = b.choices.indexWhere((e) => e.nuxIndex == item['choice']);
        if (b.choice < 0 ||
            (item['settings'] as Map)
                .keys
                .any((key) => !b.choices.any((e) => '${e.nuxIndex}' == key))) {
          throw const FormatException('Unknown stock effect');
        }
        for (final e in b.choices) {
          final values = item['settings']['${e.nuxIndex}'];
          // Older saved chains predate the new EQ choice; retain its neutral defaults.
          if (values == null &&
              b.slot == 'eq' &&
              e.nuxIndex == 4 &&
              item['choice'] != 4) {
            continue;
          }
          if (values == null &&
              b.extra &&
              e.nuxIndex == 8 &&
              item['choice'] != 8) continue;
          if (values is! List || values.length != e.parameters.length) {
            throw const FormatException('Invalid effect parameters');
          }
          for (var i = 0; i < values.length; i++) {
            final v = values[i], p = e.parameters[i], f = p.formatter;
            if (v is! num ||
                !v.isFinite ||
                (f is SwitchFormatter
                    ? !f.midiValues.contains(v)
                    : v < f.min || v > f.max)) {
              throw const FormatException('Effect parameter out of range');
            }
            p.value = v.toDouble();
          }
        }
      }
      blocks.add(b);
    }
    if (blocks.length == 9) {
      if (seen.contains('fxa') || seen.contains('fxb')) {
        throw const FormatException('Incomplete chain');
      }
      blocks.insertAll(2,
          [RigBlock('fxa')..enabled = false, RigBlock('fxb')..enabled = false]);
    }
    final tone = List<int>.from(j['nam_tone'] ?? neutralNamTone());
    validateNamTone(tone);
    return HybridRig(j['name'], blocks,
        modelSha256: j['model_sha256'], masterVolume: volume)
      ..usbRecordGain = recording
      ..namTone = tone
      ..visibleSlots.addAll(List<String>.from(j['visible_slots'] ?? const [])
          .where(slotNames.containsKey));
  }
}
