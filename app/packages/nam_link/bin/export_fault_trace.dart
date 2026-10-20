import 'dart:io';
import 'dart:math';
import 'dart:typed_data';
import 'package:nam_link/nam_link.dart';

// Semantic protocol fault corpus, all envelopes valid. C++ must return exactly
// the same response bytes as the Dart simulator. No hardware transport.
Future<void> main(List<String> args) async {
  if (args.length != 1) throw ArgumentError('output prefix required');
  final requests = BytesBuilder(),
      replies = BytesBuilder(),
      plug = SimulatedPlug();
  Future<void> send(Packet p) async {
    final bytes = p.encode(), answer = await plug.exchange(p.encode());
    requests.add(words([bytes.length]));
    requests.add(bytes);
    replies.add(words([answer.length]));
    replies.add(answer);
  }

  final model = LiteModel.fixture(), bytes = model.slot;
  await send(Packet(Packet.hello, 0, 0, []));
  await send(Packet(Packet.begin, 5, 0, words([8192, model.checksum])));
  await send(Packet(Packet.begin, 5, 0, words([8192, model.checksum])));
  await send(Packet(Packet.begin, 7, 0, words([8192, model.checksum])));
  await send(Packet(Packet.data, 5, 0xffffffff, [0]));
  await send(Packet(Packet.data, 7, 0, [0]));
  await send(Packet(Packet.commit, 5, 0, []));
  for (var i = 0; i < 8192; i += 256) {
    await send(Packet(Packet.data, 5, i, bytes.sublist(i, i + 256)));
    await send(Packet(Packet.data, 5, i, bytes.sublist(i, i + 256)));
  }
  await send(Packet(Packet.commit, 5, 0, []));
  await send(Packet(Packet.commit, 5, 0, []));
  final random = Random(773);
  for (var i = 0; i < 500; i++) {
    await send(Packet(
        random.nextInt(256),
        random.nextInt(10),
        random.nextInt(0xffffffff),
        List.generate(random.nextInt(40), (_) => random.nextInt(256))));
  }
  File('${args[0]}.slot').writeAsBytesSync(bytes);
  File('${args[0]}.requests').writeAsBytesSync(requests.takeBytes());
  File('${args[0]}.replies').writeAsBytesSync(replies.takeBytes());
}
