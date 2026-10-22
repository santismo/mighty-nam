import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/nam_tone_client.dart';
import 'package:mighty_plug_manager/nam/stock/rig.dart';
import 'package:mighty_plug_manager/nam/stock/nam_tone.dart';

void main() {
  test('NAM controls validate, round-trip and preserve neutral older chains',
      () {
    final r = HybridRig.initial();
    expect(r.namTone, neutralNamTone());
    r.namTone = [54, 18, 8, 14, 75, 42];
    expect(HybridRig.parse(r.encode()).namTone, r.namTone);
    expect(() => validateNamTone([48, 12, 12, 127, 100, 48]),
        throwsFormatException);
    expect(readNamTone(List.filled(128, 50)), neutralNamTone());
  });
  test('NG native transport validates nonce, active preset and readback',
      () async {
    late Uint8List sent;
    final client = NamToneClient((q) async {
      sent = q;
      return Uint8List.fromList([
        ...q.take(9),
        65,
        ...q.sublist(10, 13),
        0,
        q[10],
        ...q.sublist(19, 25),
        247
      ]);
    });
    expect(await client.write([54, 18, 8, 14, 75, 42], 2, 0x12345678),
        [54, 18, 8, 14, 75, 42]);
    expect(sent[7], 71);
    final bad = NamToneClient((q) async => Uint8List.fromList([
          ...q.take(9),
          65,
          ...q.sublist(10, 13),
          0,
          3,
          ...q.sublist(19, 25),
          247
        ]));
    await expectLater(bad.write(neutralNamTone(), 2, 1), throwsFormatException);
  });
  test('invalid NG request is rejected before transport', () async {
    var exchanges = 0;
    final client = NamToneClient((_) async {
      exchanges++;
      return Uint8List(0);
    });
    await expectLater(client.request(2, 0), throwsFormatException);
    await expectLater(client.request(1, 0), throwsFormatException);
    await expectLater(
        client.write(neutralNamTone(), 0, -1), throwsFormatException);
    await expectLater(
        client.write(neutralNamTone(), 0, 0x100000000), throwsFormatException);
    expect(exchanges, 0);
  });
}
