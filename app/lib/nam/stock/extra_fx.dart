import 'vendor/EQ.dart';
import 'vendor/Processor.dart';
import 'vendor/ValueFormatter.dart';

const extraFxNames = [
  'Pitch',
  'Auto Wah',
  'Chorus',
  'Flanger',
  'Phaser',
  'Tremolo',
  'Vibrato'
];
bool supportsExtraFx(String? identity) => [
      'NAMLNK13',
      'NAMLNK14',
      'NAMLNK15',
      'NAMLNK16',
      'NAMLNK17',
      'NAMLNK18',
      'NAMLNK19',
      'NAMLNK20',
      'NAMLNK21',
      'NAMLNK22',
      'NAMLNK23',
      'NAMLNK24',
      'NAMLNK25'
    ].contains(identity);

class FxValue extends ValueFormatter {
  final int index;
  FxValue(this.index);
  @override
  InputType get inputType => InputType.SliderInput;
  @override
  int get max => index == 3 ? 24 : 100;
  @override
  int valueToMidi7Bit(double value) => value.round();
  @override
  double midi7BitToValue(int midi7bit) => midi7bit.toDouble();
  @override
  String toLabel(double value) => index == 3
      ? '${value.round() - 12 > 0 ? '+' : ''}${value.round() - 12} semitones'
      : index == 5
          ? '${(.05 + 7.95 * value / 100).toStringAsFixed(2)} Hz'
          : '${value.round()}%';
}

// These controls use the custom NF message, never stock CC addresses.
class ExtraFx extends EQ {
  @override
  final int nuxIndex;
  @override
  String get name => extraFxNames[nuxIndex - 1];
  @override
  final List<Parameter> parameters;
  ExtraFx(this.nuxIndex)
      : parameters = [
          if (nuxIndex == 1) control('Pitch', 3, 12),
          if (nuxIndex >= 3) ...[
            control('Rate', 5, 30),
            control('Depth', 6, 50)
          ],
          if ([4, 5].contains(nuxIndex)) control('Feedback', 7, 0),
          if (nuxIndex == 2) ...[
            control('Sensitivity', 8, 50),
            control('Resonance', 9, 50)
          ],
          control('Mix', 4, 100),
        ];
  static Parameter control(String name, int index, double value) => Parameter(
      name: name,
      handle: 'fx_$index',
      value: value,
      formatter: FxValue(index),
      devicePresetIndex: index,
      midiCC: -1);
}

List<int> defaultFx() => [
      for (int slot = 0; slot < 2; slot++) ...[
        slot + 1,
        0,
        slot + 2,
        12,
        100,
        30,
        50,
        0,
        50,
        50,
        0,
        0,
        0,
        0,
        0,
        0
      ]
    ];
void validateFx(List<int> c) {
  if (c.length != 32 || c.any((v) => v < 0 || v > 127) || c[2] == c[18]) {
    throw const FormatException('Invalid FX blocks');
  }
  for (final i in [0, 16]) {
    if (c[i] < 1 ||
        c[i] > 7 ||
        c[i + 1] > 1 ||
        c[i + 2] > 10 ||
        c[i + 3] > 24 ||
        c.sublist(i + 4, i + 10).any((v) => v > 100) ||
        c.sublist(i + 10, i + 16).any((v) => v != 0)) {
      throw const FormatException('Invalid FX settings');
    }
  }
}
