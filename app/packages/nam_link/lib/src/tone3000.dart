import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;
import 'model.dart';

class ToneApiException implements Exception {
  final String message;
  final int? status;
  ToneApiException(this.message, [this.status]);
  @override
  String toString() => '$message${status == null ? '' : ' (HTTP $status)'}';
}

abstract class ToneSessionStore {
  Future<String?> read(String clientId);
  Future<void> write(String clientId, String? value);
}

class SelectionFlow {
  final Uri redirect, url;
  final String verifier, state;
  final bool needsTone;
  bool consumed = false;
  SelectionFlow(this.redirect, this.url, this.verifier, this.state,
      {this.needsTone = true});
}

class _Session {
  final String access, refresh;
  final DateTime expires;
  _Session(this.access, this.refresh, this.expires);
}

/// OAuth PKCE and authenticated catalog. Optional platform vault stores sessions.
/// Never place a session in presets, public configuration, logs or browser storage.
class Tone3000Client {
  static final origin = Uri.parse('https://www.tone3000.com');
  final String clientId;
  final http.Client httpClient;
  final DateTime Function() now;
  final ToneSessionStore? sessionStore;
  Future<void> _storageWork = Future.value();
  _Session? _session;
  Future<void>? _refreshing;
  int _epoch = 0;
  bool get connected => _session != null;
  Tone3000Client(this.clientId,
      {http.Client? httpClient, DateTime Function()? now, this.sessionStore})
      : httpClient = httpClient ?? http.Client(),
        now = now ?? DateTime.now {
    if (!clientId.startsWith('t3k_pub_'))
      throw ArgumentError('Use a TONE3000 publishable client ID');
  }
  Future<void> _persistSession() {
    final current = _session;
    final value = current == null
        ? null
        : jsonEncode({
            'client_id': clientId,
            'access': current.access,
            'refresh': current.refresh,
            'expires': current.expires.millisecondsSinceEpoch,
          });
    final next = _storageWork.catchError((_) {}).then((_) async {
      if (sessionStore != null) await sessionStore!.write(clientId, value);
    });
    _storageWork = next;
    return next;
  }

  Future<void> restoreSession() async {
    if (sessionStore == null || _session != null) return;
    final epoch = _epoch;
    await _storageWork.catchError((_) {});
    final text = await sessionStore!.read(clientId);
    if (epoch != _epoch || text == null) return;
    try {
      if (text.length > 16384) throw const FormatException();
      final j = jsonDecode(text);
      if (j is! Map ||
          j['client_id'] != clientId ||
          j['access'] is! String ||
          j['refresh'] is! String ||
          j['access'].isEmpty ||
          j['refresh'].isEmpty ||
          j['expires'] is! int) throw const FormatException();
      _session = _Session(j['access'], j['refresh'],
          DateTime.fromMillisecondsSinceEpoch(j['expires']));
    } catch (_) {
      await sessionStore!.write(clientId, null);
    }
  }

  Future<void> signOut() {
    _epoch++;
    _session = null;
    return _persistSession();
  }

  void disconnect() {
    unawaited(signOut().catchError((_) {}));
  }

  void close() {
    _epoch++;
    _session = null;
    httpClient.close();
  }

  SelectionFlow select(Uri redirect) => authorize(redirect, selectTone: true);

  SelectionFlow authorize(Uri redirect, {bool selectTone = false}) {
    final random = Random.secure();
    String randomString(int bytes) => base64Url
        .encode(List.generate(bytes, (_) => random.nextInt(256)))
        .replaceAll('=', '');
    final verifier = randomString(32), state = randomString(32);
    final challenge = base64Url
        .encode(sha256.convert(ascii.encode(verifier)).bytes)
        .replaceAll('=', '');
    return SelectionFlow(
        redirect,
        origin.replace(path: '/api/v1/oauth/authorize', queryParameters: {
          'client_id': clientId,
          'redirect_uri': '$redirect',
          'response_type': 'code',
          'code_challenge': challenge,
          'code_challenge_method': 'S256',
          'state': state,
          if (selectTone) 'prompt': 'select_tone',
          'architecture': '2',
          'format': 'nam',
          'preview': 'false',
          'menubar': 'true',
        }),
        verifier,
        state,
        needsTone: selectTone);
  }

  Future<int?> complete(SelectionFlow flow, Uri callback) async {
    if (flow.consumed ||
        callback.replace(query: '', fragment: '') !=
            flow.redirect.replace(query: '', fragment: '') ||
        callback.hasFragment ||
        callback.queryParametersAll.values.any((v) => v.length != 1) ||
        callback.queryParameters['state'] != flow.state) {
      throw ToneApiException('Unexpected sign-in callback');
    }
    flow.consumed = true;
    final p = callback.queryParameters;
    if (p.containsKey('error'))
      throw ToneApiException('TONE3000 sign-in was declined or failed');
    final code = p['code'];
    if (code != null && code.isNotEmpty) {
      final epoch = ++_epoch;
      _session = null;
      final session = await _token({
        'grant_type': 'authorization_code',
        'code': code,
        'code_verifier': flow.verifier,
        'redirect_uri': '${flow.redirect}',
        'client_id': clientId
      });
      if (epoch != _epoch) throw ToneApiException('Sign-in was superseded');
      _session = session;
      await _persistSession();
    } else if (p['canceled'] != 'true') {
      throw ToneApiException('Missing sign-in code');
    }
    if (p['canceled'] == 'true') return null;
    if (!flow.needsTone) return null;
    final tone = int.tryParse(p['tone_id'] ?? '');
    if (tone == null || tone <= 0) throw ToneApiException('No tone selected');
    return tone;
  }

  Future<http.Response> _send(Uri uri,
      {Map<String, String> headers = const {},
      Map<String, String>? form,
      int limit = 1024 * 1024}) async {
    if (uri.origin != origin.origin ||
        uri.userInfo.isNotEmpty ||
        uri.hasFragment)
      throw ToneApiException('Untrusted model download address');
    final request = http.Request(form == null ? 'GET' : 'POST', uri)
      ..followRedirects = false;
    request.headers.addAll(headers);
    if (form != null) request.bodyFields = form;
    final response =
        await httpClient.send(request).timeout(const Duration(seconds: 20));
    if (response.contentLength != null && response.contentLength! > limit) {
      await response.stream.listen((_) {}).cancel();
      throw ToneApiException('Response exceeds size limit');
    }
    final bytes = BytesBuilder();
    await for (final chunk
        in response.stream.timeout(const Duration(seconds: 20))) {
      if (bytes.length + chunk.length > limit)
        throw ToneApiException('Response exceeds size limit');
      bytes.add(chunk);
    }
    return http.Response.bytes(bytes.takeBytes(), response.statusCode,
        headers: response.headers);
  }

  Map<String, dynamic> _object(http.Response r) {
    if (r.statusCode != 200)
      throw ToneApiException(
          r.statusCode == 429
              ? 'TONE3000 rate limit; try again later'
              : 'TONE3000 request failed',
          r.statusCode);
    final dynamic data;
    try {
      data = jsonDecode(r.body);
    } on FormatException {
      // Do not show raw token endpoint bodies in UI exceptions.
      throw ToneApiException('Unexpected TONE3000 response');
    }
    if (data is! Map<String, dynamic>)
      throw ToneApiException('Unexpected TONE3000 response');
    return data;
  }

  Future<_Session> _token(Map<String, String> form) async {
    final j = _object(await _send(origin.resolve('/api/v1/oauth/token'),
        form: form, limit: 16384));
    if (j['access_token'] is! String ||
        (j['access_token'] as String).isEmpty ||
        j['refresh_token'] is! String ||
        (j['refresh_token'] as String).isEmpty ||
        j['expires_in'] is! int ||
        j['expires_in'] <= 0 ||
        (j['token_type'] as String?)?.toLowerCase() != 'bearer')
      throw ToneApiException('Invalid token response');
    return _Session(j['access_token'], j['refresh_token'],
        now().add(Duration(seconds: j['expires_in'])));
  }

  Future<void> _refresh() async {
    if (_refreshing != null) return _refreshing!;
    final previous = _session;
    if (previous == null) throw ToneApiException('Connect TONE3000 first');
    final epoch = _epoch;
    final work = () async {
      try {
        final next = await _token({
          'grant_type': 'refresh_token',
          'refresh_token': previous.refresh,
          'client_id': clientId
        });
        if (_epoch == epoch) {
          _session = next;
          await _persistSession();
        }
      } on ToneApiException catch (e) {
        if (_epoch == epoch && (e.status == 400 || e.status == 401))
          disconnect();
        rethrow;
      }
    }();
    _refreshing = work;
    try {
      await work;
    } finally {
      if (identical(_refreshing, work)) _refreshing = null;
    }
  }

  Future<http.Response> _get(Uri uri, {int limit = 1024 * 1024}) async {
    if (_session == null) throw ToneApiException('Connect TONE3000 first');
    if (!_session!.expires.isAfter(now().add(const Duration(seconds: 60))))
      await _refresh();
    if (_session == null) throw ToneApiException('Reconnect TONE3000');
    final sentToken = _session!.access;
    var response = await _send(uri,
        headers: {'Authorization': 'Bearer $sentToken'}, limit: limit);
    if (response.statusCode == 401) {
      if (_session?.access == sentToken) await _refresh();
      if (_session == null) throw ToneApiException('Reconnect TONE3000');
      response = await _send(uri,
          headers: {'Authorization': 'Bearer ${_session!.access}'},
          limit: limit);
      if (response.statusCode == 401) disconnect();
    }
    return response;
  }

  Future<Map<String, dynamic>> catalog(
      {String collection = 'search',
      String query = '',
      String gear = '',
      String format = 'nam',
      String sort = 'trending',
      bool liteOnly = true,
      bool verified = false,
      String make = '',
      String creator = '',
      String tag = '',
      int page = 1}) async {
    if (!['search', 'favorited', 'downloaded', 'created']
            .contains(collection) ||
        page < 1 ||
        !['nam', 'ir'].contains(format) ||
        ![
          '',
          'amp',
          'amp-cab',
          'pedal',
          'outboard',
          'cab',
          'space',
          'experimental'
        ].contains(gear) ||
        !['best-match', 'trending', 'newest', 'oldest', 'downloads-all-time']
            .contains(sort)) {
      throw ArgumentError('Invalid catalog filters');
    }
    final q = <String, String>{
      'page': '$page',
      'page_size': '20',
      if (query.trim().isNotEmpty) 'query': query.trim()
    };
    if (collection == 'search') {
      q.addAll({
        'format': format,
        if (format == 'nam') 'architecture': '2',
        'sort': sort,
        if (format == 'nam' && liteOnly) 'sizes': 'lite',
        if (gear.isNotEmpty) 'gears': gear,
        if (verified) 'verified': 'true',
        if (make.trim().isNotEmpty) 'makes': make.trim(),
        if (creator.trim().isNotEmpty) 'creators': creator.trim(),
        if (tag.trim().isNotEmpty) 'tags': tag.trim()
      });
    } else if (gear.isNotEmpty) {
      q['gear'] = gear;
    }
    return _object(await _get(
        origin.replace(path: '/api/v1/tones/$collection', queryParameters: q)));
  }

  Future<Map<String, dynamic>> tone(int id) async {
    if (id <= 0) throw ArgumentError('Invalid tone');
    return _object(await _get(origin.replace(
        path: '/api/v1/tones/$id', queryParameters: {'architecture': '2'})));
  }

  Future<Map<String, dynamic>> models(int toneId, {int page = 1}) async {
    if (toneId <= 0 || page < 1) throw ArgumentError('Invalid model page');
    return _object(
        await _get(origin.replace(path: '/api/v1/models', queryParameters: {
      'tone_id': '$toneId',
      'page': '$page',
      'page_size': '25',
      'architecture': '2',
    })));
  }

  Future<LiteModel> download(
      Map<String, dynamic> model, Map<String, dynamic> tone) async {
    if ('${model['architecture_version']}' != '2' ||
        model['tone_id'] != tone['id'] ||
        tone['format'] != 'nam') {
      throw ToneApiException('Select a NAM A2 model from this tone');
    }
    final url = Uri.parse(model['model_url'] as String);
    final r = await _get(url, limit: LiteModel.maxJsonBytes);
    if (r.statusCode != 200)
      throw ToneApiException('Model download failed', r.statusCode);
    return LiteModel.parse(r.bodyBytes, provenance: {
      'tone_id': tone['id'],
      'model_id': model['id'],
      'name': model['name'],
      'tone_name': tone['title'],
      'creator': tone['user'],
      'license': tone['license'],
      'tone_metadata': tone
    });
  }
}
