import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nam_link/nam_link.dart';
import 'package:nam_link/src/topology.dart';
import 'package:test/test.dart';

const key = 't3k_pub_test';
final redirect = Uri.parse('mighty-nam://oauth/callback');
http.Response token({int expires = 3600, String suffix = ''}) => http.Response(
    jsonEncode({
      'access_token': 'access$suffix',
      'refresh_token': 'refresh$suffix',
      'token_type': 'bearer',
      'expires_in': expires,
    }),
    200);
Uri callback(SelectionFlow f, [Map<String, String> extra = const {}]) =>
    redirect.replace(queryParameters: {
      'state': f.state,
      'code': 'code',
      'tone_id': '42',
      ...extra
    });
Future<void> connect(Tone3000Client c) async {
  final f = c.select(redirect);
  expect(await c.complete(f, callback(f)), 42);
}

void main() {
  test('selected model download validates bytes and preserves attribution',
      () async {
    var downloads = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) return token();
      expect(r.headers['Authorization'], 'Bearer access');
      downloads++;
      return http.Response(
          jsonEncode({
            'architecture': 'WaveNet',
            'version': '0.7.0',
            'sample_rate': 48000,
            'config': {...liteTopology(), 'head_scale': 1},
            'weights': List.filled(1871, 0.0)..[1870] = 1.0,
          }),
          200);
    }));
    await connect(c);
    final model = await c.download({
      'id': 8,
      'tone_id': 42,
      'name': 'Lite capture',
      'architecture_version': 2,
      'model_url': 'https://www.tone3000.com/api/v1/models/8/download',
    }, {
      'id': 42,
      'title': 'Test tone',
      'format': 'nam',
      'license': 'T3K',
      'user': {'username': 'fixture-creator'},
    });
    expect(downloads, 1);
    expect(validSlot(model.slot), isTrue);
    expect(model.metadata['license'], 'T3K');
    expect(model.metadata['tone_name'], 'Test tone');
    expect((model.metadata['creator'] as Map)['username'], 'fixture-creator');
  });
  test('public client only, random PKCE and explicit A2 with previews off', () {
    expect(() => Tone3000Client('t3k_cs_private'), throwsArgumentError);
    final c = Tone3000Client(key),
        a = c.select(redirect),
        b = c.select(redirect);
    expect(a.verifier.length, 43);
    expect(a.state, isNot(b.state));
    expect(a.url.queryParameters['architecture'], '2');
    expect(a.url.queryParameters['preview'], 'false');
    expect(a.url.queryParameters['code_challenge_method'], 'S256');
    expect(a.url.queryParameters['prompt'], 'select_tone');
    c.close();
  });
  test(
      'callback validates origin, state, duplicates and one-time use before exchange',
      () async {
    var requests = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      requests++;
      return token();
    }));
    final f = c.select(redirect);
    await expectLater(c.complete(f, callback(f).replace(host: 'evil')),
        throwsA(isA<ToneApiException>()));
    await expectLater(c.complete(f, callback(f, {'state': 'wrong'})),
        throwsA(isA<ToneApiException>()));
    await expectLater(
        c.complete(f, Uri.parse('${callback(f)}&state=${f.state}')),
        throwsA(isA<ToneApiException>()));
    expect(requests, 0);
    await c.complete(f, callback(f));
    await expectLater(
        c.complete(f, callback(f)), throwsA(isA<ToneApiException>()));
    expect(requests, 1);
  });
  test('token form, API auth, A2 paging and cancel-with-code', () async {
    final seen = <http.Request>[];
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      seen.add(r);
      if (r.url.path.endsWith('/token')) return token();
      return http.Response('{"data":[],"page":2,"total_pages":2}', 200);
    }));
    final f = c.select(redirect);
    expect(await c.complete(f, callback(f, {'canceled': 'true'})), isNull);
    expect(c.connected, isTrue);
    await c.models(42, page: 2);
    expect(seen.first.bodyFields['code_verifier'], f.verifier);
    expect(seen.first.bodyFields['client_id'], key);
    expect(seen.last.url.queryParameters, containsPair('architecture', '2'));
    expect(seen.last.headers['Authorization'], 'Bearer access');
    expect(seen.last.followRedirects, isFalse);
  });
  test(
      'cancel without code makes no request; OAuth error hides raw server data',
      () async {
    var calls = 0;
    final c = Tone3000Client(key, httpClient: MockClient((_) async {
      calls++;
      return token();
    }));
    final f = c.select(redirect);
    expect(
        await c.complete(
            f,
            redirect.replace(
                queryParameters: {'state': f.state, 'canceled': 'true'})),
        isNull);
    final g = c.select(redirect);
    await expectLater(
        c.complete(g, callback(g, {'error': 'secret-invalid-error'})),
        throwsA(predicate(
            (e) => e is ToneApiException && !'$e'.contains('secret'))));
    expect(calls, 0);
  });
  test('parallel requests share one proactive refresh', () async {
    var tokens = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) {
        tokens++;
        await Future<void>.delayed(const Duration(milliseconds: 5));
        return token(expires: tokens == 1 ? 1 : 3600, suffix: '$tokens');
      }
      expect(r.headers['Authorization'], 'Bearer access2');
      return http.Response('{"id":42}', 200);
    }));
    await connect(c);
    await Future.wait([c.tone(42), c.tone(42)]);
    expect(tokens, 2);
  });
  test('one retry on 401; failed refresh clears session', () async {
    var tokens = 0, gets = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) {
        tokens++;
        return tokens == 3
            ? http.Response('{}', 400)
            : token(suffix: '$tokens');
      }
      gets++;
      return http.Response(
          gets == 2 ? '{"id":42}' : '{}', gets == 2 ? 200 : 401);
    }));
    await connect(c);
    expect((await c.tone(42))['id'], 42);
    expect(gets, 2);
    await expectLater(c.tone(42), throwsA(isA<ToneApiException>()));
    expect(c.connected, isFalse);
  });
  test('logout cannot resurrect session from in-flight refresh', () async {
    var tokens = 0;
    final gate = Completer<http.Response>();
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) {
        tokens++;
        return tokens == 1 ? token(expires: 1) : gate.future;
      }
      throw StateError('must not request after logout');
    }));
    await connect(c);
    final pending = c.tone(42);
    await Future<void>.delayed(Duration.zero);
    c.disconnect();
    gate.complete(token());
    await expectLater(pending, throwsA(isA<ToneApiException>()));
    expect(c.connected, isFalse);
  });
  test('foreign initial URL rejected, redirected loop stops without bearer',
      () async {
    var gets = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) return token();
      gets++;
      if (r.url.host == 'untrusted.example')
        expect(r.headers['Authorization'], isNull);
      return http.Response('', 302,
          headers: {'location': 'https://untrusted.example/model'});
    }));
    await connect(c);
    final model = {
      'architecture_version': '2',
      'tone_id': 42,
      'model_url': 'https://untrusted.example/model'
    };
    final tone = {'id': 42, 'format': 'nam'};
    await expectLater(
        c.download(model, tone), throwsA(isA<ToneApiException>()));
    expect(gets, 0);
    model['model_url'] = 'https://www.tone3000.com/api/v1/models/9/download';
    await expectLater(
        c.download(model, tone), throwsA(isA<ToneApiException>()));
    expect(gets, 2);
  });
  test(
      'signed download redirects strip credentials and validate actual Lite bytes',
      () async {
    final seen = <http.Request>[];
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) return token();
      seen.add(r);
      if (seen.length == 1)
        return http.Response('', 302, headers: {
          'location': 'https://storage.example/model?signature=private'
        });
      if (seen.length == 2)
        return http.Response('', 307,
            headers: {'location': 'https://www.tone3000.com/final-model'});
      return http.Response(
          jsonEncode({
            'architecture': 'WaveNet',
            'version': '0.7.0',
            'sample_rate': 48000,
            'config': {...liteTopology(), 'head_scale': 1},
            'weights': List.filled(1871, 0.0)..[1870] = 1.0,
          }),
          200);
    }));
    await connect(c);
    final model = await c.download({
      'id': 9,
      'tone_id': 42,
      'architecture_version': 2,
      'model_url': 'https://www.tone3000.com/api/v1/models/9/download'
    }, {
      'id': 42,
      'format': 'nam'
    });
    expect(validSlot(model.slot), isTrue);
    expect(seen, hasLength(3));
    expect(seen.first.headers['Authorization'], 'Bearer access');
    for (final request in seen.skip(1))
      expect(request.headers['Authorization'], isNull);
    expect(seen.every((r) => !r.followRedirects), isTrue);
  });
  for (final location in [
    'http://storage.example/a',
    'https://user:secret@storage.example/a',
    'https://storage.example:444/a',
    'https://storage.example/a#secret',
    ''
  ]) {
    test('unsafe download redirect rejected: $location', () async {
      var gets = 0;
      final c = Tone3000Client(key, httpClient: MockClient((r) async {
        if (r.url.path.endsWith('/token')) return token();
        gets++;
        return http.Response('', 302, headers: {'location': location});
      }));
      await connect(c);
      await expectLater(
          c.download({
            'tone_id': 42,
            'architecture_version': 2,
            'model_url': 'https://www.tone3000.com/api/v1/models/9/download'
          }, {
            'id': 42,
            'format': 'nam'
          }),
          throwsA(isA<ToneApiException>()));
      expect(gets, 1);
    });
  }
  test('redirect limit and non-download API redirects remain bounded',
      () async {
    var gets = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) return token();
      gets++;
      return http.Response('', 302,
          headers: {'location': 'https://storage.example/$gets'});
    }));
    await connect(c);
    await expectLater(c.tone(42), throwsA(isA<ToneApiException>()));
    expect(gets, 1);
    await expectLater(
        c.download({
          'tone_id': 42,
          'architecture_version': 2,
          'model_url': 'https://www.tone3000.com/api/v1/models/9/download'
        }, {
          'id': 42,
          'format': 'nam'
        }),
        throwsA(isA<ToneApiException>()));
    expect(gets, 6);
  });
  test('rate-limit does not spin or discard session', () async {
    var gets = 0;
    final c = Tone3000Client(key, httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) return token();
      gets++;
      return http.Response('{}', 429);
    }));
    await connect(c);
    await expectLater(c.models(42),
        throwsA(predicate((e) => e is ToneApiException && e.status == 429)));
    expect(gets, 1);
    expect(c.connected, isTrue);
  });
}
