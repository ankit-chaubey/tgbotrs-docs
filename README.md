# tgbotrs-docs

Auto-generated documentation website for [tgbotrs](https://github.com/ankit-chaubey/tgbotrs).

**Live docs: [https://ankit-chaubey.github.io/tgbotrs/](https://ankit-chaubey.github.io/tgbotrs/)**

Direct method links:
```
https://ankit-chaubey.github.io/tgbotrs/#method-send-message
https://ankit-chaubey.github.io/tgbotrs/#method-get-me
https://ankit-chaubey.github.io/tgbotrs/#method-forward-message
https://ankit-chaubey.github.io/tgbotrs/#method-answer-callback-query
```

## What's documented

- All methods with parameter tables, optional param structs, and copyable Rust examples
- All types with field-by-field breakdown
- Bot constructors: `new`, `with_api_url`, `with_timeout`, `with_client`, `new_unverified`
- Long polling with `Poller`
- Webhook server with `WebhookServer` (axum, `webhook` feature)
- Framework: `Dispatcher`, `CommandHandler`, `MessageHandler`, `Updater`, filters
- Sync client: `SyncBot` (`client-ureq` feature)
- Custom HTTP client: `BotClient` trait
- Entity parsing: `MessageEntityExt`, `ParsedEntity`
- Error handling: `BotError` variants

## Deploy

Docs are deployed automatically to `gh-pages` on:
- Push to `main` (when `tgbotrs/src/**` or `scripts/**` change)
- Tag push matching `v*`
- GitHub Release published
- Manual workflow dispatch

To enable GitHub Pages:
1. Repo Settings → Pages
2. Source: `Deploy from a branch`
3. Branch: `gh-pages`
4. Save

## Local generation

```bash
git clone https://github.com/ankit-chaubey/tgbotrs-docs
cd tgbotrs-docs

python3 scripts/generate_docs.py

# open site/index.html in browser
```

To pull latest source files from the main repo before regenerating:

```bash
BASE=https://raw.githubusercontent.com/ankit-chaubey/tgbotrs/main/tgbotrs/src

for f in gen_methods.rs gen_types.rs bot.rs client.rs client_sync.rs \
          entities.rs error.rs polling.rs webhook.rs types.rs; do
  curl -sSL "$BASE/$f" -o "tgbotrs/src/$f"
done

python3 scripts/generate_docs.py
```

## Project structure

```
tgbotrs-docs/
├── .github/
│   └── workflows/
│       └── deploy-docs.yml      # auto-deploy on push, tag, or release
├── scripts/
│   └── generate_docs.py         # doc generator (pure Python stdlib + optional bs4)
├── tgbotrs/
│   └── src/
│       ├── gen_methods.rs       # auto-generated methods
│       ├── gen_types.rs         # auto-generated types
│       ├── bot.rs
│       ├── client.rs
│       ├── client_sync.rs
│       ├── entities.rs
│       ├── error.rs
│       ├── polling.rs
│       ├── webhook.rs
│       ├── types.rs
│       └── framework/
├── site/
│   ├── index.html               # generated output
│   └── CNAME
└── README.md
```

## License

MIT - Copyright (c) 2024-present Ankit Chaubey
