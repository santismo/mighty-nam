import 'rig.dart';
import 'extra_fx.dart';
import 'nam_tone.dart';

/// RAM-only V1.5.6 settings. The silent NAMLNK01 audio hook runs NAM alone;
/// the stock settings and order can be verified independently of stock DSP.
/// Excludes NAM's retired amplifier controls, preset saves and all audio routing.
class StockControlPlan {
  final List<List<int>> controls;
  final List<int> order;
  StockControlPlan._(this.controls, this.order);
  static const stages = {
    'gate': 5,
    'comp': 1,
    'drive': 2,
    'nam': 3,
    'cab': 9,
    'eq': 4,
    'mod': 6,
    'delay': 7,
    'reverb': 8,
  };
  static const supportedTypes = {
    'gate': 1,
    'comp': 3,
    'drive': 13,
    'cab': 34,
    'eq': 2,
    'mod': 13,
    'delay': 5,
    'reverb': 6,
  };
  static int maximumType(String slot, String? identity) =>
      slot == 'drive' && ['NAMLNK24', 'NAMLNK25'].contains(identity)
          ? 14
          : ['fxa', 'fxb'].contains(slot)
              ? (identity == null || supportsExtraFx(identity) ? 7 : 0)
              : slot == 'eq' &&
                      [
                        'NAMLNK14',
                        'NAMLNK15',
                        'NAMLNK16',
                        'NAMLNK17',
                        'NAMLNK18',
                        'NAMLNK19',
                        'NAMLNK20',
                        'NAMLNK21',
                        'NAMLNK22',
                        'NAMLNK23',
                        'NAMLNK24',
                        'NAMLNK25'
                      ].contains(identity)
                  ? 4
                  : supportedTypes[slot]!;
  static const ranges = [
    [13, 16, 15],
    [17, 22, 20],
    [31, 42, 36],
    [43, 46, 49],
    [47, 52, 54],
    [53, 60, 61],
    [61, 64, 70],
    [65, 70, 75]
  ];
  static int? presetIndex(int cc) {
    if (cc == 73) return 84;
    if (supportedTypes.keys.any((slot) => stages[slot] == cc)) return cc;
    for (final range in ranges) {
      if (cc >= range[0] && cc <= range[1]) return range[2] + cc - range[0];
    }
    return null;
  }

  /// Import the live chain without discarding remembered inactive effect settings.
  static HybridRig readRig(HybridRig previous, List<int> preset,
      {String? identity, List<int>? fx}) {
    StockControlPlan.fromSnapshot(preset,
        identity:
            identity); // Validate the complete response before changing UI state.
    final next = HybridRig.parse(previous.encode())..masterVolume = preset[84];
    next.usbRecordGain = [
              'NAMLNK21',
              'NAMLNK22',
              'NAMLNK23',
              'NAMLNK24',
              'NAMLNK25'
            ].contains(identity) &&
            preset[33] == 78 &&
            preset[34] == 2 &&
            preset[35] <= 96
        ? preset[35]
        : 48;
    next.namTone = ['NAMLNK21', 'NAMLNK22', 'NAMLNK23', 'NAMLNK24', 'NAMLNK25']
            .contains(identity)
        ? readNamTone(preset)
        : neutralNamTone();
    for (final block in next.blocks.where((b) => !b.extra)) {
      final id = stages[block.slot]!;
      block.enabled = (preset[id] & 64) == 0;
      if (block.slot == 'nam') continue;
      final choice =
          block.choices.indexWhere((e) => e.nuxIndex == (preset[id] & 63));
      if (choice < 0) {
        throw FormatException(
            'The plug uses an unrecognized ${block.name} type.');
      }
      block.choice = choice;
      for (final parameter in block.effect!.parameters) {
        parameter.midiValue = preset[parameter.devicePresetIndex];
      }
    }
    final order = preset.sublist(90, 99);
    final extras = next.blocks.where((b) => b.extra).toList();
    final positions = extras.map((b) => next.blocks.indexOf(b)).toList();
    next.blocks.removeWhere((b) => b.extra);
    next.blocks.sort((a, b) => order
        .indexOf(stages[a.slot]!)
        .compareTo(order.indexOf(stages[b.slot]!)));
    if (fx != null) {
      validateFx(fx);
      for (var j = 0; j < 2; j++) {
        final b = extras.singleWhere((b) => b.slot == (j == 0 ? 'fxa' : 'fxb'));
        final i = j * 16;
        b.fxWire = fx.sublist(i, i + 16);
        b.choice = fx[i] - 1;
        b.enabled = fx[i + 1] == 1;
        for (final p in b.effect!.parameters) {
          p.midiValue = fx[i + p.devicePresetIndex];
        }
      }
    }
    final placements = [
      for (var j = 0; j < 2; j++)
        (
          block: extras[j],
          at: fx == null ? positions[j] : fx[extras[j].slot == 'fxa' ? 2 : 18]
        )
    ];
    placements.sort((a, b) => a.at.compareTo(b.at));
    for (final p in placements) {
      next.blocks.insert(p.at, p.block);
    }
    return HybridRig.parse(next.encode());
  }

  factory StockControlPlan.fromRig(HybridRig rig, {String? identity}) {
    // Check stored values before translating into physical writes.
    final checked = HybridRig.parse(rig.encode());
    final controls = <List<int>>[
      [73, checked.masterVolume]
    ];
    for (final block
        in checked.blocks.where((b) => b.slot != 'nam' && !b.extra)) {
      final effect = block.effect!;
      if (effect.nuxIndex > maximumType(block.slot, identity)) {
        throw FormatException('${effect.name} requires newer stock firmware. '
            'Choose another ${block.name.toLowerCase()} for this plug.');
      }
      controls.add(
          [stages[block.slot]!, effect.nuxIndex | (block.enabled ? 0 : 64)]);
      for (final parameter in effect.parameters) {
        final value = parameter.midiValue;
        if (presetIndex(parameter.midiCC) != parameter.devicePresetIndex ||
            value < 0 ||
            value > 100) {
          throw FormatException('Unsupported control: ${parameter.name}');
        }
        controls.add([parameter.midiCC, value]);
      }
    }
    return StockControlPlan._(
        controls,
        checked.blocks
            .where((b) => !b.extra)
            .map((b) => stages[b.slot]!)
            .toList());
  }
  factory StockControlPlan.fromSnapshot(List<int> preset, {String? identity}) {
    if (preset.length != 128 || preset.any((v) => v < 0 || v > 127)) {
      throw const FormatException('Invalid stock control snapshot');
    }
    if (preset[84] > 100) throw const FormatException('Invalid master volume');
    final controls = <List<int>>[
      [73, preset[84]]
    ];
    for (final slot in supportedTypes.keys) {
      final id = stages[slot]!, value = preset[stages[slot]!];
      if ((value & 63) < 1 || (value & 63) > maximumType(slot, identity)) {
        throw const FormatException(
            'Snapshot contains unsupported effect types');
      }
      controls.add([id, value]);
    }
    for (final range in ranges) {
      for (var cc = range[0]; cc <= range[1]; cc++) {
        final value = preset[presetIndex(cc)!];
        if (value > 100) {
          throw const FormatException('Unsupported parameter value');
        }
        controls.add([cc, value]);
      }
    }
    final order = preset.sublist(90, 99);
    if (order.toSet().length != 9 || order.any((id) => id < 1 || id > 9)) {
      throw const FormatException('Invalid block order');
    }
    return StockControlPlan._(controls, order);
  }
}
