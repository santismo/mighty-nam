// Mightier Amp MP-3 effect choices; MIT attribution in vendor sources.
import 'vendor/Processor.dart';
import 'vendor/NoiseGate.dart';
import 'vendor/Compressor.dart';
import 'vendor/EFX.dart';
import 'vendor/Cabinet.dart';
import 'vendor/Modulation.dart';
import 'vendor/EQ.dart';
import 'cut_eq.dart';
import 'vendor/Delay.dart';
import 'vendor/Reverb.dart';
export 'vendor/Processor.dart' show Processor, Parameter;
export 'vendor/SwitchFormatters.dart' show SwitchFormatter;

List<Processor> stockEffects(String slot) => switch (slot) {
      'gate' => [NoiseGatePro()],
      'comp' => [RoseCompPro(), KComp(), StudioComp()],
      'drive' => [
          DistortionPlus(),
          RCBoost(),
          ACBoost(),
          DistOne(),
          TSDrive(),
          BluesDrive(),
          MorningDrive(),
          EatDist(),
          RedDirt(),
          Crunch(),
          MuffFuzz(),
          Katana(),
          STSinger(),
          TouchWahPro()
        ],
      'cab' => [
          JZ120Pro(),
          DR112Pro(),
          TR212Pro(),
          HIWIRE412(),
          CALI112(),
          A112(),
          GB412Pro(),
          M1960AX(),
          M1960AV(),
          M1960TV(),
          SLO412(),
          FIREMAN412(),
          RECT412(),
          DIE412(),
          MATCH212(),
          UBER412(),
          BS410(),
          A212Pro(),
          M1960AHW(),
          M1936(),
          BUDDA112(),
          Z212(),
          SUPERVERB410(),
          VIBROKING310(),
          AGLDB810(),
          AMPSV212(),
          AMPSV410(),
          AMPSV810(),
          BASSGUY410(),
          EDEN410(),
          MKB410(),
          GHBIRDPro(),
          GJ15Pro(),
          MD45Pro()
        ],
      'mod' => [
          ModCE1(),
          ModCE2(),
          STChorusPro(),
          Vibrato(),
          Detune(),
          FlangerPro(),
          Phase90(),
          Phase100(),
          SCFPro(),
          VibePro(),
          TremoloPro(),
          Rotary(),
          SCH1Pro(),
          MonoOctave()
        ],
      'eq' => [EQSixBand(), EQTenBand(), HighLowCut()],
      'delay' => [
          AnalogDelayV2(),
          DigitalDelay(),
          ModDelay(),
          TapeEcho(),
          PanDelay(),
          PhiDelayPro()
        ],
      'reverb' => [
          RoomReverb(),
          HallReverb(),
          PlateReverb(),
          SpringReverb(),
          ShimmerReverb(),
          DampReverbPro()
        ],
      _ => throw const FormatException('Unknown stock slot'),
    };
