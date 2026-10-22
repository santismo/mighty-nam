import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:nam_link/nam_link.dart';
import 'model_library.dart';

/// Resolve an onboard starter without replacing a user's library or presets.
class StarterCaptures {
  static const identities = {
    '18daa3374ec8c4db48776f9e5190d671c55c13a8603ff720c61f79d8ae154a87',
    'b44310f24a2cd3f5680c674a03e70a5e605aa4376ba4093633a6288f9a7121da',
    '05737e628314d97a3ce90958d19513e5a9ef0eb7f2b81d8873625072bfddf116',
  };
  Future<Map<String, LiteModel>>? _models;
  Future<Map<String, LiteModel>> load() => _models ??=
          rootBundle.loadString('assets/starter-captures.json').then((text) {
        final data = jsonDecode(text);
        if (data['schema'] != 'mighty-nam-starter-captures-1' ||
            (data['models'] as List).length != 3) {
          throw const FormatException('Invalid bundled starters');
        }
        return {
          for (final row in data['models'])
            (row['sha256'] as String):
                LiteModel.restore(Map<String, dynamic>.from(row))
        };
      });

  Future<bool> recognize(ModelLibrary library, String? sha) async {
    if (sha == null ||
        !identities.contains(sha) ||
        library.captures.containsKey(sha) ||
        library.captures.length >= ModelLibrary.capacity) return false;
    final starter = (await load())[sha];
    if (starter == null) return false;
    library.add(starter);
    return true;
  }
}
