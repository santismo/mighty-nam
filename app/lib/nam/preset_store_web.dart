// This conditional implementation is only selected for Flutter web.
// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' as html;

Future<String?> loadLibrary() async =>
    html.window.localStorage['nam-plug-library-v2'];
Future<void> saveLibrary(String value) async {
  html.window.localStorage['nam-plug-library-v2'] = value;
}
