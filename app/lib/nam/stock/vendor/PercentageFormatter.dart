// Adapted from Mightier Amp (MIT), copyright Dian Iliev. Data and formatting only.
// ignore_for_file: non_constant_identifier_names, constant_identifier_names, file_names, annotate_overrides, hash_and_equals, prefer_final_fields, unnecessary_this
import 'ValueFormatter.dart';

class PercentageFormatter extends ValueFormatter {
  @override
  InputType get inputType => InputType.SliderInput;

  @override
  int valueToMidi7Bit(double value) {
    return (value / 100 * 127).floor();
  }

  @override
  double midi7BitToValue(int midi7bit) {
    return (midi7bit / 127.0) * 100;
  }

  @override
  String toLabel(double value) {
    return "${value.round()} %";
  }
}

class PercentageFormatterMPPro extends ValueFormatter {
  @override
  InputType get inputType => InputType.SliderInput;

  @override
  int valueToMidi7Bit(double value) {
    return value.round();
  }

  @override
  double midi7BitToValue(int midi7bit) {
    return midi7bit.toDouble();
  }

  @override
  String toLabel(double value) {
    return "${value.round()} %";
  }
}
