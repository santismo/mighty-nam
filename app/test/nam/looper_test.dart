import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/looper.dart';
import 'package:mighty_plug_manager/nam/looper_dialog.dart';

Uint8List response(Uint8List q, List<int> words) => Uint8List.fromList([
      ...q.take(9),
      q[9] | 64,
      ...q.sublist(10, 13),
      0,
      for (final w in words)
        for (var j = 0; j < 5; j++) (w >> (7 * j)) & 127,
      247
    ]);
void main() {
  test(
      'meter uses raw peak with matching threshold and rejects malformed replies',
      () async {
    final sent = <Uint8List>[];
    final client = LooperClient((q) async {
      sent.add(q);
      return response(
          q, [257, 0, 0, 0, 1, 1311 << 8, 40 | (50 << 8) | (30 << 16), 0]);
    }, 'NAMLNK27');
    final s = await client.read();
    expect(sent.single[10], 6);
    expect(s.inputDb, closeTo(-34, .1));
    expect(s.reaches(-40), isTrue);
    expect(s.reaches(-20), isFalse);
    expect(s.meterFraction, closeTo(26 / 48, .01));
    final bad = LooperClient((q) async {
      final r = response(q, List.filled(8, 0));
      r[11]++;
      return r;
    }, 'NAMLNK27');
    await expectLater(bad.read(), throwsFormatException);
    await expectLater(client.request(2, 11), throwsFormatException);
    final old = LooperClient(
        (q) async =>
            response(q, [0, 0, 0, 0, 0, 0, 40 | (50 << 8) | (30 << 16), 0]),
        'NAMLNK26');
    expect((await old.read()).peak, isNull);
    await expectLater(old.request(0, 6), throwsFormatException);
  });
  test('mutation acknowledged once, then read until applied without retries',
      () async {
    int writes = 0, reads = 0;
    final client = LooperClient((q) async {
      if (q[9] != 0) {
        writes++;
        return response(q, [3, 0, 0, 0, 0, 0, 0, 0]);
      }
      reads++;
      return response(q,
          [0, 0, 0, reads == 1 ? 1 : 0, 3, 0, 40 | (65 << 8) | (30 << 16), 0]);
    }, 'NAMLNK27');
    expect((await client.change(3, 65)).volume, 65);
    expect(writes, 1);
    expect(reads, 2);
  });
  testWidgets(
      'input level is on the threshold slider and settings are live MIDI only',
      (tester) async {
    var threshold = 40, sequence = 0, peak = 1311;
    final mutations = <List<int>>[];
    final client = LooperClient((q) async {
      if (q[9] != 0) {
        mutations.add(q);
        sequence++;
        if (q[9] == 2) threshold = q[10];
        return response(q, [sequence, 0, 0, 0, 0, 0, 0, 0]);
      }
      return response(q, [
        0,
        0,
        0,
        0,
        sequence,
        peak << 8,
        threshold | (50 << 8) | (30 << 16),
        0
      ]);
    }, 'NAMLNK27');
    await tester.pumpWidget(MaterialApp(home: LooperDialog(client: client)));
    await tester.pump();
    expect(find.textContaining('above threshold'), findsOneWidget);
    expect(
        tester
            .widget<LinearProgressIndicator>(
                find.byKey(const ValueKey('loop-input-meter')))
            .value,
        greaterThan(.5));
    var slider =
        tester.widget<Slider>(find.byKey(const ValueKey('loop-threshold')));
    slider.onChangeStart!(-20);
    slider.onChanged!(-20);
    await tester.pump();
    expect(find.textContaining('below threshold'), findsOneWidget);
    slider =
        tester.widget<Slider>(find.byKey(const ValueKey('loop-threshold')));
    slider.onChangeEnd!(-20);
    await tester.pump();
    await tester.pump();
    expect(threshold, 20);
    expect(mutations.single[7], 79);
    expect(mutations.single[9], 2);
    peak = 0;
    await tester.pump(const Duration(milliseconds: 150));
    await tester.pump();
    expect(find.textContaining('below −60'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
