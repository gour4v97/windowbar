# Localization workflow

Windows Bar does not yet have complete runtime localization. This document sets the translation file and review conventions for the first implementation pass

## Translation conventions

- Use English source text as the fallback and stable message key for the initial rollout.
- Keep translation files in `locales/<locale>.json`, encoded as UTF-8 JSON objects.
- Keep placeholders identical between English and translated values (for example, `{count}`). Do not concatenate sentence fragments to build a sentence.
- Use standard locale tags such as `en`, `en-GB`, or `hi`; do not add a locale until a maintainer can review it.
- Preserve Windows product names, keyboard shortcuts, paths, and code tokens unless a translator's note says otherwise.
- Record pluralization and formatting requirements before translating dynamic messages. Avoid inventing a plural rule in a flat key/value file.

## Contribution and review

1. Include a translator note for ambiguous UI context.
2. Review strings in the UI for clipping, mnemonic conflicts, and correct keyboard shortcut rendering.

Until those land, do not add a locale file that the application cannot load.

## Release localization checklist

- [ ] Choose and document the runtime localization library or a small in-house loader.
- [ ] Complete a native-speaker review before advertising a locale as supported.
