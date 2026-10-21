import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/tuner.dart';
import 'package:mighty_plug_manager/nam/tuner_dialog.dart';
import 'package:nam_link/nam_link.dart' show crc32;

Int16List signal(double frequency,
    {double harmonic = 0, double noise = 0, double decay = 0}) {
  final random = math.Random(7);
  return Int16List.fromList(List.generate(2048, (i) {
    var sum = 0.0;
    for (var j = 0; j < 4; j++) {
      final t = (i * 4 + j) / 48000;
      final x = (0.32 * math.sin(2 * math.pi * frequency * t) +
                  harmonic * math.sin(4 * math.pi * frequency * t)) *
              math.exp(-decay * t) +
          noise * (random.nextDouble() - .5);
      sum += (x * 32768).floor();
    }
    return (sum / 4).floor();
  }));
}

class Fixture {
  int generation = 0, starts = 0, stops = 0;
  bool wrongGeneration = false, badCrc = false, silent = false;
  final calls = <int>[];
  Future<Uint8List> call(int op, int page, int nonce) async {
    calls.add(op);
    if (op == 1) {
      generation++;
      starts++;
    }
    if (op == 0) stops++;
    final raw = Uint8List(280), b = ByteData(280);
    b.setUint32(0, 0x31554e4d, Endian.little);
    b.setUint8(4, 1);
    b.setUint8(5, op | 128);
    b.setUint8(6, page);
    b.setUint32(8, nonce, Endian.little);
    b.setUint32(
        12, generation + (op == 2 && wrongGeneration ? 1 : 0), Endian.little);
    b.setUint16(16, 12000, Endian.little);
    b.setUint16(18, op == 2 ? 2048 : 0, Endian.little);
    if (op == 2) {
      final s = silent ? Int16List(2048) : signal(440);
      for (var i = 0; i < 128; i++) {
        b.setInt16(20 + 2 * i, s[page * 128 + i], Endian.little);
      }
    }
    raw.setAll(0, b.buffer.asUint8List());
    ByteData.sublistView(raw)
        .setUint32(276, crc32(raw.sublist(0, 276)), Endian.little);
    if (badCrc) raw[279] ^= 1;
    return raw;
  }
}

void main() {
  test('chromatic tuning across bass and guitar with harmonics and decay', () {
    for (final f in [
      41.2034,
      55.0,
      61.7354,
      73.4162,
      82.4069,
      110.0,
      146.8324,
      196.0,
      246.9417,
      329.6276,
      440.0,
      659.2551,
      880.0,
      1318.5102
    ]) {
      for (final cents in [-23.0, 0.0, 19.0]) {
        final frequency = f * math.pow(2, cents / 1200);
        for (final harmonic in [0.0, .5]) {
          final pitch = detectPitch(
              signal(frequency, harmonic: harmonic, noise: .003, decay: 2));
          expect(pitch, isNotNull, reason: '$frequency harmonic $harmonic');
          final error =
              1200 * math.log(pitch!.frequency / frequency) / math.ln2;
          expect(error.abs(), lessThan(2.0),
              reason: '$frequency harmonic $harmonic: $error cents');
        }
      }
    }
  });
  test('silence, DC, low signal and noise do not show an in-tune note', () {
    expect(detectPitch(Int16List(2048)), isNull);
    expect(detectPitch(List.filled(2048, 1200)), isNull);
    expect(detectPitch(signal(110).map((x) => (x / 10000).round()).toList()),
        isNull);
    final random = math.Random(32);
    expect(
        detectPitch(List.generate(2048, (_) => random.nextInt(30000) - 15000)),
        isNull);
    expect(detectPitch([1, 2, 3]), isNull);
    expect(detectPitch(signal(440), referenceHz: 1000), isNull);
    final a = detectPitch(signal(442), referenceHz: 442)!;
    expect(a.note, 'A');
    expect(a.octave, 4);
    expect(a.cents.abs(), lessThan(1));
  });
  test('capture assembles all pages and rejects mixed or corrupt data',
      () async {
    final f = Fixture(), client = TunerClient(Fixture().call);
    final data = await client.capture(cancelled: () => false);
    expect(data, orderedEquals(signal(440)));
    f.wrongGeneration = true;
    await expectLater(TunerClient(f.call).capture(cancelled: () => false),
        throwsFormatException);
    f.wrongGeneration = false;
    f.badCrc = true;
    await expectLater(TunerClient(f.call).capture(cancelled: () => false),
        throwsFormatException);
    f.badCrc = false;
    final before = f.starts;
    expect(await TunerClient(f.call).capture(cancelled: () => true), isNull);
    expect(f.starts, before);
  });
  testWidgets('tuner updates, clears silence and stops on close',
      (tester) async {
    final f = Fixture();
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () => showDialog(
                        context: context,
                        builder: (_) =>
                            TunerDialog(client: TunerClient(f.call))),
                    child: const Text('Open'))))));
    await tester.tap(find.text('Open'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump();
    expect(find.text('A4'), findsOneWidget);
    f.silent = true;
    await tester.pump(const Duration(milliseconds: 40));
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump();
    expect(find.text('Play one string and let it ring'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('close-tuner')));
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pumpAndSettle();
    expect(f.stops, 1);
    expect(find.text('Tuner'), findsNothing);
    final starts = f.starts;
    await tester.pump(const Duration(seconds: 2));
    expect(f.starts, starts);
    expect(tester.takeException(), isNull);
  });
}
