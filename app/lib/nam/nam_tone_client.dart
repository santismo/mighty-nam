import 'dart:typed_data';
import 'stock/nam_tone.dart';

class NamToneClient {
  final Future<Uint8List> Function(Uint8List) exchange;
  int nonce = DateTime.now().millisecondsSinceEpoch % 16383;
  NamToneClient(this.exchange);
  Future<List<int>> read() => request(0, 0);
  Future<List<int>> write(List<int> config, int active, int model) =>
      request(1, active, config: config, model: model);
  Future<List<int>> request(int op, int slot,
      {List<int>? config, int model = 0}) async {
    if (op < 0 || op > 1 || slot < 0 || (slot > 6 && slot != 255)) {
      throw const FormatException('Invalid NAM preset');
    }
    if (model < 0 || model > 0xffffffff || (op == 1 && config == null)) {
      throw const FormatException('Invalid NAM controls request');
    }
    if (config != null) validateNamTone(config);
    final token = nonce = nonce % 16383 + 1;
    final q = Uint8List.fromList([
      240,
      67,
      88,
      112,
      4,
      2,
      78,
      71,
      1,
      op,
      slot == 255 ? 127 : slot,
      token & 127,
      token >> 7,
      if (op == 1) ...[
        0,
        for (var i = 0; i < 5; i++) (model >> (i * 7)) & 127,
        ...config!
      ],
      247
    ]);
    final reply = await exchange(q);
    if (reply.length != 22 ||
        reply.take(9).join(',') != q.take(9).join(',') ||
        reply.last != 247 ||
        reply.sublist(1, 21).any((v) => v > 127) ||
        reply[9] != (op | 64) ||
        reply[10] != q[10] ||
        reply[11] != q[11] ||
        reply[12] != q[12] ||
        reply[13] != 0 ||
        ![0, 1, 2, 3, 4, 5, 6, 127].contains(reply[14])) {
      throw const FormatException('NAM change was not confirmed');
    }
    final result = reply.sublist(15, 21);
    validateNamTone(result);
    if (op == 1 &&
        (reply[14] != q[10] || result.join(',') != config!.join(','))) {
      throw const FormatException('NAM readback did not match');
    }
    return result;
  }
}

class UsbRecordClient {
  final Future<Uint8List> Function(Uint8List) exchange;
  int nonce = DateTime.now().millisecondsSinceEpoch % 16383;
  UsbRecordClient(this.exchange);
  Future<List<int>> read() => request(0, 0);
  Future<List<int>> write(List<int> config, int active, int model) =>
      request(1, active, config: config, model: model);
  Future<List<int>> request(int op, int slot,
      {List<int>? config, int model = 0}) async {
    if (op < 0 || op > 1 || slot < 0 || (slot > 6 && slot != 255)) {
      throw const FormatException('Invalid NAM preset');
    }
    if (model < 0 || model > 0xffffffff || (op == 1 && config == null)) {
      throw const FormatException('Invalid NAM controls request');
    }
    if (config != null) if (config.length != 1 ||
        config[0] < 0 ||
        config[0] > 96)
      throw const FormatException('Invalid USB recording gain');
    final token = nonce = nonce % 16383 + 1;
    final q = Uint8List.fromList([
      240,
      67,
      88,
      112,
      4,
      2,
      78,
      86,
      1,
      op,
      slot == 255 ? 127 : slot,
      token & 127,
      token >> 7,
      if (op == 1) ...[
        0,
        for (var i = 0; i < 5; i++) (model >> (i * 7)) & 127,
        ...config!
      ],
      247
    ]);
    final reply = await exchange(q);
    if (reply.length != 17 ||
        reply.take(9).join(',') != q.take(9).join(',') ||
        reply.last != 247 ||
        reply.sublist(1, 16).any((v) => v > 127) ||
        reply[9] != (op | 64) ||
        reply[10] != q[10] ||
        reply[11] != q[11] ||
        reply[12] != q[12] ||
        reply[13] != 0 ||
        ![0, 1, 2, 3, 4, 5, 6, 127].contains(reply[14])) {
      throw const FormatException('NAM change was not confirmed');
    }
    final result = reply.sublist(15, 16);
    if (result[0] > 96)
      throw const FormatException('Invalid USB recording gain');
    if (op == 1 &&
        (reply[14] != q[10] || result.join(',') != config!.join(','))) {
      throw const FormatException('NAM readback did not match');
    }
    return result;
  }
}
