import 'dart:math' as math;
import 'dart:typed_data';
import 'package:nam_link/nam_link.dart' show crc32;

typedef TunerExchange = Future<Uint8List> Function(
    int operation, int page, int nonce);

class TunerClient {
  final TunerExchange exchange;
  int _nonce = 1;
  TunerClient(this.exchange);
  Future<ByteData> _request(int operation, int page) async {
    final nonce = _nonce;
    _nonce = _nonce % 16383 + 1;
    final raw = await exchange(operation, page, nonce);
    if (raw.length != 280) {
      throw const FormatException('Incomplete tuner reply');
    }
    final b = ByteData.sublistView(raw);
    if (b.getUint32(0, Endian.little) != 0x31554e4d ||
        raw[4] != 1 ||
        raw[5] != (operation | 128) ||
        raw[6] != page ||
        b.getUint32(8, Endian.little) != nonce ||
        b.getUint16(16, Endian.little) != 12000 ||
        b.getUint16(18, Endian.little) > 2048 ||
        b.getUint32(276, Endian.little) != crc32(raw.sublist(0, 276))) {
      throw const FormatException('Invalid tuner reply');
    }
    if (raw[7] != 0 && !(operation == 2 && raw[7] == 1)) {
      throw const FormatException('The plug must be muted to tune');
    }
    return b;
  }

  Future<void> stop() async {
    await _request(0, 0);
  }

  Future<Int16List?> capture({required bool Function() cancelled}) async {
    if (cancelled()) return null;
    final start = await _request(1, 0);
    final generation = start.getUint32(12, Endian.little);
    await Future<void>.delayed(const Duration(milliseconds: 175));
    final samples = Int16List(2048);
    for (var page = 0; page < 16; page++) {
      ByteData? reply;
      for (var attempt = 0; attempt < 25; attempt++) {
        if (cancelled()) return null;
        final next = await _request(2, page);
        if (next.getUint32(12, Endian.little) != generation) {
          throw const FormatException(
              'Tuner capture changed. Close and reopen the tuner.');
        }
        if (next.getUint8(7) == 0) {
          reply = next;
          break;
        }
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
      if (reply == null || reply.getUint16(18, Endian.little) != 2048) {
        throw const FormatException(
            'The plug did not finish its tuner capture');
      }
      for (var i = 0; i < 128; i++) {
        samples[page * 128 + i] = reply.getInt16(20 + i * 2, Endian.little);
      }
    }
    return cancelled() ? null : samples;
  }
}

class TunerReading {
  final double frequency, confidence, cents;
  final int midiNote;
  const TunerReading(
      this.frequency, this.confidence, this.cents, this.midiNote);
  String get note => const [
        'C',
        'C♯',
        'D',
        'D♯',
        'E',
        'F',
        'F♯',
        'G',
        'G♯',
        'A',
        'A♯',
        'B'
      ][midiNote % 12];
  int get octave => midiNote ~/ 12 - 1;
  bool get inTune => cents.abs() <= 3;
}

/// Monophonic YIN estimate with a longer-period refinement. Input is a bounded
/// dry capture, not a Mac microphone or output stream. Reject silence/noise.
TunerReading? detectPitch(List<int> samples, {double referenceHz = 440}) {
  if (samples.length != 2048 || referenceHz < 430 || referenceHz > 450) {
    return null;
  }
  const rate = 12000.0, window = 1024, maximumLag = 301;
  var mean = 0.0;
  for (final value in samples) {
    mean += value / samples.length;
  }
  var energy = 0.0;
  for (final value in samples) {
    final x = (value - mean) / 32768;
    energy += x * x / samples.length;
  }
  if (energy < 0.000001) return null;
  double difference(int lag) {
    var sum = 0.0;
    for (var i = 0; i < window; i++) {
      final d = (samples[i] - samples[i + lag]).toDouble();
      sum += d * d;
    }
    return sum;
  }

  final values = List<double>.filled(maximumLag + 1, 1);
  var cumulative = 0.0;
  for (var lag = 1; lag <= maximumLag; lag++) {
    final d = difference(lag);
    cumulative += d;
    values[lag] = cumulative > 0 ? d * lag / cumulative : 1;
  }
  var lag = 4;
  for (; lag < maximumLag; lag++) {
    if (values[lag] < 0.12) {
      while (lag + 1 <= maximumLag && values[lag + 1] < values[lag]) {
        lag++;
      }
      break;
    }
  }
  if (lag >= maximumLag || values[lag] > 0.1) return null;
  double offset(double left, double center, double right) {
    final denominator = left - 2 * center + right;
    return denominator <= 0
        ? 0
        : (0.5 * (left - right) / denominator).clamp(-1.0, 1.0);
  }

  final period = lag + offset(values[lag - 1], values[lag], values[lag + 1]);
  final multiple = math.min(8, (1000 / period).floor());
  final expected = (period * multiple).round();
  final radius = math.max(1, math.min(3, (period * 0.45).floor()));
  var best = expected;
  var minimum = double.infinity;
  for (var i = math.max(2, expected - radius);
      i <= math.min(1022, expected + radius);
      i++) {
    final d = difference(i);
    if (d < minimum) {
      minimum = d;
      best = i;
    }
  }
  final refined =
      best + offset(difference(best - 1), minimum, difference(best + 1));
  final frequency = rate * multiple / refined;
  if (!frequency.isFinite || frequency < 40 || frequency > 1400) return null;
  final note = 69 + 12 * math.log(frequency / referenceHz) / math.ln2;
  final nearest = note.round();
  return TunerReading(
      frequency, 1 - values[lag], (note - nearest) * 100, nearest);
}
