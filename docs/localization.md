# Localization workflow

Windows Bar does not yet have complete runtime localization. This document sets the translation file and review conventions for the first implementation pass; it does not claim that all UI strings are localized.

## Translation conventions

- Use English source text as the fallback and stable message key for the initial rollout.
- Keep translation files in `locales/<locale>.json`, encoded as UTF-8 JSON objects.
- Keep placeholders identical between English and translated values (for example, `{count}`). Do not concatenate sentence fragments to build a sentence.
- Use standard locale tags such as `en`, `en-GB`, or `hi`; do not add a locale until a maintainer can review it.
- Preserve Windows product names, keyboard shortcuts, paths, and code tokens unless a translator's note says otherwise.
- Record pluralization and formatting requirements before translating dynamic messages. Avoid inventing a plural rule in a flat key/value file.

## Contribution and review

1. Add or update the English source entry first.
2. Include a translator note for ambiguous UI context.
3. Update each supported locale and retain the same placeholders.
4. Check JSON syntax and compare key sets before submitting.
5. Review strings in the UI for clipping, mnemonic conflicts, and correct keyboard shortcut rendering.

The initial runtime loader, Settings language picker, missing-key reporting, and CI key-parity check remain roadmap work. Until those land, do not add a locale file that the application cannot load.

## Release localization checklist

- [ ] Choose and document the runtime localization library or a small in-house loader.
- [ ] Extract UI strings into stable keys and add an English source catalog.
- [ ] Add locale selection and fallback behavior in Settings/config.
- [ ] Add key parity, JSON syntax, and placeholder checks to CI.
- [ ] Complete a native-speaker review before advertising a locale as supported.
