import 'dart:convert';
import 'package:nam_link/nam_link.dart';
import 'package:test/test.dart';

void main() {
  test('preset roundtrip retains order, bypass and model identity', () {
    final p = ChainPreset.initial();
    p.modelSha256 = 'a' * 64;
    p.blocks[0].values[0] = .8;
    final q = ChainPreset.parse(p.encodeJson());
    expect(q.encodeJson(), p.encodeJson());
    expect(q.compile().length, 112);
    expect(q.blocks[3].enabled, false);
  });
  test('unsafe values, duplicates and incompatible sample rates rejected', () {
    final p = ChainPreset.initial();
    p.blocks.add(ChainBlock('second', effectById(3)));
    expect(p.validate, throwsFormatException);
    p.blocks.removeLast();
    p.blocks[0].values[0] = double.nan;
    expect(p.compile, throwsFormatException);
    final j = jsonDecode(ChainPreset.initial().encodeJson());
    j['sample_rate'] = 44100;
    expect(() => ChainPreset.parse(jsonEncode(j)), throwsFormatException);
  });
  test('repeatable drives, full catalogue, empty bypass', () {
    final p = ChainPreset(
        'all', effectCatalog.map((s) => ChainBlock(s.key, s)).toList());
    p.blocks.add(ChainBlock('drive2', effectById(1)));
    expect(p.compile().length, 176);
    expect(ChainPreset('bypass', []).compile().length, 16);
  });
}
