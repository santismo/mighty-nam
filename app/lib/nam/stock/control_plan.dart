import 'rig.dart';

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
    if (supportedTypes.keys.any((slot) => stages[slot] == cc)) return cc;
    for (final range in ranges) {
      if (cc >= range[0] && cc <= range[1]) return range[2] + cc - range[0];
    }
    return null;
  }

  /// Import the live chain without discarding remembered inactive effect settings.
  static HybridRig readRig(HybridRig previous, List<int> preset) {
    StockControlPlan.fromSnapshot(
        preset); // Validate the complete response before changing UI state.
    final next = HybridRig.parse(previous.encode());
    for (final block in next.blocks) {
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
    next.blocks.sort((a, b) => order
        .indexOf(stages[a.slot]!)
        .compareTo(order.indexOf(stages[b.slot]!)));
    return HybridRig.parse(next.encode());
  }

  factory StockControlPlan.fromRig(HybridRig rig) {
    // Check stored values before translating into physical writes.
    final checked = HybridRig.parse(rig.encode());
    final controls = <List<int>>[];
    for (final block in checked.blocks.where((b) => b.slot != 'nam')) {
      final effect = block.effect!;
      if (effect.nuxIndex > supportedTypes[block.slot]!) {
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
        controls, checked.blocks.map((b) => stages[b.slot]!).toList());
  }
  factory StockControlPlan.fromSnapshot(List<int> preset) {
    if (preset.length != 128 || preset.any((v) => v < 0 || v > 127)) {
      throw const FormatException('Invalid stock control snapshot');
    }
    final controls = <List<int>>[];
    for (final slot in supportedTypes.keys) {
      final id = stages[slot]!, value = preset[stages[slot]!];
      if ((value & 63) < 1 || (value & 63) > supportedTypes[slot]!) {
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
