import 'dart:convert';
import 'dart:typed_data';
import 'package:collection/collection.dart';
import 'package:crypto/crypto.dart';
import 'topology.dart';

int crc32(List<int> bytes) {
  var crc = 0xffffffff;
  for (final byte in bytes) {
    crc ^= byte;
    for (var bit = 0; bit < 8; bit++) {
      crc = (crc >>> 1) ^ ((crc & 1) != 0 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) & 0xffffffff;
}

/// Validated model; byte buffers are returned as copies so validation cannot
/// silently be invalidated by a caller. No conversion from other topologies.
class LiteModel {
  static const weightCount = 1871,
      slotBytes = 8192,
      maxJsonBytes = 4 * 1024 * 1024;
  final Uint8List _slot;
  final Map<String, dynamic> metadata;
  LiteModel._(this._slot, Map<String, dynamic> metadata)
      : metadata = Map.unmodifiable(metadata);
  Uint8List get slot => Uint8List.fromList(_slot);
  String get sha256Hex => sha256.convert(_slot).toString();
  int get checksum => crc32(_slot);

  /// Restore a previously validated fixed-topology slot from the local library.
  /// Revalidate bytes and their identity before making them selectable.
  factory LiteModel.restore(Map<String, dynamic> record) {
    if (record['slot'] is! String ||
        record['slot'].length > 12000 ||
        record['metadata'] is! Map<String, dynamic> ||
        jsonEncode(record['metadata']).length > 8192) {
      throw const FormatException('Invalid saved capture');
    }
    final bytes = base64Decode(record['slot']);
    if (!validSlot(bytes) ||
        sha256.convert(bytes).toString() != record['sha256']) {
      throw const FormatException('Saved capture failed integrity check');
    }
    return LiteModel._(Uint8List.fromList(bytes), record['metadata']);
  }

  Map<String, dynamic> toRecord() => {
        'slot': base64Encode(_slot),
        'sha256': sha256Hex,
        'metadata': metadata,
      };

  factory LiteModel.parse(List<int> bytes,
      {Map<String, dynamic> provenance = const {}}) {
    if (bytes.length > maxJsonBytes)
      throw const FormatException('Model file is too large');
    final decoded = jsonDecode(utf8.decode(bytes));
    if (decoded is! Map<String, dynamic>)
      throw const FormatException('Expected a NAM model');
    Map<String, dynamic> selected = decoded;
    if (decoded['architecture'] == 'SlimmableContainer') {
      if (decoded['version'] != '0.7.0')
        throw const FormatException('Unsupported NAM container version');
      final config = decoded['config'];
      final submodels = config is Map ? config['submodels'] : null;
      if (submodels is! List) throw const FormatException('Missing submodels');
      final matches = <Map<String, dynamic>>[];
      for (final submodel in submodels) {
        if (submodel is! Map || submodel['model'] is! Map<String, dynamic>)
          continue;
        final model = Map<String, dynamic>.from(submodel['model']);
        if (!model.containsKey('sample_rate'))
          model['sample_rate'] = decoded['sample_rate'];
        try {
          _validate(model);
          matches.add(model);
        } on FormatException {/* Other sizes are not supported. */}
      }
      if (matches.length != 1)
        throw const FormatException(
            'Need exactly one compatible A2 Lite submodel');
      selected = matches.single;
    }
    _validate(selected);
    final slot = Uint8List(slotBytes)..fillRange(0, slotBytes, 0xff);
    final view = ByteData.sublistView(slot);
    final weights = selected['weights'] as List;
    for (var i = 0; i < weightCount; i++) {
      view.setFloat32(
          32 + i * 4, (weights[i] as num).toDouble(), Endian.little);
    }
    final header = [
      0x3241504d,
      1,
      48000,
      weightCount,
      weightCount * 4,
      crc32(slot.sublist(32, 32 + weightCount * 4)),
      1,
      0
    ];
    for (var i = 0; i < header.length; i++) {
      view.setUint32(i * 4, header[i], Endian.little);
    }
    return LiteModel._(slot, {
      'nam_metadata': decoded['metadata'],
      ...provenance,
      'source_sha256': sha256.convert(bytes).toString(),
      'topology': 'a2-lite-fixed-v1',
      'sample_rate': 48000,
    });
  }

  static void _validate(Map<String, dynamic> model) {
    if (model['version'] != '0.7.0' ||
        model['architecture'] != 'WaveNet' ||
        model['sample_rate'] != 48000) {
      throw const FormatException('Requires NAM 0.7.0 WaveNet at 48 kHz');
    }
    if (model['config'] is! Map<String, dynamic>)
      throw const FormatException('Missing model configuration');
    final config = Map<String, dynamic>.from(model['config']);
    final scale = config.remove('head_scale');
    if (scale is! num ||
        !scale.isFinite ||
        !const DeepCollectionEquality().equals(config, liteTopology())) {
      throw const FormatException(
          'This model does not match the supported A2 Lite topology');
    }
    final weights = model['weights'];
    if (weights is! List ||
        weights.length != weightCount ||
        weights
            .any((w) => w is! num || !w.isFinite || w.abs() > 3.402823466e38)) {
      throw const FormatException('Requires 1871 finite float32 weights');
    }
    // NAM Core takes the actual output scale from the last weight, not JSON head_scale.
  }

  /// Synthetic zero-output fixture, never presented as a real guitar capture.
  factory LiteModel.fixture() => LiteModel.parse(
          utf8.encode(jsonEncode({
            'version': '0.7.0',
            'architecture': 'WaveNet',
            'sample_rate': 48000,
            'config': {...liteTopology(), 'head_scale': 1},
            'weights': List<double>.generate(
                weightCount, (i) => i == weightCount - 1 ? 1 : 0),
          })),
          provenance: {
            'name': 'Silent test model',
            'creator': 'Local synthetic fixture',
            'license': 'CC0-1.0'
          });
}

bool validSlot(Uint8List slot) {
  if (slot.length != LiteModel.slotBytes) return false;
  final b = ByteData.sublistView(slot);
  final expected = <int>[0x3241504d, 1, 48000, 1871, 7484];
  for (var i = 0; i < expected.length; i++) {
    if (b.getUint32(i * 4, Endian.little) != expected[i]) return false;
  }
  if (b.getUint32(24, Endian.little) != 1 ||
      b.getUint32(28, Endian.little) != 0 ||
      b.getUint32(20, Endian.little) != crc32(slot.sublist(32, 7516)))
    return false;
  for (var offset = 32; offset < 7516; offset += 4) {
    if (!b.getFloat32(offset, Endian.little).isFinite) return false;
  }
  return slot.skip(7516).every((byte) => byte == 0xff);
}
