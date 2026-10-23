import 'package:flutter/material.dart';

const nuxDownloadsUrl = 'https://nuxaudio.com/product/mightyplugpro/';
const nuxFirmwareUrl =
    'https://nux.cherubtechnology.com/download/Firmware/Amps/HeadphoneAmps/MightyPlugPro/NUX_MightyPlugPro_Firmware_V3.0.5_macOS.zip';
const firmwareBuilderUrl = 'https://santismo.github.io/mighty-nam/looper-builder.html';
const firmwareInstallUrl = '$firmwareBuilderUrl#install';

/// Opens documented web resources only. No device, updater or audio API.
class FirmwareSetupCard extends StatelessWidget {
  final Future<void> Function(String url) onOpen;
  final bool busy;
  const FirmwareSetupCard({super.key, required this.onOpen, this.busy = false});

  Widget link(String label, String url, {bool primary = false}) => primary
      ? FilledButton.icon(
          onPressed: busy ? null : () => onOpen(url),
          icon: const Icon(Icons.open_in_new, size: 17),
          label: Text(label))
      : OutlinedButton.icon(
          onPressed: busy ? null : () => onOpen(url),
          icon: const Icon(Icons.open_in_new, size: 17),
          label: Text(label));

  Widget step(String title, String text, Widget? action) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w500)),
        const SizedBox(height: 7),
        Text(text, style: const TextStyle(color: Colors.white70, height: 1.5)),
        if (action != null) ...[const SizedBox(height: 12), action],
      ]));

  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Set up firmware', style: TextStyle(fontSize: 21)),
        const SizedBox(height: 8),
        const Text('Mighty Plug Pro only · experimental NAMLNK23',
            style: TextStyle(color: Colors.white54, fontSize: 12)),
        step(
            '1  Get the NUX files',
            'Download and unzip V3.0.5 for macOS. Keep MP3_OR_V3.0.5.bin (Original) and install NUX Device Updater from the included disk image.',
            Wrap(spacing: 10, runSpacing: 10, children: [
              link('Download NUX V3.0.5', nuxFirmwareUrl),
              link('NUX downloads', nuxDownloadsUrl),
            ])),
        const Divider(),
        step(
            '2  Build mighty-nam',
            'Select that Original .bin in the local builder, then save the generated firmware and build report. The file stays on your computer.',
            link('Open local builder', firmwareBuilderUrl, primary: true)),
        const Divider(),
        step(
            '3  Install with the NUX updater',
            'Installation replaces onboard presets. With headphones unplugged and USB connected, power off, then hold PRESET while powering on. In blinking-blue mode, select the generated file in NUX Device Updater and start the update. Wait for explicit success before restarting with POWER only.',
            link('Installation guide', firmwareInstallUrl)),
        const Divider(),
        step(
            '4  Connect and play',
            'Reconnect here in normal mode. Check the builder’s preset list, start with the plug volume low, and select a color. To use your own capture: NAM → Explore TONE3000, then Save to plug. Saved colors play without the app.',
            null),
        const SizedBox(height: 8),
        const Text(
            'Building and installation are separate steps. This app opens the builder and guide; it does not flash firmware.',
            style: TextStyle(color: Colors.white54, fontSize: 12, height: 1.5)),
      ]);
}
