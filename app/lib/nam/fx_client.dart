import 'dart:typed_data';
import 'stock/extra_fx.dart';

class FxClient {
  final Future<Uint8List> Function(Uint8List) exchange;
  int nonce = DateTime.now().millisecondsSinceEpoch % 16383;
  FxClient(this.exchange);
  Future<List<int>> read({int? savedSlot}) =>
      request(savedSlot == null ? 0 : 2, savedSlot ?? 0);
  Future<List<int>> write(List<int> config, int active, int model) =>
      request(1, active, config: config, model: model);
  Future<List<int>> request(int op, int slot,
      {List<int>? config, int model = 0}) async {
    if (slot < 0 || (slot > 6 && slot != 255) || (op == 2 && slot == 255)) {
      throw const FormatException('Invalid FX preset');
    }
    if (config != null) validateFx(config);
    final token = nonce = nonce % 16383 + 1;
    final q = Uint8List.fromList([
      240,
      67,
      88,
      112,
      4,
      2,
      78,
      70,
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
    if (reply.length != 48 ||
        reply.take(9).join(',') != q.take(9).join(',') ||
        reply.last != 247 ||
        reply.sublist(1, 47).any((v) => v > 127) ||
        reply[9] != (op | 64) ||
        reply[10] != q[10] ||
        reply[11] != q[11] ||
        reply[12] != q[12] ||
        reply[13] != 0 ||
        ![0, 1, 2, 3, 4, 5, 6, 127].contains(reply[14])) {
      throw const FormatException('FX change was not confirmed');
    }
    final result = reply.sublist(15, 47);
    validateFx(result);
    if (op == 1 &&
        (reply[14] != q[10] || result.join(',') != config!.join(','))) {
      throw const FormatException('FX readback did not match');
    }
    return result;
  }
}
