import 'package:flutter/services.dart';

Future<String?> loadLibrary() async {
  try {
    return await const MethodChannel('nam_plug/device')
        .invokeMethod<String>('loadLibrary');
  } on MissingPluginException {
    return null;
  }
}

Future<void> saveLibrary(String value) async {
  await const MethodChannel('nam_plug/device')
      .invokeMethod<void>('saveLibrary', value);
}
