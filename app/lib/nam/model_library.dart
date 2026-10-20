import 'package:nam_link/nam_link.dart';

bool captureIncludesCabinet(LiteModel model) {
  final tone = model.metadata['tone_metadata'];
  final gear = tone is Map ? tone['gear'] : null;
  return gear == 'amp-cab' || gear == 'full-rig';
}

class ModelLibrary {
  final captures = <String, LiteModel>{};
  final favorites = <String>{};
  static const capacity = 64;
  void add(LiteModel model) {
    if (!captures.containsKey(model.sha256Hex) && captures.length >= capacity) {
      throw const FormatException(
          'The library holds 64 captures. Remove one first.');
    }
    // Validate serialization as well as the original download.
    final checked = LiteModel.restore(model.toRecord());
    captures[checked.sha256Hex] = checked;
  }

  void toggleFavorite(String sha) {
    if (!captures.containsKey(sha)) {
      throw const FormatException('Capture is missing');
    }
    if (!favorites.remove(sha)) favorites.add(sha);
  }

  void remove(String sha) {
    captures.remove(sha);
    favorites.remove(sha);
  }

  Map<String, dynamic> toJson() => {
        'captures': captures.values.map((m) => m.toRecord()).toList(),
        'favorites': favorites.toList(),
      };
  factory ModelLibrary.parse(dynamic value) {
    if (value is! Map ||
        value['captures'] is! List ||
        value['captures'].length > capacity ||
        value['favorites'] is! List ||
        value['favorites'].length > capacity) {
      throw const FormatException('Invalid capture library');
    }
    final library = ModelLibrary();
    for (final record in value['captures']) {
      if (record is! Map<String, dynamic>) {
        throw const FormatException('Invalid capture');
      }
      final m = LiteModel.restore(record);
      if (library.captures.containsKey(m.sha256Hex)) {
        throw const FormatException('Duplicate capture');
      }
      library.add(m);
    }
    for (final sha in value['favorites']) {
      if (sha is! String ||
          !library.captures.containsKey(sha) ||
          !library.favorites.add(sha)) {
        throw const FormatException('Invalid favorite');
      }
    }
    return library;
  }
  ModelLibrary();
}
