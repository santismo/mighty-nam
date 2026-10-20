import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mighty_plug_manager/nam/tone_browser.dart';
import 'package:nam_link/nam_link.dart';

// UI tests use deterministic asynchronous responses. HTTP, PKCE, session races,
// validation and real query construction are covered by nam_link's API tests.
class CatalogFixture extends Tone3000Client {
  CatalogFixture() : super('t3k_pub_fixture');
  final calls = <Map<String, dynamic>>[];
  bool signedIn = true, rateLimited = false, invalidModel = false;
  String lastGear = 'amp', lastFormat = 'nam';
  int modelRequests = 0;
  dynamic downloads = 12345;
  String? captureGear;
  @override
  bool get connected => signedIn;
  @override
  Future<void> signOut() async {
    signedIn = false;
  }

  @override
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
    calls.add({
      'collection': collection,
      'query': query,
      'page': page,
      'gear': gear,
      'format': format,
      'sort': sort
    });
    lastGear = gear.isEmpty ? 'amp' : gear;
    lastFormat = format;
    if (rateLimited) {
      throw ToneApiException('TONE3000 rate limit; try again later', 429);
    }
    return {
      'data': [
        {
          'id': 42,
          'title': 'Test amp',
          'format': format,
          'gear': lastGear,
          'downloads_count': downloads,
          'irs_count': format == 'ir' ? 3 : 0,
          'a2_models_count': 1,
          'user': {'username': 'test-creator'}
        }
      ],
      'total_pages': 2
    };
  }

  @override
  Future<Map<String, dynamic>> tone(int id) async => {
        'id': id,
        'title': 'Test amp',
        'format': lastFormat,
        'gear': lastGear,
        'downloads_count': downloads,
        'license': 'CC0',
        'user': {'username': 'test-creator'}
      };
  @override
  Future<Map<String, dynamic>> models(int id, {int page = 1}) async {
    modelRequests++;
    return {
      'data': [
        {
          'id': 5,
          'tone_id': id,
          'name': 'Test Lite capture',
          'size': 'lite',
          'architecture_version': 2
        }
      ],
      'total_pages': 1
    };
  }

  @override
  Future<LiteModel> download(
      Map<String, dynamic> m, Map<String, dynamic> tone) async {
    if (invalidModel) {
      throw const FormatException(
          'This model does not match the supported A2 Lite topology');
    }
    final record = LiteModel.fixture().toRecord();
    if (captureGear != null) {
      record['metadata'] = {
        ...Map<String, dynamic>.from(record['metadata'] as Map),
        'tone_metadata': {'gear': captureGear}
      };
    }
    return LiteModel.restore(record);
  }
}

void main() {
  testWidgets('tone filters, real counts and cabinet IR browse-only details',
      (t) async {
    final api = CatalogFixture();
    addTearDown(api.close);
    await t.binding.setSurfaceSize(const Size(1000, 1100));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ToneBrowser(
                client: api,
                signIn: () async => api,
                officialPicker: () async {}))));
    await t.pumpAndSettle();
    expect(find.text('12,345 downloads'), findsOneWidget);
    for (final entry in {
      'Amp head': 'amp',
      'Amp + cab': 'amp-cab',
      'Pedal': 'pedal',
      'Cabinet': 'cab'
    }.entries) {
      await t.ensureVisible(find.byKey(const ValueKey('tone-gear')));
      await t.tap(find.byKey(const ValueKey('tone-gear')));
      await t.pumpAndSettle();
      await t.tap(find.text(entry.key).last);
      await t.pumpAndSettle();
      expect(api.calls.last['gear'], entry.value);
      expect(api.calls.last['page'], 1);
    }
    expect(api.calls.last['format'], 'ir');
    expect(find.text('3 IRs'), findsOneWidget);
    await t.ensureVisible(find.text('Test amp'));
    await t.tap(find.text('Test amp'));
    await t.pumpAndSettle();
    expect(api.modelRequests, 0);
    expect(find.textContaining('Custom IR transfer'), findsOneWidget);
    expect(find.text('Choose a model'), findsNothing);
    expect(find.text('12,345 downloads'), findsOneWidget);
    await t.tap(find.byTooltip('Back to tones'));
    await t.pumpAndSettle();
    await t.ensureVisible(find.byKey(const ValueKey('tone-format')));
    await t.tap(find.byKey(const ValueKey('tone-format')));
    await t.pumpAndSettle();
    await t.tap(find.text('NAM captures').last);
    await t.pumpAndSettle();
    expect(api.calls.last['gear'], 'cab');
    expect(api.calls.last['format'], 'nam');
    await t.tap(find.byKey(const ValueKey('tone-sort')));
    await t.pumpAndSettle();
    await t.tap(find.text('Most downloaded').last);
    await t.pumpAndSettle();
    expect(api.calls.last['sort'], 'downloads-all-time');
    api.downloads = null;
    await t.enterText(
        find.widgetWithText(TextField, 'Search tones'), 'missing count');
    await t.tap(find.byTooltip('Search catalog'));
    await t.pumpAndSettle();
    expect(find.text('Downloads unavailable'), findsOneWidget);
    expect(find.text('0 downloads'), findsNothing);
    expect(find.byTooltip('Close tone browser'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets(
      'catalog search, favorites, pages, detail and validated capture return',
      (t) async {
    final api = CatalogFixture();
    addTearDown(api.close);
    LiteModel? chosen;
    await t.binding.setSurfaceSize(const Size(1000, 1100));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(MaterialApp(
        home: Builder(
            builder: (ctx) => Scaffold(
                body: TextButton(
                    onPressed: () async {
                      chosen = await showModalBottomSheet<LiteModel>(
                          context: ctx,
                          isScrollControlled: true,
                          builder: (_) => SizedBox(
                              height: 1000,
                              child: ToneBrowser(
                                  client: api,
                                  signIn: () async => api,
                                  officialPicker: () async {})));
                    },
                    child: const Text('Browse'))))));
    await t.tap(find.text('Browse'));
    await t.pumpAndSettle();
    expect(find.text('Test amp'), findsOneWidget);
    await t.enterText(find.widgetWithText(TextField, 'Search tones'), 'plexi');
    await t.tap(find.byTooltip('Search catalog'));
    await t.pumpAndSettle();
    expect(api.calls.last['query'], 'plexi');
    await t.tap(find.text('Favorites'));
    await t.pumpAndSettle();
    expect(api.calls.last['collection'], 'favorited');
    await t.ensureVisible(find.text('Next'));
    await t.tap(find.text('Next'));
    await t.pumpAndSettle();
    expect(api.calls.last['page'], 2);
    await t.tap(find.text('Test amp'));
    await t.pumpAndSettle();
    expect(find.text('Choose a model'), findsOneWidget);
    api.invalidModel = true;
    await t.tap(find.text('Test Lite capture'));
    await t.pumpAndSettle();
    expect(find.textContaining('does not match'), findsOneWidget);
    expect(chosen, isNull);
    api.invalidModel = false;
    await t.tap(find.text('Test Lite capture'));
    await t.pumpAndSettle();
    expect(chosen, isNotNull);
    expect(validSlot(chosen!.slot), true);
    expect(find.text('Browse'), findsOneWidget);
    expect(t.takeException(), isNull);
  });
  testWidgets(
      'setup error and rate limit offer fallback; logout clears catalog',
      (t) async {
    await t.binding.setSurfaceSize(const Size(1000, 1100));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ToneBrowser(
                signIn: () async {
                  throw const FormatException(
                      'Add publishable client ID in Workspace');
                },
                officialPicker: () async {}))));
    await t.tap(find.text('Sign in to TONE3000'));
    await t.pumpAndSettle();
    expect(find.textContaining('Add publishable client ID'), findsOneWidget);
    final api = CatalogFixture()..rateLimited = true;
    addTearDown(api.close);
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ToneBrowser(
                client: api,
                signIn: () async => api,
                officialPicker: () async {}))));
    await t.pumpAndSettle();
    expect(find.textContaining('rate limit'), findsOneWidget);
    await t.ensureVisible(find.text('Open official tone picker'));
    expect(find.text('Open official tone picker'), findsOneWidget);
    await t.ensureVisible(find.text('Sign out'));
    await t.tap(find.text('Sign out'));
    await t.pumpAndSettle();
    expect(find.text('Sign in to TONE3000'), findsOneWidget);
    expect(find.text('Test amp'), findsNothing);
    expect(t.takeException(), isNull);
  });
}
