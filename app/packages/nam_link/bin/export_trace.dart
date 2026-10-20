// Files-only interop tool. No USB, Bluetooth, sound or cloud requests.
import 'dart:io';
import 'dart:convert';
import 'dart:typed_data';
import 'package:nam_link/nam_link.dart';

Future<void> main(List<String> args) async {
  if (args.length != 2)
    throw ArgumentError('export_trace.dart INPUT.nam|--fixture OUTPUT_PREFIX');
  final model = args[0] == '--fixture'
      ? LiteModel.fixture()
      : LiteModel.parse(File(args[0]).readAsBytesSync());
  final capture = _Capture();
  await TransferClient(capture).upload(model, sessionId: 0x12345678);
  File('${args[1]}.slot').writeAsBytesSync(model.slot);
  File('${args[1]}.requests').writeAsBytesSync(capture.requests.takeBytes());
  File('${args[1]}.replies').writeAsBytesSync(capture.replies.takeBytes());
  File('${args[1]}.json').writeAsStringSync(jsonEncode({
    'sha256': model.sha256Hex,
    'crc32': model.checksum,
    'slot_bytes': 8192,
    'frames': capture.count
  }));
}

class _Capture implements ModelTransport {
  final plug = SimulatedPlug(),
      requests = BytesBuilder(),
      replies = BytesBuilder();
  int count = 0;
  @override
  Future<Uint8List> exchange(Uint8List data) async {
    requests.add(words([data.length]));
    requests.add(data);
    final reply = await plug.exchange(data);
    replies.add(words([reply.length]));
    replies.add(reply);
    count++;
    return reply;
  }
}
