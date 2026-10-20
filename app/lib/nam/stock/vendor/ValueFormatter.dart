// Adapted from Mightier Amp (MIT), copyright Dian Iliev. Data and formatting only.
// ignore_for_file: non_constant_identifier_names, constant_identifier_names, file_names, annotate_overrides, hash_and_equals, prefer_final_fields, unnecessary_this
import 'FrequencyFormatter.dart';
import 'SwitchFormatters.dart';

import 'TempoFormatter.dart';
import 'DecibelFormatter.dart';
import 'PercentageFormatter.dart';

enum InputType { SliderInput, SwitchInput }

class ValueFormatters {
  static PercentageFormatter percentage = PercentageFormatter();
  static PercentageFormatterMPPro percentageMPPro = PercentageFormatterMPPro();
  static DecibelFormatterMP2 decibelMP2 = DecibelFormatterMP2();
  static DecibelFormatterMPPro decibelMPPro = DecibelFormatterMPPro();
  static DecibelFormatterEQ decibelEQ = DecibelFormatterEQ();
  static TempoFormatter tempo = TempoFormatter();
  static TempoFormatterPro tempoPro = TempoFormatterPro();
  static TempoFormatterProMod tempoProMod = TempoFormatterProMod();
  static TempoFormatterProAnalog tempoProAnalog = TempoFormatterProAnalog();
  static TempoFormatterProTapeEcho tempoProTapeEcho =
      TempoFormatterProTapeEcho();
  static BrightModeFormatter brightMode = BrightModeFormatter();
  static BrightModeFormatterMPPro brightModePro = BrightModeFormatterMPPro();
  static BoostModeFormatter boostMode = BoostModeFormatter();
  static BoostModeFormatterMPPro boostModePro = BoostModeFormatterMPPro();
  static VibeModeFormatter vibeMode = VibeModeFormatter();
  static VibeModeFormatterPro vibeModePro = VibeModeFormatterPro();
  static ContourModeFormatter contourMode = ContourModeFormatter();
  static SCFModeFormatter scfMode = SCFModeFormatter();
  static LowFrequencyFormatter lowFreqFormatter = LowFrequencyFormatter();
  static HighFrequencyFormatter highFreqFormatter = HighFrequencyFormatter();
  static TouchWahModeFormatter touchWahFormatter = TouchWahModeFormatter();
  static TouchWahModeFormatterLiteMk2 touchWahFormatterLiteMk2 =
      TouchWahModeFormatterLiteMk2();
  static TouchWahDirectionFormatterPro touchWahDirectionFormatterPro =
      TouchWahDirectionFormatterPro();
}

abstract class ValueFormatter {
  InputType get inputType;
  int get min => 0;
  int get max => 100;

  int valueToMidi7Bit(double value);
  double midi7BitToValue(int midi7bit);
  String toLabel(double value);
  double toHumanInput(double value) {
    return value;
  }

  double fromHumanInput(double value) {
    return value;
  }
}
