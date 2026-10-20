# Reporting security problems

Do not include live tokens, device backups, private captures, or personal paths in public issues. For a sensitive security report, use GitHub's private vulnerability reporting when enabled on this repository. Public issues are suitable for non-sensitive reproducible bugs.

The controller stores its Mac sign-in session in Keychain. `app/config/tone3000.json` is a publishable application identifier, not a secret. Forks should register their own public client identifier. Never add private client secrets or account access tokens to the build configuration.
