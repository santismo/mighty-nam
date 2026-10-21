import 'dart:math' as math;
import 'vendor/EQ.dart';
import 'vendor/Processor.dart';
import 'vendor/ValueFormatter.dart';

class CutFrequency extends ValueFormatter {
  final bool high;
  CutFrequency(this.high);
  @override
  InputType get inputType => InputType.SliderInput;
  @override
  int valueToMidi7Bit(double value) => value.round();
  @override
  double midi7BitToValue(int midi7bit) => midi7bit.toDouble();
  @override
  String toLabel(double value) {
    final v = value.round();
    if (v == 0) return 'Off';
    final hz = (high ? 1000 : 20) * math.pow(high ? 20 : 50, (v - 1) / 99);
    return hz >= 1000
        ? '${(hz / 1000).toStringAsFixed(2)} kHz'
        : '${hz.round()} Hz';
  }
}

class HighLowCut extends EQ {
  @override
  String get name => 'High / Low Cut';
  @override
  int get nuxIndex => 4;
  @override
  final List<Parameter> parameters = [
    Parameter(
        name: 'Low Cut',
        handle: 'cut_low',
        value: 0,
        formatter: CutFrequency(false),
        devicePresetIndex: 36,
        midiCC: 31),
    Parameter(
        name: 'High Cut',
        handle: 'cut_high',
        value: 0,
        formatter: CutFrequency(true),
        devicePresetIndex: 37,
        midiCC: 32),
  ];
}
