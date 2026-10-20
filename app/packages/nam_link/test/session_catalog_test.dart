import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nam_link/nam_link.dart';
import 'package:test/test.dart';

class Vault implements ToneSessionStore {
  String? value;
  final writes = <String?>[];
  @override
  Future<String?> read(String id) async => value;
  @override
  Future<void> write(String id, String? text) async {
    writes.add(text);
    value = text;
  }
}

http.Response token([String suffix = '']) => http.Response(
    jsonEncode({
      'access_token': 'access$suffix',
      'refresh_token': 'refresh$suffix',
      'token_type': 'bearer',
      'expires_in': 3600
    }),
    200);
Future<void> login(Tone3000Client c) async {
  final f = c.authorize(Uri.parse('mighty-nam://oauth/callback'));
  expect(f.needsTone, false);
  expect(f.url.queryParameters.containsKey('prompt'), false);
  await c.complete(
      f,
      f.redirect
          .replace(queryParameters: {'state': f.state, 'code': 'fixture'}));
}

void main() {
  test(
      'standard sign-in stores session, restores after closing, then removes on logout',
      () async {
    final v = Vault(),
        c = Tone3000Client('t3k_pub_test',
            sessionStore: v, httpClient: MockClient((r) async => token()));
    await login(c);
    expect(c.connected, true);
    expect(jsonDecode(v.value!)['client_id'], 't3k_pub_test');
    c.close();
    final next = Tone3000Client('t3k_pub_test', sessionStore: v,
        httpClient: MockClient((r) async {
      expect(r.headers['Authorization'], 'Bearer access');
      return http.Response('{"id":42}', 200);
    }));
    await next.restoreSession();
    expect(next.connected, true);
    await next.tone(42);
    await next.signOut();
    expect(v.value, null);
    expect(next.connected, false);
    next.close();
  });
  test('invalid vault data is rejected and cleared', () async {
    for (final value in [
      'bad',
      jsonEncode({
        'client_id': 'another',
        'access': 'x',
        'refresh': 'y',
        'expires': 123
      })
    ]) {
      final v = Vault()..value = value;
      final c = Tone3000Client('t3k_pub_test', sessionStore: v);
      await c.restoreSession();
      expect(c.connected, false);
      expect(v.value, null);
      c.close();
    }
  });
  test('expired restored token rotates and persists before catalog use',
      () async {
    final v = Vault()
      ..value = jsonEncode({
        'client_id': 't3k_pub_test',
        'access': 'old',
        'refresh': 'oldrefresh',
        'expires': 0
      });
    var requests = 0;
    final c = Tone3000Client('t3k_pub_test', sessionStore: v,
        httpClient: MockClient((r) async {
      requests++;
      if (r.url.path.endsWith('/token')) {
        expect(r.bodyFields['refresh_token'], 'oldrefresh');
        return token('new');
      }
      expect(r.headers['Authorization'], 'Bearer accessnew');
      return http.Response('{"data":[],"total_pages":0}', 200);
    }));
    await c.restoreSession();
    await c.catalog();
    expect(requests, 2);
    expect(jsonDecode(v.value!)['refresh'], 'refreshnew');
    c.close();
  });
  test('logout during auth cannot resurrect persistent credentials', () async {
    final v = Vault(), pending = Completer<http.Response>();
    final c = Tone3000Client('t3k_pub_test',
        sessionStore: v, httpClient: MockClient((r) => pending.future));
    final flow = c.authorize(Uri.parse('mighty-nam://oauth/callback'));
    final future = c.complete(
        flow,
        flow.redirect.replace(
            queryParameters: {'state': flow.state, 'code': 'fixture'}));
    final failure = expectLater(future, throwsA(isA<ToneApiException>()));
    await c.signOut();
    pending.complete(token());
    await failure;
    expect(v.value, null);
    expect(c.connected, false);
    c.close();
  });
  test(
      'search vs personal collections encode supported filters and A2 detail queries',
      () async {
    final urls = <Uri>[];
    final c = Tone3000Client('t3k_pub_test', httpClient: MockClient((r) async {
      if (r.url.path.endsWith('/token')) return token();
      urls.add(r.url);
      return http.Response('{"data":[],"total_pages":0}', 200);
    }));
    await login(c);
    await c.catalog(
        query: ' plexi ',
        gear: 'amp',
        sort: 'best-match',
        make: 'Marshall',
        creator: 'creator',
        tag: 'rock',
        verified: true,
        page: 2);
    expect(urls.last.path, '/api/v1/tones/search');
    expect(urls.last.queryParameters, containsPair('architecture', '2'));
    expect(urls.last.queryParameters, containsPair('sizes', 'lite'));
    expect(urls.last.queryParameters, containsPair('query', 'plexi'));
    expect(urls.last.queryParameters, containsPair('gears', 'amp'));
    expect(urls.last.queryParameters, containsPair('verified', 'true'));
    await c.catalog(gear: 'cab', format: 'ir', sort: 'downloads-all-time');
    expect(urls.last.queryParameters, {
      'page': '1',
      'page_size': '20',
      'format': 'ir',
      'gears': 'cab',
      'sort': 'downloads-all-time',
    });
    for (final gear in ['amp-cab', 'pedal', 'cab']) {
      await c.catalog(gear: gear);
      expect(urls.last.queryParameters, containsPair('gears', gear));
      expect(urls.last.queryParameters, containsPair('format', 'nam'));
      expect(urls.last.queryParameters, containsPair('architecture', '2'));
    }
    final beforeInvalid = urls.length;
    await expectLater(c.catalog(format: 'unsupported'), throwsArgumentError);
    expect(urls.length, beforeInvalid);
    for (final collection in ['favorited', 'downloaded', 'created']) {
      await c.catalog(collection: collection, gear: 'amp', query: 'test');
      expect(urls.last.path, '/api/v1/tones/$collection');
      expect(urls.last.queryParameters,
          {'page': '1', 'page_size': '20', 'query': 'test', 'gear': 'amp'});
    }
    await c.tone(42);
    expect(urls.last.queryParameters, {'architecture': '2'});
    c.close();
  });
}
