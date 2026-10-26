import 'vendor/EQ.dart';
import 'vendor/SwitchFormatters.dart';
import 'vendor/Processor.dart';
import 'vendor/ValueFormatter.dart';

bool stockAmpsAvailable = false;
const stockAmpIds = [
  1,
  2,
  3,
  4,
  5,
  6,
  7,
  8,
  9,
  10,
  11,
  12,
  13,
  14,
  15,
  16,
  17,
  18,
  19,
  20,
  21,
  22,
  23,
  24,
  25,
  26,
  27,
  28,
  29
];
List<int> availableStockAmpIds = [];
const stockAmpNames = [
  "Jazz Clean",
  "Deluxe Rvb",
  "Bass Mate",
  "Tweedy",
  "Twin Reverb",
  "Hiwire",
  "Cali Crunch",
  "Class A15",
  "Class A30",
  "Plexi 100",
  "Plexi 45",
  "Brit 800",
  "1987x50",
  "Slo 100",
  "Fireman HBE",
  "Dual Rect",
  "DIE VH4",
  "Vibro King",
  "Budda",
  "Mr. Z38",
  "Super Rvb",
  "Brit Blues",
  "Match D30",
  "Brit 2000",
  "Uber HiGain",
  "AGL",
  "MLD",
  "Optima Air",
  "Stageman"
];
const stockAmpControls = [
  ["Gain", "Master", "Bass", "Middle", "Treble", "Bright"],
  ["Gain", "Master", "Bass", "Middle", "Treble", ""],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "", "", "", "Tone"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Bright"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "", "Treble", "Cut"],
  ["Gain", "Master", "Bass", "", "Treble", "Cut"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Bright"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Cut"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Cut"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Bright"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "", "Treble", "Cut"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Presence"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Mid Freq"],
  ["Gain", "Master", "Bass", "Middle", "Treble", "Mid Freq"],
  ["Gain", "Master", "Bass", "Middle", "Treble", ""],
  ["Gain", "Master", "Bass", "Middle", "Treble", ""]
];

const extraFxNames = [
  'Pitch',
  'Auto Wah',
  'Chorus',
  'Flanger',
  'Phaser',
  'Tremolo',
  'Vibrato',
  'Stock amp'
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
      'NAMLNK25',
      'NAMLNK26',
      'NAMLNK27',
      'NAMLNK28',
      'NAMLNK29',
      'NAMLNK30'
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

class StockAmpChoice extends SwitchFormatter {
  @override
  String get labelTitle => 'Amplifier';
  @override
  List<int> get midiValues => stockAmpIds;
  @override
  List<String> get labelValues => stockAmpNames;
  @override
  String toLabel(double v) => stockAmpNames[stockAmpIds.indexOf(v.round())];
}

class StockAmpBright extends SwitchFormatter {
  @override
  String get labelTitle => 'Bright';
  @override
  List<int> get midiValues => [0, 100];
  @override
  List<String> get labelValues => ['Off', 'On'];
  @override
  String toLabel(double v) => v >= 50 ? 'On' : 'Off';
}

class StockAmpFx extends EQ {
  @override
  int get nuxIndex => 8;
  @override
  String get name => 'Amp';
  final List<Parameter> values = [
    Parameter(
        name: 'Amplifier',
        handle: 'stock_amp',
        value: 1,
        formatter: StockAmpChoice(),
        devicePresetIndex: 3,
        midiCC: -1),
    for (var i = 0; i < 6; i++)
      Parameter(
          name: 'Tone',
          handle: 'stock_$i',
          value: i == 5 ? 0 : 50,
          formatter: ValueFormatters.percentageMPPro,
          devicePresetIndex: 5 + i,
          midiCC: -1),
    ExtraFx.control('Mix', 4, 100)
  ];
  @override
  List<Parameter> get parameters {
    final names = stockAmpControls[values[0].value.round() - 1];
    for (var i = 0; i < 6; i++) {
      values[i + 1].name = names[i];
      values[i + 1].formatter = names[i] == 'Bright'
          ? StockAmpBright()
          : ValueFormatters.percentageMPPro;
    }
    return values; // fixed storage positions also preserve hidden/reserved setting
  }
}

void validateFx(List<int> c) {
  if (c.length != 32 || c.any((v) => v < 0 || v > 127) || c[2] == c[18])
    throw const FormatException('Invalid FX blocks');
  var amps = 0;
  for (final i in [0, 16]) {
    if (c[i] < 1 || c[i] > 8 || c[i + 1] > 1 || c[i + 2] > 10)
      throw const FormatException('Invalid FX settings');
    if (c[i] == 8) {
      if (++amps > 1 ||
          !stockAmpIds.contains(c[i + 3]) ||
          c.sublist(i + 4, i + 11).any((v) => v > 100) ||
          c.sublist(i + 11, i + 16).any((v) => v != 0))
        throw const FormatException('Choose one supported stock amp block');
    } else if (c[i + 3] > 24 ||
        c.sublist(i + 4, i + 10).any((v) => v > 100) ||
        c.sublist(i + 10, i + 16).any((v) => v != 0))
      throw const FormatException('Invalid FX settings');
  }
}
