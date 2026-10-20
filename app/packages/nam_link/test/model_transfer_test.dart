import 'dart:convert';
import 'dart:typed_data';
import 'package:nam_link/nam_link.dart';
import 'package:nam_link/src/topology.dart';
import 'package:test/test.dart';

Map<String, dynamic> fixtureJson() => {
      'version': '0.7.0',
      'architecture': 'WaveNet',
      'sample_rate': 48000,
      'config': {...liteTopology(), 'head_scale': 0.75},
      'weights': List.filled(1871, 0.0)..[1870] = 1.0
    };
LiteModel parse(Map<String, dynamic> j) =>
    LiteModel.parse(utf8.encode(jsonEncode(j)));
int result(Packet p) =>
    ByteData.sublistView(p.payload).getUint32(0, Endian.little);
Future<Packet> send(SimulatedPlug plug, Packet p) async =>
    Packet.decode(await plug.exchange(p.encode()));

class Lossy implements ModelTransport {
  final SimulatedPlug plug;
  final Set<int> lost = {};
  Lossy(this.plug);
  @override
  Future<Uint8List> exchange(Uint8List bytes) async {
    final p = Packet.decode(bytes), answer = await plug.exchange(bytes);
    if ((p.op == Packet.begin ||
            p.op == Packet.data ||
            p.op == Packet.commit) &&
        lost.add(p.op)) throw Exception('ACK lost');
    return answer;
  }
}

class WrongDevice implements ModelTransport {
  int calls = 0;
  @override
  Future<Uint8List> exchange(Uint8List bytes) async {
    calls++;
    return Uint8List.fromList([0xf0, 0x43, 0x58, 0xf7]);
  }
}

void main() {
  test('standard CRC32 vector',
      () => expect(crc32(ascii.encode('123456789')), 0xcbf43926));
  test('strict model slot, float scale and immutable copy', () {
    final model = parse(fixtureJson()), slot = model.slot;
    expect(slot.length, 8192);
    expect(validSlot(slot), isTrue);
    expect(ByteData.sublistView(slot).getFloat32(7512, Endian.little), 1);
    slot[0] = 0;
    expect(validSlot(model.slot), isTrue);
  });
  for (final variant in [
    'rate',
    'version',
    'architecture',
    'weights',
    'overflow',
    'topology',
    'head'
  ]) {
    test('reject $variant', () {
      final j = fixtureJson();
      switch (variant) {
        case 'rate':
          j['sample_rate'] = 44100;
        case 'version':
          j['version'] = '0.6.0';
        case 'architecture':
          j['architecture'] = 'LSTM';
        case 'weights':
          j['weights'] = [0];
        case 'overflow':
          (j['weights'] as List)[0] = 1e39;
        case 'topology':
          (j['config']['layers'] as List)[0]['channels'] = 4;
        case 'head':
          j['config']['head_scale'] = '1';
      }
      expect(() => parse(j), throwsFormatException);
    });
  }
  test('one matching Lite submodel only', () {
    final lite = fixtureJson()..remove('sample_rate');
    final container = {
      'version': '0.7.0',
      'architecture': 'SlimmableContainer',
      'sample_rate': 48000,
      'config': {
        'submodels': [
          {'model': lite},
          {
            'model': {'architecture': 'Other'}
          }
        ]
      }
    };
    expect(validSlot(parse(container).slot), isTrue);
    (container['config'] as Map)['submodels'] = [
      {'model': lite},
      {'model': lite}
    ];
    expect(() => parse(container), throwsFormatException);
  });
  test('successful upload and ACK loss retries', () async {
    final plug = SimulatedPlug(), model = LiteModel.fixture();
    expect(await TransferClient(Lossy(plug)).upload(model, sessionId: 9),
        model.sha256Hex);
    expect(plug.activeSlot, orderedEquals(model.slot));
  });
  test('stock-like peer stops before begin', () async {
    final peer = WrongDevice();
    await expectLater(TransferClient(peer).upload(LiteModel.fixture()),
        throwsFormatException);
    expect(peer.calls, 1);
  });
  test(
      'cancel preserves active; reset loses volatile model and rejects stale writes',
      () async {
    final plug = SimulatedPlug(), model = LiteModel.fixture();
    await TransferClient(plug).upload(model, sessionId: 1);
    var done = 0;
    await expectLater(
        TransferClient(plug).upload(model,
            sessionId: 2,
            progress: (n, _) => done = n,
            canceled: () => done >= 512),
        throwsStateError);
    expect(plug.activeSlot, model.slot);
    plug.reset();
    expect(plug.activeSlot, isNull);
    expect(result(await send(plug, Packet(Packet.data, 2, 512, [1]))), 2);
  });
  test('bad lengths, CRC, stale sessions, duplicate conflicts and gaps',
      () async {
    final plug = SimulatedPlug();
    final packet = Packet(Packet.begin, 7, 0, words([8192, 0]));
    final corrupt = packet.encode()..[24] ^= 1;
    await expectLater(plug.exchange(corrupt), throwsFormatException);
    await expectLater(plug.exchange(Uint8List(400)), throwsFormatException);
    expect(result(await send(plug, packet)), 0);
    expect(result(await send(plug, Packet(Packet.data, 8, 0, [1]))), 2);
    expect(
        result(await send(plug, Packet(Packet.data, 7, 0xffffffff, [1]))), 3);
    expect(result(await send(plug, Packet(Packet.data, 7, 1, [1]))), 4);
    expect(result(await send(plug, Packet(Packet.data, 7, 0, [1, 2]))), 0);
    expect(result(await send(plug, Packet(Packet.data, 7, 0, [1, 2]))), 0);
    expect(result(await send(plug, Packet(Packet.data, 7, 0, [1, 3]))), 4);
    expect(result(await send(plug, Packet(Packet.commit, 7, 0, []))), 6);
  });
  test('invalid slot cannot replace active even with correct transfer CRC',
      () async {
    final plug = SimulatedPlug(), model = LiteModel.fixture();
    await TransferClient(plug).upload(model, sessionId: 1);
    final bad = model.slot..[0] = 0;
    await send(plug, Packet(Packet.begin, 2, 0, words([8192, crc32(bad)])));
    for (var n = 0; n < 8192; n += 256) {
      await send(plug, Packet(Packet.data, 2, n, bad.sublist(n, n + 256)));
    }
    expect(result(await send(plug, Packet(Packet.commit, 2, 0, []))), 5);
    expect(plug.activeSlot, model.slot);
  });
  test('slot rejects nonfinite coefficients and modified padding', () {
    final slot = LiteModel.fixture().slot;
    ByteData.sublistView(slot).setUint32(32, 0x7f800000, Endian.little);
    ByteData.sublistView(slot)
        .setUint32(20, crc32(slot.sublist(32, 7516)), Endian.little);
    expect(validSlot(slot), isFalse);
    final bad = LiteModel.fixture().slot..[8191] = 0;
    expect(validSlot(bad), isFalse);
  });
}
