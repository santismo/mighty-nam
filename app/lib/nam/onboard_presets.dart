import 'dart:convert';
import 'dart:typed_data';
import 'package:nam_link/nam_link.dart';
import 'stock/rig.dart';
import 'stock/control_plan.dart';

// Fixed Mighty Plug Pro channel colors, matching Mightier Amp's Pro mapping.
const presetColors = [
  0xff00ff00,
  0xfff0a00a,
  0xffdc0000,
  0xff2196f3,
  0xff82e1ff,
  0xffe778d7,
  0xffe1bee7
];
const presetColorNames = [
  'Green',
  'Orange',
  'Red',
  'Blue',
  'Cyan',
  'Pink',
  'Lilac'
];

class OnboardPresets {
  int selected = 0;
  final List<HybridRig> slots =
      List.generate(7, (i) => HybridRig.initial()..name = presetColorNames[i]);
  final List<bool> dirty = List.filled(7, false);
  final List<int> generations = List.filled(7, 0);
  void edit(HybridRig rig) {
    if (slots[selected].encode() != rig.encode()) {
      slots[selected] = HybridRig.parse(rig.encode());
      dirty[selected] = true;
    }
  }

  Map<String, dynamic> toJson() => {
        'schema': 1,
        'selected': selected,
        'slots': slots.map((r) => r.encode()).toList(),
        'dirty': dirty,
        'generations': generations
      };
  static OnboardPresets parse(dynamic value) {
    if (value is! Map ||
        value['schema'] != 1 ||
        value['selected'] is! int ||
        value['selected'] < 0 ||
        value['selected'] > 6 ||
        value['slots'] is! List ||
        value['slots'].length != 7 ||
        value['dirty'] is! List ||
        value['dirty'].length != 7 ||
        value['generations'] is! List ||
        value['generations'].length != 7) {
      throw const FormatException('Invalid seven-preset library');
    }
    final bank = OnboardPresets()..selected = value['selected'];
    for (var i = 0; i < 7; i++) {
      if (value['slots'][i] is! String ||
          value['dirty'][i] is! bool ||
          value['generations'][i] is! int ||
          value['generations'][i] < 0 ||
          value['generations'][i] > 0xffffffff) {
        throw const FormatException('Invalid preset');
      }
      bank.slots[i] = HybridRig.parse(value['slots'][i]);
      bank.dirty[i] = value['dirty'][i];
      bank.generations[i] = value['generations'][i];
    }
    return bank;
  }
}

class PresetSnapshot {
  final int slot, active, mask, generation, modelCrc, buffer;
  final String? modelSha;
  final String name;
  final List<int>? effects;
  bool get occupied => (mask & (1 << slot)) != 0;
  PresetSnapshot(this.slot, this.active, this.mask, this.generation,
      this.modelCrc, this.buffer, this.modelSha, this.name, this.effects);
  HybridRig rig(HybridRig previous) {
    final result = effects == null
        ? HybridRig.initial()
        : StockControlPlan.readRig(previous, effects!);
    result.name = name;
    result.modelSha256 = modelSha;
    return result;
  }
}

class PresetClient {
  final Future<Uint8List> Function(Uint8List) exchange;
  int nonce = DateTime.now().microsecondsSinceEpoch & 0x7fffffff;
  PresetClient(this.exchange);
  Future<PresetSnapshot> read(int slot) => _request(1, slot, Uint8List(0));
  Future<PresetSnapshot> recall(int slot) => _request(3, slot, Uint8List(0));
  Future<PresetSnapshot> save(
      int slot, LiteModel model, List<int> effects, String name, int buffer) {
    StockControlPlan.fromSnapshot(effects);
    final bytes = utf8.encode(name.trim());
    if (bytes.isEmpty ||
        bytes.length > 63 ||
        bytes.any((b) => b < 32 || b == 127)) {
      throw const FormatException(
          'Use a shorter preset name without control characters.');
    }
    if (![8, 16, 32].contains(buffer)) {
      throw const FormatException('Unsupported output buffer');
    }
    final body = Uint8List(112), words = ByteData(16);
    words.setUint32(0, model.checksum, Endian.little);
    words.setUint32(4, crc32(effects), Endian.little);
    words.setUint32(
        8, 1, Endian.little); // Saved presets play after standalone startup.
    words.setUint32(12, buffer, Endian.little);
    body.setRange(0, 16, words.buffer.asUint8List());
    for (var i = 0; i < 32; i++) {
      body[16 + i] =
          int.parse(model.sha256Hex.substring(2 * i, 2 * i + 2), radix: 16);
    }
    body.setRange(48, 48 + bytes.length, bytes);
    return _request(2, slot, body);
  }

  Future<PresetSnapshot> _request(int op, int slot, Uint8List body) async {
    if (slot < 0 || slot > 6) {
      throw const FormatException('Choose a preset from 1 to 7');
    }
    nonce = (nonce + 1) & 0xffffffff;
    if (nonce == 0) nonce = 1;
    final token = nonce,
        raw = Uint8List(20 + body.length),
        d = ByteData.sublistView(raw);
    d.setUint32(0, 0x3031504e, Endian.little);
    raw[4] = 1;
    raw[5] = op;
    raw[6] = slot;
    d.setUint32(8, token, Endian.little);
    d.setUint16(12, body.length, Endian.little);
    raw.setRange(16, 16 + body.length, body);
    d.setUint32(
        raw.length - 4, crc32(raw.sublist(0, raw.length - 4)), Endian.little);
    final reply = await exchange(raw);
    if (reply.length != 276) {
      throw const FormatException('Incomplete preset reply');
    }
    final r = ByteData.sublistView(reply);
    if (r.getUint32(0, Endian.little) != 0x3031504e ||
        reply[4] != 1 ||
        reply[5] != (op | 128) ||
        reply[6] != slot ||
        r.getUint32(8, Endian.little) != token ||
        r.getUint16(12, Endian.little) != 256 ||
        !(reply[14] < 7 || reply[14] == 255) ||
        reply[15] > 127 ||
        r.getUint32(272, Endian.little) != crc32(reply.sublist(0, 272))) {
      throw const FormatException('Preset reply did not match the request');
    }
    if (reply[7] != 0) {
      throw StateError(
          'The plug could not ${op == 2 ? 'save' : 'recall'} this preset (code ${reply[7]}). Previous saved copies are retained.');
    }
    final header = reply.sublist(16, 272), h = ByteData.sublistView(header);
    if ((reply[15] & (1 << slot)) == 0) {
      if (header.any((v) => v != 0)) {
        throw const FormatException('Invalid empty preset reply');
      }
      return PresetSnapshot(slot, reply[14], reply[15], 0, 0, 8, null,
          presetColorNames[slot], null);
    }
    if (h.getUint32(0, Endian.little) != 0x3142504e ||
        h.getUint32(4, Endian.little) != 1 ||
        h.getUint32(8, Endian.little) != slot ||
        h.getUint32(12, Endian.little) == 0 ||
        h.getUint32(20, Endian.little) > 1 ||
        ![8, 16, 32].contains(h.getUint32(24, Endian.little)) ||
        h.getUint32(28, Endian.little) != 0) {
      throw const FormatException('Unsupported preset metadata');
    }
    final nameBytes = header.sublist(64, 128), end = nameBytes.indexOf(0);
    if (end <= 0 || nameBytes.sublist(end).any((v) => v != 0)) {
      throw const FormatException('Invalid saved preset name');
    }
    final name = utf8.decode(nameBytes.sublist(0, end)),
        effects = header.sublist(128, 256);
    StockControlPlan.fromSnapshot(effects);
    return PresetSnapshot(
        slot,
        reply[14],
        reply[15],
        h.getUint32(12, Endian.little),
        h.getUint32(16, Endian.little),
        h.getUint32(24, Endian.little),
        header
            .sublist(32, 64)
            .map((v) => v.toRadixString(16).padLeft(2, '0'))
            .join(),
        name,
        effects);
  }
}
