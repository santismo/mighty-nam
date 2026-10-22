import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nam_link/nam_link.dart';
import 'package:mighty_plug_manager/nam/starter_captures.dart';
import 'package:mighty_plug_manager/nam/model_library.dart';
import 'package:mighty_plug_manager/nam/firmware_setup.dart';

void main() {
  testWidgets('starters preserve private captures and favorites', (t) async {
    final starters = StarterCaptures(), library = ModelLibrary();
    final private = LiteModel.fixture();
    library.add(private);
    library.toggleFavorite(private.sha256Hex);
    final before = library.toJson();
    expect(await starters.recognize(library, private.sha256Hex), false);
    expect(await starters.recognize(library, '0' * 64), false);
    expect(library.toJson(), before);
    final models = await starters.load();
    expect(models.length, 3);
    for (final m in models.values) {
      expect(m.metadata['license'], 'MIT');
      expect(captureIncludesCabinet(m), true);
      expect(await starters.recognize(library, m.sha256Hex), true);
      expect(await starters.recognize(library, m.sha256Hex), false);
    }
    expect(library.captures.length, 4);
    expect(library.captures[private.sha256Hex]!.toRecord(), private.toRecord());
    expect(library.favorites, {private.sha256Hex});
  });
  testWidgets('setup opens official files and builder without device commands',
      (t) async {
    final urls = <String>[];
    await t.binding.setSurfaceSize(const Size(1000, 1800));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(MaterialApp(home: Scaffold(body:
        SingleChildScrollView(child: FirmwareSetupCard(onOpen: (url) async {
      urls.add(url);
    })))));
    for (final label in [
      'Download NUX V3.0.5',
      'NUX downloads',
      'Open local builder',
      'Installation guide'
    ]) {
      await t.ensureVisible(find.text(label));
      await t.tap(find.text(label));
      await t.pump();
    }
    expect(urls, [
      nuxFirmwareUrl,
      nuxDownloadsUrl,
      firmwareBuilderUrl,
      firmwareInstallUrl
    ]);
    expect(find.textContaining('MP3_OR_V3.0.5.bin'), findsOneWidget);
    expect(find.textContaining('it does not flash'), findsOneWidget);
  });
}
