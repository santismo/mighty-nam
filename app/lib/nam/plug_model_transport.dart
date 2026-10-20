import 'dart:typed_data';
import 'package:nam_device/nam_device.dart';
import 'package:nam_link/nam_link.dart';

/// macOS repeats the exact firmware identity gate for every frame, including
/// retries and reconnections. This wrapper cannot send stock effect writes.
class PlugModelTransport implements ModelTransport {
  final NamDevice device;
  final int source;
  PlugModelTransport(this.device, this.source);
  @override
  Future<Uint8List> exchange(Uint8List request) =>
      device.exchangeModelFrame(source, request);
}
