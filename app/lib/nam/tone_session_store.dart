import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:nam_link/nam_link.dart';

/// Native sessions use Keychain. The web preview keeps its session in memory.
class NativeToneSessionStore implements ToneSessionStore {
  static const channel = MethodChannel('nam_plug/device');
  bool get supported =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.iOS ||
          defaultTargetPlatform == TargetPlatform.macOS);
  @override
  Future<String?> read(String clientId) async => supported
      ? channel.invokeMethod<String>('loadToneSession', {'clientId': clientId})
      : null;
  @override
  Future<void> write(String clientId, String? value) async {
    if (supported) {
      await channel.invokeMethod<void>(
          'saveToneSession', {'clientId': clientId, 'value': value});
    }
  }
}
