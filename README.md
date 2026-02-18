# 📚 tgbotrs-docs

> **Auto-generated, interactive documentation website for [tgbotrs](https://github.com/ankit-chaubey/tgbotrs)**  
> 🦀 The complete Telegram Bot API library for Rust — 165 methods, 285 types, Bot API 9.4

**Developed by [Ankit Chaubey](https://github.com/ankit-chaubey)**  
📧 ankitchaubey.dev@gmail.com · 💬 [@ankify](https://t.me/ankify)

---

## 🌐 Live Documentation

**👉 [https://ankit-chaubey.github.io/tgbotrs/](https://ankit-chaubey.github.io/tgbotrs/)**

### Direct method links:
```
https://ankit-chaubey.github.io/tgbotrs/#method-send-message
https://ankit-chaubey.github.io/tgbotrs/#method-get-me
https://ankit-chaubey.github.io/tgbotrs/#method-forward-message
https://ankit-chaubey.github.io/tgbotrs/#method-answer-callback-query
```

---

## ✨ What's in the Docs

| Feature | Details |
|---|---|
| **165 methods** | Every single Telegram Bot API method documented |
| **285 types** | All types with field-by-field breakdown |
| **Copyable examples** | Real working Rust code for every method |
| **Builder params** | All optional params structs fully documented |
| **Quick Search** | Search all 165 methods by name or description |
| **Category filter** | Filter by Send, Get, Edit, Admin, Stickers, Payments... |
| **Sidebar nav** | Jump to any method instantly |
| **Dark theme** | Beautiful dark design with code highlighting |
| **Mobile friendly** | Responsive layout for all devices |

---

## 🚀 Deploying

### One-click deploy (GitHub Actions)

1. Push this repo to GitHub
2. Go to **Actions** tab → **Generate & Deploy Docs**
3. Click **Run workflow** → **Run workflow**
4. Done! Your docs go live at `https://YOUR_USER.github.io/tgbotrs/`

### Enable GitHub Pages first:
1. Go to your repo **Settings** → **Pages**
2. Set **Source** to: `Deploy from a branch`
3. Set **Branch** to: `gh-pages`
4. Save

The workflow will create and maintain the `gh-pages` branch automatically.

---

## 🔧 Regenerating Locally

```bash
# Clone this repo
git clone https://github.com/ankit-chaubey/tgbotrs-docs
cd tgbotrs-docs

# Run the generator
python3 scripts/generate_docs.py

# Open in browser
open site/index.html
```

### Auto-update from latest tgbotrs source:

```bash
# Pull the latest source files
curl -L https://raw.githubusercontent.com/ankit-chaubey/tgbotrs/main/tgbotrs/src/gen_methods.rs \
  -o tgbotrs/src/gen_methods.rs

curl -L https://raw.githubusercontent.com/ankit-chaubey/tgbotrs/main/tgbotrs/src/gen_types.rs \
  -o tgbotrs/src/gen_types.rs

# Regenerate
python3 scripts/generate_docs.py
```

---

## 📁 Project Structure

```
tgbotrs-docs/
├── .github/
│   └── workflows/
│       └── deploy-docs.yml      # GitHub Actions auto-deploy
├── scripts/
│   └── generate_docs.py         # Doc generator (Python, no deps)
├── tgbotrs/
│   └── src/
│       ├── gen_methods.rs       # 165 methods (auto-generated)
│       ├── gen_types.rs         # 285 types (auto-generated)
│       ├── bot.rs               # Bot struct
│       ├── polling.rs           # Long polling
│       ├── webhook.rs           # Webhook server
│       ├── error.rs             # BotError types
│       ├── chat_id.rs           # ChatId enum
│       ├── reply_markup.rs      # ReplyMarkup enum
│       ├── input_file.rs        # InputFile
│       ├── types.rs             # Hand-crafted types
│       └── lib.rs               # Crate root
├── site/
│   └── index.html               # Generated docs (single file!)
└── README.md
```

---

## 🛠️ How It Works

1. **Python parser** reads the Rust source files
2. Extracts all 165 method signatures, docs, and param structs
3. Extracts all 285 types and 20 enums  
4. Generates working Rust code examples for every method
5. Outputs a **single self-contained `index.html`** — no build tools needed
6. GitHub Actions deploys to GitHub Pages on every push or manual trigger

---

## 📜 License

MIT — Copyright (c) 2024-present [Ankit Chaubey](https://github.com/ankit-chaubey)

---

<div align="center">

🦀 **tgbotrs** — *The complete Rust Telegram Bot library*

[GitHub](https://github.com/ankit-chaubey/tgbotrs) · [crates.io](https://crates.io/crates/tgbotrs) · [docs.rs](https://docs.rs/tgbotrs) · [@ankify](https://t.me/ankify)

</div>
