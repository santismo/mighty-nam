import 'dart:math' as math;
import 'dart:typed_data';

class LoopReading {
  final int state,
      length,
      cursor,
      sequence,
      pending,
      error,
      faults,
      seconds,
      threshold,
      volume;
  final bool mode, overdub, saveSupported, saved;
  final double? peak;
  LoopReading(List<int> w, String identity)
      : state = w[0] & 255,
        length = w[1],
        cursor = w[2],
        pending = w[3],
        sequence = w[4],
        error = ['NAMLNK27', 'NAMLNK28'].contains(identity) ? w[5] & 255 : w[5],
        faults = w[7],
        seconds = (w[6] >> 16) & 255,
        threshold = w[6] & 255,
        volume = (w[6] >> 8) & 255,
        saveSupported = identity == 'NAMLNK28',
        saved = identity == 'NAMLNK28' && (w[6] & (1 << 24)) != 0,
        mode = (w[0] & 256) != 0,
        overdub = (w[0] & 512) != 0,
        peak = ['NAMLNK27', 'NAMLNK28'].contains(identity)
            ? (w[5] >> 8) / 65535
            : null {
    if (state > 5 ||
        length > 720000 ||
        cursor > length ||
        error > 3 ||
        w[0] >> 12 != 0 ||
        ![30, 60].contains(seconds) ||
        threshold < 12 ||
        threshold > 60 ||
        volume > 100 ||
        (identity == 'NAMLNK28' && w[6] >> 25 != 0) ||
        (['NAMLNK27', 'NAMLNK28'].contains(identity) && w[5] >> 24 != 0)) {
      throw const FormatException('Invalid loop status');
    }
  }
  double? get inputDb => peak == null
      ? null
      : peak! > 0
          ? 20 * math.log(peak!) / math.ln10
          : -96;
  double get meterFraction =>
      (((inputDb ?? -96) + 60) / 48).clamp(0, 1).toDouble();
  bool reaches(double thresholdDb) => (inputDb ?? -96) >= thresholdDb;
  String get label => overdub
      ? 'Overdubbing'
      : [
          'Empty',
          'Armed · waiting for guitar',
          'Recording',
          'Playing',
          'Paused',
          'Stopped'
        ][state];
}

class LooperClient {
  final Future<Uint8List> Function(Uint8List) exchange;
  final String identity;
  int nonce = 0;
  LooperClient(this.exchange, this.identity);
  Future<List<int>> request(int op, int arg) async {
    final extended = ['NAMLNK27', 'NAMLNK28'].contains(identity);
    if (!['NAMLNK26', 'NAMLNK27', 'NAMLNK28'].contains(identity) ||
        !(op == 0 && arg >= 0 && arg <= (extended ? 6 : 5) ||
            op == 1 && arg >= 1 && arg <= 10 ||
            op == 2 && arg >= 12 && arg <= 60 ||
            op == 3 && arg >= 0 && arg <= 100 ||
            op == 4 && [30, 60].contains(arg) ||
            identity == 'NAMLNK28' && op == 5 && arg == 1)) {
      throw const FormatException('Unsupported looper request');
    }
    nonce = nonce % 16383 + 1;
    final q = Uint8List.fromList([
      240,
      67,
      88,
      112,
      4,
      2,
      78,
      79,
      1,
      op,
      arg,
      nonce & 127,
      nonce >> 7,
      247
    ]);
    final r = await exchange(q);
    if (r.length != 55 ||
        r.last != 247 ||
        r.take(9).join(',') != q.take(9).join(',') ||
        r[9] != (op | 64) ||
        r.sublist(10, 13).join(',') != q.sublist(10, 13).join(',') ||
        r.sublist(1, 54).any((v) => v > 127) ||
        r[13] > 3 ||
        List.generate(8, (i) => r[18 + i * 5]).any((v) => v > 15)) {
      throw const FormatException('Invalid loop reply');
    }
    if (op == 5 && r[13] == 2)
      throw StateError('Clear the retained loop before saving looper settings');
    if (op == 5 && r[13] == 3)
      throw StateError('Looper settings save failed; refresh before retrying');
    if (r[13] != 0)
      throw StateError([
        '',
        'Invalid loop control',
        'Loop busy; refresh before retrying',
        'Loop memory check failed'
      ][r[13]]);
    return List.generate(
        8,
        (i) => List.generate(5, (j) => r[14 + i * 5 + j] << (j * 7))
            .reduce((a, b) => a + b));
  }

  Future<LoopReading> read() async => LoopReading(
      await request(0, ['NAMLNK27', 'NAMLNK28'].contains(identity) ? 6 : 5),
      identity);
  Future<LoopReading> change(int op, int arg) async {
    final sequence = (await request(op, arg))[0];
    for (var i = 0; i < 10; i++) {
      final s = await read();
      if (s.sequence == sequence && s.pending == 0) {
        if (s.error != 0)
          throw StateError('That action is unavailable in this loop state');
        return s;
      }
      await Future<void>.delayed(const Duration(milliseconds: 50));
    }
    throw StateError('Loop action not confirmed. Refresh before retrying.');
  }
}
