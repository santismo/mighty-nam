import 'package:flutter/services.dart';

class NamDevice {
  static const channel = MethodChannel('nam_plug/device');
  Future<List<Map<String, dynamic>>> devices() async =>
      ((await channel.invokeMethod<List<dynamic>>('devices')) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
  Future<Uint8List> tunerFrame(
          int source, int operation, int page, int nonce) async =>
      (await channel.invokeMethod<Uint8List>('tunerFrame', {
        'source': source,
        'operation': operation,
        'page': page,
        'nonce': nonce
      }))!;
  Future<void> bluetooth() => channel.invokeMethod<void>('bluetooth');
  Future<Map<String, dynamic>> inspect(int source) async =>
      Map<String, dynamic>.from(
          (await channel.invokeMethod<Map>('inspect', {'source': source}))!);
  Future<void> disconnect() => channel.invokeMethod<void>('disconnect');
  Future<Map<String, dynamic>> setOutputBuffer(int source, int samples) async =>
      Map<String, dynamic>.from((await channel.invokeMethod<Map>(
          'setOutputBuffer', {'source': source, 'samples': samples}))!);
  Future<Map<String, dynamic>> setListening(int source, bool enabled) async =>
      Map<String, dynamic>.from((await channel.invokeMethod<Map>(
          'setListening', {'source': source, 'enabled': enabled}))!);
  Future<Map<String, dynamic>> readStockControls(int source) async =>
      Map<String, dynamic>.from((await channel
          .invokeMethod<Map>('readStockControls', {'source': source}))!);
  Future<Map<String, dynamic>> setCabinetBypassed(
          int source, bool bypassed) async =>
      Map<String, dynamic>.from((await channel.invokeMethod<Map>(
          'setCabinetBypassed', {'source': source, 'bypassed': bypassed}))!);
  Future<Map<String, dynamic>> applyStockControls(
          int source, List<List<int>> controls, List<int> order,
          {bool? namEnabled}) async =>
      Map<String, dynamic>.from(
          (await channel.invokeMethod<Map>('applyStockControls', {
        'source': source,
        'controls': controls,
        'order': order,
        if (namEnabled != null) 'namEnabled': namEnabled
      }))!);
  Future<Uint8List> exchangeFxFrame(int source, Uint8List frame) async =>
      (await channel.invokeMethod<Uint8List>(
          'exchangeFxFrame', {'source': source, 'frame': frame}))!;
  Future<Uint8List> exchangePresetFrame(int source, Uint8List frame) async =>
      (await channel.invokeMethod<Uint8List>(
          'exchangePresetFrame', {'source': source, 'frame': frame}))!;
  Future<Uint8List> exchangeModelFrame(int source, Uint8List frame) async =>
      (await channel.invokeMethod<Uint8List>(
          'exchangeModelFrame', {'source': source, 'frame': frame}))!;
}
