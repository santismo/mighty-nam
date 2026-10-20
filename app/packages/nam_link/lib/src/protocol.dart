import 'dart:math';
import 'dart:typed_data';
import 'model.dart';

// Application protocol only. It is NOT NUX SysEx or HID DFU, and there is
// deliberately no USB/BLE transport in this library.
class Packet {
  static const hello = 1,
      begin = 2,
      data = 3,
      commit = 4,
      abort = 5,
      status = 6;
  final int op, session, offset;
  final Uint8List payload;
  Packet(this.op, this.session, this.offset, List<int> payload)
      : payload = Uint8List.fromList(payload);
  Uint8List encode() {
    if (payload.length > 256) throw const FormatException('Packet too large');
    final bytes = Uint8List(24 + payload.length), b = ByteData(24);
    b.setUint32(0, 0x314c504d, Endian.little); // MPL1
    b.setUint8(4, 1);
    b.setUint8(5, op);
    b.setUint16(6, payload.length, Endian.little);
    b.setUint32(8, session, Endian.little);
    b.setUint32(12, offset, Endian.little);
    b.setUint32(16, crc32(payload), Endian.little);
    b.setUint32(20, crc32(b.buffer.asUint8List(0, 20)), Endian.little);
    bytes.setAll(0, b.buffer.asUint8List());
    bytes.setAll(24, payload);
    return bytes;
  }

  factory Packet.decode(Uint8List bytes) {
    if (bytes.length < 24 || bytes.length > 280)
      throw const FormatException('Bad packet size');
    final b = ByteData.sublistView(bytes),
        length = b.getUint16(6, Endian.little);
    if (b.getUint32(0, Endian.little) != 0x314c504d ||
        b.getUint8(4) != 1 ||
        bytes.length != 24 + length ||
        b.getUint32(20, Endian.little) != crc32(bytes.sublist(0, 20)) ||
        b.getUint32(16, Endian.little) != crc32(bytes.sublist(24))) {
      throw const FormatException('Bad protocol header or checksum');
    }
    return Packet(b.getUint8(5), b.getUint32(8, Endian.little),
        b.getUint32(12, Endian.little), bytes.sublist(24));
  }
}

Uint8List words(List<int> values) {
  final b = ByteData(values.length * 4);
  for (var i = 0; i < values.length; i++) {
    b.setUint32(i * 4, values[i], Endian.little);
  }
  return b.buffer.asUint8List();
}

abstract interface class ModelTransport {
  // Only implementations for an independently identified custom firmware may
  // ever send this protocol. Stock identity or a shared VID/PID is insufficient.
  Future<Uint8List> exchange(Uint8List request);
}

class TransferClient {
  final ModelTransport transport;
  TransferClient(this.transport);
  Future<Packet> _request(Packet packet) async {
    // Bounded retries are safe because Begin, identical Data and Commit are idempotent.
    for (var attempt = 0;; attempt++) {
      try {
        final reply = Packet.decode(await transport
            .exchange(packet.encode())
            .timeout(const Duration(seconds: 2)));
        if (reply.op != (packet.op | 0x80) ||
            reply.session != packet.session ||
            reply.payload.length != 24) {
          throw const FormatException('Wrong transfer reply');
        }
        final status =
            ByteData.sublistView(reply.payload).getUint32(0, Endian.little);
        if (status != 0)
          throw StateError('Receiver rejected transfer (status $status)');
        return reply;
      } on FormatException {
        rethrow;
      } on StateError {
        rethrow;
      } catch (_) {
        if (attempt >= 2) rethrow;
      }
    }
  }

  Future<String> upload(LiteModel model,
      {void Function(int, int)? progress,
      bool Function()? canceled,
      int? sessionId}) async {
    final info = await _request(Packet(Packet.hello, 0, 0, []));
    final caps = ByteData.sublistView(info.payload);
    if (caps.getUint32(12, Endian.little) != 8192 ||
        caps.getUint32(16, Endian.little) != 256 ||
        caps.getUint32(20, Endian.little) != 3) {
      throw StateError('Requires custom A2 Lite RAM receiver v1');
    }
    final session = sessionId ?? Random.secure().nextInt(0x7ffffffe) + 1;
    if (session <= 0 || session > 0xffffffff)
      throw ArgumentError('Nonzero session required');
    final bytes = model.slot;
    bool didBegin = false;
    try {
      await _request(
          Packet(Packet.begin, session, 0, words([8192, model.checksum])));
      didBegin = true;
      for (var offset = 0; offset < bytes.length; offset += 256) {
        if (canceled?.call() ?? false) throw StateError('Transfer canceled');
        final end = min(offset + 256, bytes.length);
        final reply = await _request(
            Packet(Packet.data, session, offset, bytes.sublist(offset, end)));
        if (ByteData.sublistView(reply.payload).getUint32(4, Endian.little) !=
            end) throw StateError('Unexpected transfer offset');
        progress?.call(end, bytes.length);
      }
      if (canceled?.call() ?? false) throw StateError('Transfer canceled');
      final reply = await _request(Packet(Packet.commit, session, 0, []));
      if (ByteData.sublistView(reply.payload).getUint32(8, Endian.little) !=
          model.checksum) throw StateError('Committed checksum differs');
      return model.sha256Hex;
    } catch (_) {
      if (didBegin) {
        try {
          await _request(Packet(Packet.abort, session, 0, []));
        } catch (_) {/* Preserve original failure. */}
      }
      rethrow;
    }
  }
}

/// In-process RAM receiver. Reset deliberately loses the model; no durable
/// storage or actual DSP execution is claimed by this simulator.
class SimulatedPlug implements ModelTransport {
  Uint8List? _active, _staging;
  int _session = 0, _received = 0, _expected = 0, _committed = 0;
  Uint8List? get activeSlot =>
      _active == null ? null : Uint8List.fromList(_active!);
  void reset() {
    _active = null;
    _staging = null;
    _session = _received = _expected = _committed = 0;
  }

  @override
  Future<Uint8List> exchange(Uint8List bytes) async {
    final p = Packet.decode(bytes);
    var result = 0;
    switch (p.op) {
      case Packet.hello:
        if (p.session != 0 || p.offset != 0 || p.payload.isNotEmpty) result = 1;
      case Packet.begin:
        if (p.payload.length != 8 || p.offset != 0 || p.session == 0) {
          result = 1;
          break;
        }
        final b = ByteData.sublistView(p.payload);
        if (b.getUint32(0, Endian.little) != 8192) {
          result = 3;
          break;
        }
        final crc = b.getUint32(4, Endian.little);
        if (_staging != null) {
          if (_session != p.session || _expected != crc) result = 4;
        } else if (p.session == _committed) {
          result = 4;
        } else {
          _session = p.session;
          _received = 0;
          _expected = crc;
          _staging = Uint8List(8192);
        }
      case Packet.data:
        if (_staging == null || p.session != _session) {
          result = 2;
          break;
        }
        if (p.payload.isEmpty ||
            p.offset > 8192 ||
            p.payload.length > 8192 - p.offset) {
          result = 3;
          break;
        }
        if (p.offset < _received) {
          if (p.offset + p.payload.length > _received) {
            result = 4;
            break;
          }
          for (var i = 0; i < p.payload.length; i++) {
            if (_staging![p.offset + i] != p.payload[i]) result = 4;
          }
        } else if (p.offset != _received) {
          result = 4;
        } else {
          _staging!.setRange(p.offset, p.offset + p.payload.length, p.payload);
          _received += p.payload.length;
        }
      case Packet.commit:
        if (p.payload.isNotEmpty || p.offset != 0 || p.session == 0) {
          result = 1;
          break;
        }
        if (_staging == null && _committed == p.session) break;
        if (_staging == null || p.session != _session) {
          result = 2;
          break;
        }
        if (_received != 8192) {
          result = 6;
          break;
        }
        if (crc32(_staging!) != _expected || !validSlot(_staging!)) {
          result = 5;
          break;
        }
        _active = _staging;
        _staging = null;
        _committed = p.session;
      case Packet.abort:
        if (p.payload.isNotEmpty || p.offset != 0 || p.session == 0) {
          result = 1;
          break;
        }
        if (p.session != _session) {
          result = 2;
          break;
        }
        _staging = null;
        _received = 0;
      case Packet.status:
        if (p.payload.isNotEmpty || p.offset != 0 || p.session != _session)
          result = 2;
      default:
        result = 1;
    }
    return Packet(
        p.op | 0x80,
        p.session,
        0,
        words([
          result,
          _received,
          _active == null ? 0 : crc32(_active!),
          8192,
          256,
          3
        ])).encode();
  }
}
