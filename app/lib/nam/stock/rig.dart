import 'dart:convert';
import 'catalog.dart';

const slotNames = {
  'gate': 'Gate',
  'comp': 'Compressor',
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
  int choice = 0;
  bool enabled = true;
  RigBlock(this.slot) : choices = slot == 'nam' ? [] : stockEffects(slot);
  Processor? get effect => choices.isEmpty ? null : choices[choice];
  String get name => slotNames[slot]!;
  Map<String, dynamic> toJson() => {
        'slot': slot,
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
        j['blocks'].length != slotNames.length ||
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
      if (b.slot == 'nam') {
        if (item['choice'] != null || item['settings'].isNotEmpty) {
          throw const FormatException('Invalid NAM block');
        }
      } else {
        b.choice = b.choices.indexWhere((e) => e.nuxIndex == item['choice']);
        if (b.choice < 0 || item['settings'].length != b.choices.length) {
          throw const FormatException('Unknown stock effect');
        }
        for (final e in b.choices) {
          final values = item['settings']['${e.nuxIndex}'];
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
    return HybridRig(j['name'], blocks, modelSha256: j['model_sha256']);
  }
}
