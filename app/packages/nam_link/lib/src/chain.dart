import 'dart:convert';
import 'dart:typed_data';
import 'model.dart';

class ParameterSpec {
  final String name, unit;
  final double min, max, initial;
  const ParameterSpec(this.name, this.min, this.max, this.initial,
      [this.unit = '']);
}

class EffectSpec {
  final int id, color;
  final String key, name, category;
  final List<ParameterSpec> parameters;
  final bool repeatable;
  const EffectSpec(
      this.id, this.key, this.name, this.category, this.color, this.parameters,
      {this.repeatable = false});
}

const effectCatalog = <EffectSpec>[
  EffectSpec(0, 'gain', 'Gain', 'Utility', 0xff94a3b8,
      [ParameterSpec('Level', 0, 16, 1, '×')],
      repeatable: true),
  EffectSpec(1, 'drive', 'Overdrive', 'Drive', 0xffffb45b,
      [ParameterSpec('Drive', 1, 100, 3), ParameterSpec('Mix', 0, 1, .7)],
      repeatable: true),
  EffectSpec(2, 'distortion', 'Distortion', 'Drive', 0xffff766f,
      [ParameterSpec('Drive', 1, 100, 5), ParameterSpec('Mix', 0, 1, .5)],
      repeatable: true),
  EffectSpec(3, 'nam', 'NAM A2 Lite', 'Amp', 0xff64d8ff, []),
  EffectSpec(4, 'tremolo', 'Tremolo', 'Modulation', 0xffc7a0ff, [
    ParameterSpec('Rate', .1, 20, 3, 'Hz'),
    ParameterSpec('Depth', 0, 1, .35)
  ]),
  EffectSpec(5, 'chorus', 'Chorus', 'Modulation', 0xffb5a1ff, [
    ParameterSpec('Rate', .1, 20, .8, 'Hz'),
    ParameterSpec('Mix', 0, 1, .25)
  ]),
  EffectSpec(6, 'pitch', 'Pitch shift', 'Pitch', 0xffffdc78, [
    ParameterSpec('Shift', -12, 12, 7, 'st'),
    ParameterSpec('Mix', 0, 1, .4)
  ]),
  EffectSpec(7, 'delay', 'Delay', 'Time', 0xff7ae1b3, [
    ParameterSpec('Time', 1, 900, 320, 'ms'),
    ParameterSpec('Feedback', 0, .95, .35),
    ParameterSpec('Mix', 0, 1, .2)
  ]),
  EffectSpec(8, 'reverb', 'Reverb', 'Space', 0xffd29dff,
      [ParameterSpec('Decay', 0, .9, .65), ParameterSpec('Mix', 0, 1, .2)]),
];
EffectSpec effectById(int id) => effectCatalog.firstWhere((e) => e.id == id,
    orElse: () => throw const FormatException(
        'Unknown effect. Install its definition first.'));

class ChainBlock {
  final String id;
  final EffectSpec effect;
  final List<double> values;
  bool enabled;
  ChainBlock(this.id, this.effect, {List<double>? values, this.enabled = true})
      : values = values ??
            List.generate(
                3,
                (i) => i < effect.parameters.length
                    ? effect.parameters[i].initial
                    : 0);
  Map<String, dynamic> toJson() =>
      {'id': id, 'effect': effect.id, 'enabled': enabled, 'parameters': values};
}

class ChainPreset {
  String name;
  String? modelSha256;
  final List<ChainBlock> blocks;
  ChainPreset(this.name, this.blocks, {this.modelSha256});
  factory ChainPreset.initial() => ChainPreset('Midnight clean', [
        ChainBlock('input', effectById(0)),
        ChainBlock('drive', effectById(1)),
        ChainBlock('amp', effectById(3)),
        ChainBlock('chorus', effectById(5), enabled: false),
        ChainBlock('delay', effectById(7)),
        ChainBlock('space', effectById(8)),
      ]);
  void validate() {
    if (name.trim().isEmpty || name.length > 80 || blocks.length > 12)
      throw const FormatException('Use a name and at most 12 blocks.');
    if (modelSha256 != null &&
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(modelSha256!))
      throw const FormatException('Invalid model identity');
    final ids = <String>{}, stateful = <int>{};
    for (final b in blocks) {
      if (b.id.isEmpty ||
          b.id.length > 64 ||
          !ids.add(b.id) ||
          b.values.length != 3)
        throw const FormatException('Invalid or duplicate block');
      effectById(b.effect.id);
      if (!b.effect.repeatable && !stateful.add(b.effect.id))
        throw const FormatException(
            'One instance per stateful effect in this engine.');
      for (var i = 0; i < 3; i++) {
        final v = b.values[i];
        if (!v.isFinite)
          throw const FormatException('Parameters must be finite');
        if (i < b.effect.parameters.length) {
          final p = b.effect.parameters[i];
          if (v < p.min || v > p.max)
            throw FormatException('${p.name} is outside its range');
        } else if (v != 0)
          throw const FormatException('Unused parameters must be zero');
      }
    }
  }

  String encodeJson() {
    validate();
    return const JsonEncoder.withIndent('  ').convert({
      'schema': 'nam-plug-preset-1',
      'name': name,
      'sample_rate': 48000,
      'model_sha256': modelSha256,
      'blocks': blocks.map((b) => b.toJson()).toList()
    });
  }

  factory ChainPreset.parse(String source) {
    if (source.length > 32768) throw const FormatException('Preset too large');
    final j = jsonDecode(source);
    if (j is! Map ||
        j['schema'] != 'nam-plug-preset-1' ||
        j['sample_rate'] != 48000 ||
        j['name'] is! String ||
        j['blocks'] is! List ||
        j['blocks'].length > 12)
      throw const FormatException('Unsupported preset');
    final list = <ChainBlock>[];
    for (final b in j['blocks']) {
      if (b is! Map ||
          b['id'] is! String ||
          b['effect'] is! int ||
          b['enabled'] is! bool ||
          b['parameters'] is! List ||
          b['parameters'].length != 3 ||
          !(b['parameters'] as List).every((v) => v is num))
        throw const FormatException('Invalid block');
      list.add(ChainBlock(b['id'], effectById(b['effect']),
          enabled: b['enabled'],
          values: (b['parameters'] as List)
              .map((v) => (v as num).toDouble())
              .toList()));
    }
    if (j['model_sha256'] != null && j['model_sha256'] is! String)
      throw const FormatException('Invalid model identity');
    final p = ChainPreset(j['name'], list, modelSha256: j['model_sha256']);
    p.validate();
    return p;
  }

  /// Program for the portable C++ engine. Not a stock or NAMA2I01 command.
  Uint8List compile() {
    validate();
    final bytes = Uint8List(16 + 16 * blocks.length),
        d = ByteData.sublistView(bytes);
    d.setUint32(0, 0x3143504e, Endian.little);
    d.setUint16(4, 1, Endian.little);
    d.setUint16(6, blocks.length, Endian.little);
    d.setUint32(8, 48000, Endian.little);
    for (var i = 0; i < blocks.length; i++) {
      final b = blocks[i], o = 16 + 16 * i;
      d.setUint16(o, b.effect.id, Endian.little);
      d.setUint8(o + 2, b.enabled ? 1 : 0);
      for (var k = 0; k < 3; k++)
        d.setFloat32(o + 4 + 4 * k, b.values[k], Endian.little);
    }
    d.setUint32(12, crc32(bytes.sublist(16)), Endian.little);
    return bytes;
  }
}
