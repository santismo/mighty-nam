import 'dart:convert';
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
  String get name => slotNames[slot]!;
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
  final List<RigBlock> blocks;
  HybridRig(this.name, this.blocks, {this.modelSha256});
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
      for (final p in b.effect!.parameters) {
        config[i + p.devicePresetIndex] = p.midiValue;
      }
    }
    validateFx(config);
    return config;
  }

  List<RigBlock> visibleBlocks({required bool activeOnly}) =>
      activeOnly ? blocks.where((b) => b.enabled).toList() : blocks;

  void addBlock(RigBlock block) {
    if (!blocks.contains(block)) throw ArgumentError('Unknown block');
    if (block.enabled) return;
    block.enabled = true;
    reorder(blocks.indexOf(block), blocks.length - 1);
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
      throw const FormatException('Invalid NAM Plug chain');
    }
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
    return HybridRig(j['name'], blocks, modelSha256: j['model_sha256']);
  }
}
