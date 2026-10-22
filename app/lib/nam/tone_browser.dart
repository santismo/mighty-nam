import 'package:flutter/material.dart';
import 'package:nam_link/nam_link.dart';

/// A browser attached to the selected NAM block. It never plays audio or writes
/// to a plug. Returning a model only changes the controller's selected capture.
class ToneBrowser extends StatefulWidget {
  final Tone3000Client? client;
  final Future<Tone3000Client> Function() signIn;
  final Future<void> Function() officialPicker;
  final int? initialToneId;
  final bool loadToPlug;
  final String? activeCaptureName;
  const ToneBrowser(
      {super.key,
      this.client,
      this.initialToneId,
      this.loadToPlug = false,
      this.activeCaptureName,
      required this.signIn,
      required this.officialPicker});
  @override
  State<ToneBrowser> createState() => _ToneBrowserState();
}

class _ToneBrowserState extends State<ToneBrowser> {
  Tone3000Client? client;
  final query = TextEditingController(),
      make = TextEditingController(),
      creator = TextEditingController(),
      tag = TextEditingController();
  String collection = 'search',
      gear = '',
      format = 'nam',
      sort = 'trending',
      message = '';
  static const liteOnly = true;
  bool verified = false, busy = false;
  int page = 1, pages = 1, modelPage = 1, modelPages = 1;
  List<Map<String, dynamic>> tones = [], models = [];
  Map<String, dynamic>? tone;
  final browseScroll = ScrollController(), detailScroll = ScrollController();
  final cache = <String, Map<String, dynamic>>{};
  @override
  void initState() {
    super.initState();
    client = widget.client;
    if (client?.connected ?? false) {
      if (widget.initialToneId != null) {
        openTone({'id': widget.initialToneId});
      } else {
        load();
      }
    }
  }

  @override
  void dispose() {
    for (final c in [query, make, creator, tag]) {
      c.dispose();
    }
    browseScroll.dispose();
    detailScroll.dispose();
    super.dispose();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      message = '';
    });
    try {
      await action();
    } catch (error) {
      if (mounted) {
        setState(() => message = error is FormatException
            ? error.message
            : error is ToneApiException
                ? '$error'
                : 'Connection unavailable. Retry or sign in again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  List<Map<String, dynamic>> rows(Map<String, dynamic> response) {
    final data = response['data'];
    if (data is! List ||
        data.length > 100 ||
        data.any((v) => v is! Map<String, dynamic>)) {
      throw const FormatException('Unexpected catalog page');
    }
    return data.cast<Map<String, dynamic>>();
  }

  Future<void> fetch({int nextPage = 1}) async {
    if (!(client?.connected ?? false)) {
      setState(
          () => message = 'Sign in once to browse and switch captures here.');
      return;
    }
    final key = [
      collection,
      query.text,
      gear,
      format,
      sort,
      liteOnly,
      verified,
      make.text,
      creator.text,
      tag.text,
      nextPage
    ].join('|');
    final response = cache[key] ??
        await client!.catalog(
            collection: collection,
            query: query.text,
            gear: gear,
            format: format,
            sort: sort,
            liteOnly: liteOnly,
            verified: verified,
            make: make.text,
            creator: creator.text,
            tag: tag.text,
            page: nextPage);
    final next = rows(response)
        .where((t) =>
            t['format'] == format &&
            (format != 'nam' ||
                t['a2_models_count'] == null ||
                (t['a2_models_count'] is num && t['a2_models_count'] > 0)))
        .toList();
    final count = response['total_pages'];
    if (count is! int || count < 0) {
      throw const FormatException('Unexpected page count');
    }
    if (!mounted) return;
    if (cache.length >= 12) cache.remove(cache.keys.first);
    cache[key] = response;
    setState(() {
      tones = next;
      page = nextPage;
      pages = count == 0 ? 1 : count;
      tone = null;
      models = [];
    });
  }

  Future<void> load({int nextPage = 1}) => run(() => fetch(nextPage: nextPage));
  Future<void> openTone(Map<String, dynamic> selected) => run(() async {
        if (selected['id'] is! int) {
          throw const FormatException('Missing tone identity');
        }
        final detail = await client!.tone(selected['id']);
        final result = detail['format'] == 'nam'
            ? await client!.models(selected['id'])
            : <String, dynamic>{
                'data': <Map<String, dynamic>>[],
                'total_pages': 1
              };
        final next = rows(result);
        if (!mounted) return;
        setState(() {
          tone = detail;
          models = next;
          modelPage = 1;
          if (detailScroll.hasClients) detailScroll.jumpTo(0);
          modelPages = result['total_pages'] is int ? result['total_pages'] : 1;
        });
      });
  Future<void> choose(Map<String, dynamic> selected) => run(() async {
        final capture = await client!.download(selected, tone!);
        if (mounted) Navigator.pop(context, capture);
      });
  Widget choice(String value, String title) => ChoiceChip(
      label: Text(title),
      selected: collection == value,
      onSelected: busy
          ? null
          : (_) {
              setState(() => collection = value);
              load();
            });
  static const gearLabels = {
    '': 'All gear',
    'amp': 'Amp head',
    'amp-cab': 'Amp + cab',
    'cab': 'Cabinet',
    'pedal': 'Pedal',
    'outboard': 'Outboard',
    'space': 'Space',
    'experimental': 'Experimental',
  };

  String? count(dynamic value) => value is int && value >= 0
      ? '$value'.replaceAllMapped(
          RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},')
      : null;

  Widget stats(Map<String, dynamic> t) {
    final downloads = count(t['downloads_count']);
    final n = count(t[t['format'] == 'ir' ? 'irs_count' : 'a2_models_count']);
    return Wrap(spacing: 14, runSpacing: 4, children: [
      Text(
          '${gearLabels[t['gear']] ?? 'Other'} · ${t['format'] == 'ir' ? 'IR' : 'NAM'}'),
      Row(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.download_outlined, size: 14),
        const SizedBox(width: 4),
        Text(downloads == null
            ? 'Downloads unavailable'
            : '$downloads downloads'),
      ]),
      if (n != null) Text('$n ${t['format'] == 'ir' ? 'IRs' : 'A2 models'}'),
    ]);
  }

  Widget thumbnail(dynamic url, {double size = 52, bool avatar = false}) {
    final uri = url is String ? Uri.tryParse(url) : null;
    final fallback = Icon(avatar ? Icons.person_outline : Icons.graphic_eq,
        size: avatar ? 16 : 24, color: Colors.white54);
    return ClipRRect(
        borderRadius: BorderRadius.circular(avatar ? size : 6),
        child: SizedBox(
            width: size,
            height: size,
            child: uri?.scheme == 'https' &&
                    uri!.host.isNotEmpty &&
                    uri.userInfo.isEmpty
                ? Image.network('$uri',
                    fit: BoxFit.cover, errorBuilder: (_, __, ___) => fallback)
                : fallback));
  }

  Widget creatorLine(Map<String, dynamic> t) {
    final user = t['user'] is Map ? t['user'] as Map : const {};
    return Row(children: [
      thumbnail(user['avatar_url'], size: 18, avatar: true),
      const SizedBox(width: 6),
      Flexible(
          child: Text('@${user['username'] ?? 'creator'}',
              overflow: TextOverflow.ellipsis)),
    ]);
  }

  dynamic toneImage(Map<String, dynamic> t) =>
      t['images'] is List && (t['images'] as List).isNotEmpty
          ? t['images'][0]
          : null;
  Widget browseList() => Scrollbar(
      controller: browseScroll,
      thumbVisibility: true,
      child: ListView(
          key: const PageStorageKey('tone-results'),
          controller: browseScroll,
          padding: const EdgeInsets.all(18),
          children: [
            const SizedBox(height: 16),
            SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [
                  choice('search', 'Explore'),
                  const SizedBox(width: 7),
                  choice('favorited', 'Favorites'),
                  const SizedBox(width: 7),
                  choice('downloaded', 'Downloaded'),
                  const SizedBox(width: 7),
                  choice('created', 'My tones')
                ])),
            const SizedBox(height: 14),
            TextField(
                controller: query,
                enabled: !busy,
                onSubmitted: (_) => load(),
                decoration: InputDecoration(
                    labelText: 'Search tones',
                    hintText: 'Amp, tone or capture name',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: IconButton(
                        tooltip: 'Search catalog',
                        onPressed: busy ? null : () => load(),
                        icon: const Icon(Icons.arrow_forward)))),
            const SizedBox(height: 12),
            Wrap(spacing: 10, runSpacing: 10, children: [
              SizedBox(
                  width: 175,
                  child: DropdownButtonFormField<String>(
                      key: const ValueKey('tone-gear'),
                      isExpanded: true,
                      value: gear,
                      decoration: const InputDecoration(labelText: 'Tone type'),
                      items: gearLabels.entries
                          .map((e) => DropdownMenuItem(
                              value: e.key, child: Text(e.value)))
                          .toList(),
                      onChanged: busy
                          ? null
                          : (v) {
                              setState(() {
                                gear = v!;
                                format = gear == 'cab' ? 'ir' : 'nam';
                              });
                              load();
                            })),
              SizedBox(
                  width: 180,
                  child: DropdownButtonFormField<String>(
                      key: const ValueKey('tone-format'),
                      isExpanded: true,
                      value: format,
                      decoration: const InputDecoration(labelText: 'Format'),
                      items: const [
                        DropdownMenuItem(
                            value: 'nam', child: Text('NAM captures')),
                        DropdownMenuItem(
                            value: 'ir', child: Text('IRs · browse only')),
                      ],
                      onChanged: busy
                          ? null
                          : (v) {
                              setState(() => format = v!);
                              load();
                            })),
              if (collection == 'search')
                SizedBox(
                    width: 160,
                    child: DropdownButtonFormField<String>(
                        key: const ValueKey('tone-sort'),
                        isExpanded: true,
                        value: sort,
                        decoration: const InputDecoration(labelText: 'Order'),
                        items: const [
                          DropdownMenuItem(
                              value: 'trending', child: Text('Trending')),
                          DropdownMenuItem(
                              value: 'best-match', child: Text('Best match')),
                          DropdownMenuItem(
                              value: 'newest', child: Text('Newest')),
                          DropdownMenuItem(
                              value: 'downloads-all-time',
                              child: Text('Most downloaded'))
                        ],
                        onChanged: busy
                            ? null
                            : (v) {
                                setState(() => sort = v!);
                                load();
                              })),
            ]),
            if (collection == 'search') ...[
              Wrap(spacing: 8, children: [
                if (format == 'nam')
                  const Chip(label: Text('A2 Lite · 48 kHz')),
                FilterChip(
                    label: const Text('Verified creators'),
                    selected: verified,
                    onSelected: busy
                        ? null
                        : (v) {
                            setState(() => verified = v);
                            load();
                          })
              ]),
              ExpansionTile(
                  key: const PageStorageKey('tone-more-filters'),
                  title: const Text('Make, creator & tag'),
                  tilePadding: EdgeInsets.zero,
                  children: [
                    for (final field in [
                      (make, 'Exact make / model'),
                      (creator, 'Creator username'),
                      (tag, 'Tag')
                    ])
                      Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: TextField(
                              controller: field.$1,
                              enabled: !busy,
                              onSubmitted: (_) => load(),
                              decoration:
                                  InputDecoration(labelText: field.$2))),
                    Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                            onPressed: busy ? null : () => load(),
                            child: const Text('Apply filters')))
                  ]),
            ],
            if ((client?.connected ?? false) && tones.isEmpty && !busy)
              const Padding(
                  padding: EdgeInsets.symmetric(vertical: 22),
                  child: Text(
                      'No matching tones on this page. Try another filter or page.')),
            if (format == 'ir')
              const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                      'Browse cabinet IRs here. Loading custom IRs onto the plug is not supported yet.',
                      style: TextStyle(fontSize: 12, color: Colors.white60))),
            for (final t in tones)
              Card(
                  child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 10),
                      leading: thumbnail(toneImage(t)),
                      title: Text('${t['title'] ?? 'Untitled tone'}'),
                      subtitle: Padding(
                          padding: const EdgeInsets.only(top: 5),
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                creatorLine(t),
                                const SizedBox(height: 5),
                                stats(t)
                              ])),
                      selected: tone?['id'] == t['id'],
                      trailing: const Icon(Icons.chevron_right),
                      onTap: busy ? null : () => openTone(t))),
            if (client?.connected ?? false)
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                TextButton(
                    onPressed: !busy && page > 1
                        ? () => load(nextPage: page - 1)
                        : null,
                    child: const Text('Previous')),
                Text('$page / $pages'),
                TextButton(
                    onPressed: !busy && page < pages
                        ? () => load(nextPage: page + 1)
                        : null,
                    child: const Text('Next'))
              ]),
          ]));
  Widget detailList() => tone == null
      ? const Center(
          child: Padding(
              padding: EdgeInsets.all(32),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.graphic_eq, size: 36, color: Colors.white38),
                SizedBox(height: 16),
                Text('Choose a tone to see its captures',
                    style: TextStyle(fontSize: 18)),
                SizedBox(height: 8),
                Text(
                    'Load an A2 Lite capture into NAM. Favorites stay in Your captures.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white54))
              ])))
      : Scrollbar(
          controller: detailScroll,
          thumbVisibility: true,
          child: ListView(
              key: ValueKey('tone-detail-${tone!['id']}'),
              controller: detailScroll,
              padding: const EdgeInsets.all(22),
              children: [
                const SizedBox(height: 12),
                Text('${tone!['title']}',
                    style: const TextStyle(
                        fontSize: 27, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Row(children: [
                  thumbnail(toneImage(tone!)),
                  const SizedBox(width: 12),
                  Expanded(child: creatorLine(tone!))
                ]),
                const SizedBox(height: 10),
                stats(tone!),
                const SizedBox(height: 8),
                Text('${tone!['license'] ?? 'See tone license'}',
                    style: const TextStyle(color: Colors.white60)),
                const SizedBox(height: 12),
                Text('${tone!['description'] ?? ''}'),
                const SizedBox(height: 20),
                if (tone!['format'] == 'ir')
                  const Text(
                      'This is an impulse response, not a NAM capture. Custom IR transfer to the Cabinet block is not available yet.'),
                if (tone!['format'] == 'nam') ...[
                  const Text('Choose a model', style: TextStyle(fontSize: 20)),
                  const Text(
                      'Only A2 Lite at 48 kHz can load. Multi-size A2 captures use their Lite model; incompatible files leave your current capture unchanged.',
                      style: TextStyle(fontSize: 12, color: Colors.white60)),
                  for (final m in models)
                    Card(
                        child: ListTile(
                            title: Text('${m['name'] ?? 'Model'}'),
                            subtitle:
                                Text('A2 · ${m['size'] ?? 'unknown size'}'),
                            trailing: FilledButton(
                                key: ValueKey('load-model-${m['id']}'),
                                onPressed: busy ? null : () => choose(m),
                                child: Text(widget.loadToPlug
                                    ? 'Load on plug'
                                    : 'Use capture')),
                            onTap: busy ? null : () => choose(m))),
                  if (models.isEmpty)
                    const Padding(
                        padding: EdgeInsets.all(18),
                        child: Text('No A2 models found for this tone.')),
                  if (modelPage < modelPages)
                    TextButton(
                        onPressed: busy
                            ? null
                            : () => run(() async {
                                  final r = await client!
                                      .models(tone!['id'], page: modelPage + 1);
                                  final next = rows(r);
                                  if (mounted) {
                                    setState(() {
                                      models.addAll(next);
                                      modelPage++;
                                    });
                                  }
                                }),
                        child: const Text('More models')),
                ],
              ]));
  @override
  Widget build(BuildContext context) => SafeArea(
          child: Column(children: [
        Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 12, 12),
            child: Row(children: [
              if (tone != null)
                IconButton(
                    tooltip: 'Back to tones',
                    onPressed: busy
                        ? null
                        : () {
                            setState(() => tone = null);
                            if (tones.isEmpty) load();
                          },
                    icon: const Icon(Icons.arrow_back)),
              const Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text('TONE3000',
                        style: TextStyle(
                            fontSize: 23, fontWeight: FontWeight.w600)),
                    Text('Choose a capture for NAM',
                        style: TextStyle(fontSize: 12, color: Colors.white60))
                  ])),
              if (widget.initialToneId == null)
                FilledButton.icon(
                    key: const ValueKey('official-tone-picker'),
                    onPressed: busy ? null : () => run(widget.officialPicker),
                    icon: const Icon(Icons.search),
                    label: const Text('Browse TONE3000')),
              IconButton(
                  tooltip: 'Close tone browser',
                  onPressed: busy ? null : () => Navigator.pop(context),
                  icon: const Icon(Icons.close)),
            ])),
        Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
            child: Row(children: [
              Expanded(
                  child: Text(
                      widget.activeCaptureName == null
                          ? '48 kHz · A2 Lite · no audio previews'
                          : 'Selected in NAM: ${widget.activeCaptureName}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 12, color: Colors.white60))),
              if (client?.connected ?? false)
                TextButton(
                    onPressed: busy
                        ? null
                        : () => run(() async {
                              await client!.signOut();
                              cache.clear();
                              setState(() {
                                tone = null;
                                tones = [];
                                models = [];
                                message = 'Signed out.';
                              });
                            }),
                    child: const Text('Sign out')),
            ])),
        if (busy) const LinearProgressIndicator(minHeight: 2),
        if (message.isNotEmpty)
          Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Text(message,
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.error))),
        const Divider(height: 1),
        Expanded(
            child: !(client?.connected ?? false)
                ? Center(
                    child: SizedBox(
                        width: 440,
                        child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Text('Your next capture',
                                      style: TextStyle(fontSize: 24)),
                                  const SizedBox(height: 12),
                                  const Text(
                                      'Browse the full TONE3000 catalog, or sign in here for your favorites and downloads.',
                                      textAlign: TextAlign.center),
                                  const SizedBox(height: 20),
                                  FilledButton.icon(
                                      onPressed: busy
                                          ? null
                                          : () => run(() async {
                                                client = await widget.signIn();
                                                if (mounted) await fetch();
                                              }),
                                      icon: const Icon(Icons.login),
                                      label: const Text('Sign in to TONE3000')),
                                ]))))
                : LayoutBuilder(
                    builder: (context, size) => size.maxWidth >= 820
                        ? Row(children: [
                            Expanded(flex: 5, child: browseList()),
                            const VerticalDivider(width: 1),
                            Expanded(flex: 4, child: detailList())
                          ])
                        : tone == null
                            ? browseList()
                            : detailList())),
      ]));
}
