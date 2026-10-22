TONE3000 app registration

tone3000.json contains only mighty-nam's publishable application identifier.
It is safe to include in the app. It is not an account access token or secret.

Build the Mac app with:
  flutter build macos --release --dart-define-from-file=config/tone3000.json

Build the browser preview with:
  flutter build web --release --no-web-resources-cdn --dart-define-from-file=config/tone3000.json

Normal users just select NAM > Explore TONE3000 > Sign in to TONE3000.
App registration is not a per-user setting. A bundled ID takes precedence over
saved connection settings from earlier development builds.

For an independently distributed fork, register your own application at
https://www.tone3000.com/settings. Use only the publishable t3k_pub_ identifier.
Never put a t3k_cs_ secret, legacy API key, password or session token here.
If redirect destinations are restricted, include mighty-nam://oauth/callback.
Localhost redirects are allowed by TONE3000 for development.

The Mac uses OAuth PKCE and stores the resulting session in Keychain.
The web preview retains the session only in memory. Audio previews are off.
