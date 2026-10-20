import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mighty_plug_manager/nam/nam_app.dart';
import 'package:mighty_plug_manager/nam/tone_browser.dart';
import 'package:mighty_plug_manager/nam/tone_session_store.dart';
import 'package:nam_link/nam_link.dart';

// Manual, opt-in live verification. The user completes the system sign-in
// window. No tokens, account details or capture contents are printed.
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.shouldPropagateDevicePointerEvents = true;
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;
  testWidgets('Mac sign-in, live catalog and Keychain restoration', (t) async {
    const id = String.fromEnvironment('TONE3000_CLIENT_ID');
    expect(id.startsWith('t3k_pub_'), isTrue);
    Future<void> until(bool Function() ready,
        {Duration timeout = const Duration(seconds: 45)}) async {
      final deadline = DateTime.now().add(timeout);
      while (!ready() && DateTime.now().isBefore(deadline)) {
        await t.pump(const Duration(milliseconds: 150));
      }
      expect(ready(), isTrue, reason: 'Live sign-in step did not complete');
    }

    await t.pumpWidget(const NamLabApp(autoConnect: false));
    await t.pumpAndSettle();
    debugPrint('NAM_LIVE_SIGNIN: app loaded');
    void press(String label) {
      final button = find.ancestor(
          of: find.text(label),
          matching: find.byWidgetPredicate((w) => w is ButtonStyleButton));
      final action = t.widget<ButtonStyleButton>(button).onPressed;
      expect(action, isNotNull);
      action!();
    }

    press('Explore TONE3000');
    await until(() =>
        find.text('Sign in to TONE3000').evaluate().isNotEmpty ||
        find.text('Sign out').evaluate().isNotEmpty);
    if (find.text('Sign in to TONE3000').evaluate().isNotEmpty) {
      press('Sign in to TONE3000');
      debugPrint('NAM_LIVE_SIGNIN: waiting for user in system sign-in window');
      await until(() => find.text('Sign out').evaluate().isNotEmpty,
          timeout: const Duration(minutes: 6));
    }
    final browser = find.byType(ToneBrowser);
    await until(() => find
        .descendant(of: browser, matching: find.byType(LinearProgressIndicator))
        .evaluate()
        .isEmpty);
    expect(
        find
            .descendant(of: browser, matching: find.byIcon(Icons.chevron_right))
            .evaluate(),
        isNotEmpty,
        reason: 'The live catalog should show tone rows');
    final restored = Tone3000Client(id, sessionStore: NativeToneSessionStore());
    try {
      await restored.restoreSession();
      expect(restored.connected, isTrue);
      final page = await restored.catalog();
      expect(page['data'], isA<List>());
      expect((page['data'] as List).isNotEmpty, isTrue);
      debugPrint(
          'NAM_LIVE_SIGNIN: oauth=pass; catalog=pass; keychain_restore=pass; '
          'catalog_rows=${(page['data'] as List).length}; audio_streams=0');
    } finally {
      // Leave the requested sign-in in Keychain for the user's release app.
      restored.close();
    }
    expect(t.takeException(), isNull);
  },
      skip: !const bool.fromEnvironment('RUN_LIVE_TONE3000'),
      timeout: const Timeout(Duration(minutes: 8)));
}
