#!/usr/bin/env python3
"""
tgbotrs Documentation Generator
================================
Parses the tgbotrs Rust source files and generates a complete,
interactive documentation website.

Developed by Ankit Chaubey <ankitchaubey.dev@gmail.com>
GitHub: https://github.com/ankit-chaubey/tgbotrs

Usage:
    python3 scripts/generate_docs.py

Output:
    site/index.html  — The full docs website (self-contained, no build tools)
"""

import re
import json
import os
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR   = SCRIPT_DIR.parent
SRC_DIR    = ROOT_DIR / "tgbotrs" / "src"
SITE_DIR   = ROOT_DIR / "site"

SITE_DIR.mkdir(exist_ok=True)

print("📂 Source dir:", SRC_DIR)
print("📂 Site dir:", SITE_DIR)

# ── Load source files ─────────────────────────────────────────────────────────

def load(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"⚠️  File not found: {path}")
        return ""

gen_methods  = load(SRC_DIR / "gen_methods.rs")
gen_types    = load(SRC_DIR / "gen_types.rs")
hand_types   = load(SRC_DIR / "types.rs")
lib_src      = load(SRC_DIR / "lib.rs")
bot_src      = load(SRC_DIR / "bot.rs")
polling_src  = load(SRC_DIR / "polling.rs")
error_src    = load(SRC_DIR / "error.rs")
webhook_src  = load(SRC_DIR / "webhook.rs")
reply_src    = load(SRC_DIR / "reply_markup.rs")
chat_id_src  = load(SRC_DIR / "chat_id.rs")

print("✅ Source files loaded")

# ── Parse Methods ────────────────────────────────────────────────────────────

def parse_methods(content):
    """Extract all method definitions from gen_methods.rs."""
    # Split into impl Bot blocks
    all_blocks = re.split(r'\nimpl Bot \{', content)
    methods = []

    for block in all_blocks:
        m = re.search(
            r'/// (.*?)\n\s+/// See: (https://[^\n]+)\n\s+pub async fn (\w+)\(\s*&self,?(.*?)\)\s*->\s*Result<([^,\n{]+)',
            block, re.DOTALL)
        if not m:
            continue

        doc     = m.group(1).strip()
        url     = m.group(2).strip()
        name    = m.group(3)
        raw_p   = m.group(4)
        ret     = m.group(5).strip()

        params_clean = re.sub(r'\s+', ' ', raw_p.strip()).rstrip(',')
        param_list   = _parse_param_list(params_clean)

        methods.append({
            'name':       name,
            'doc':        doc,
            'url':        url,
            'params':     params_clean,
            'param_list': param_list,
            'ret':        ret,
        })

    return methods


def _parse_param_list(raw):
    """Split 'name: Type, ...' into list, respecting angle brackets."""
    params = []
    depth, cur = 0, ''
    for ch in raw:
        if ch in '<([': depth += 1
        elif ch in '>)]': depth -= 1
        if ch == ',' and depth == 0:
            _add_param(params, cur)
            cur = ''
        else:
            cur += ch
    _add_param(params, cur)
    return params


def _add_param(lst, raw):
    raw = raw.strip()
    if not raw:
        return
    parts = raw.split(':', 1)
    if len(parts) == 2:
        lst.append({'name': parts[0].strip(), 'type': parts[1].strip()})


# ── Parse Optional Param Structs ─────────────────────────────────────────────

def parse_param_structs(content):
    """Extract optional parameter structs and their fields."""
    pattern = re.compile(
        r'/// Optional parameters for \[`Bot::(\w+)`\]\n'
        r'#\[derive[^\]]+\]\n'
        r'pub struct (\w+) \{(.*?)\}\n',
        re.DOTALL)
    result = {}
    for method, struct_name, fields_raw in pattern.findall(content):
        fields = re.findall(
            r'/// ([^\n]+)\n\s+(?:#\[serde[^\]]+\]\n\s+)?pub (\w+): ([^,\n]+)',
            fields_raw)
        result[method] = {
            'struct': struct_name,
            'fields': [
                {'doc': d.strip(), 'name': n.strip(), 'type': t.strip().rstrip(',')}
                for d, n, t in fields
            ]
        }
    return result


# ── Parse Types ───────────────────────────────────────────────────────────────

def parse_structs(content):
    structs = []
    for name, body in re.findall(r'pub struct (\w+) \{([^}]+)\}', content):
        fields = re.findall(r'pub (\w+): ([^,\n]+)', body)
        structs.append({
            'name':   name,
            'fields': [{'name': n, 'type': t.strip().rstrip(',')} for n, t in fields]
        })
    return structs


def parse_enums(content):
    enums = []
    for name, body in re.findall(r'pub enum (\w+) \{([^}]+)\}', content):
        variants = re.findall(r'\n\s+(\w+)', body)
        enums.append({'name': name, 'variants': variants})
    return enums


# ── Code Example Generator ────────────────────────────────────────────────────

def type_placeholder(t, name=''):
    t = t.strip()
    if t.startswith('Option<'):
        return 'None'
    if t in ('i64', 'i32', 'u64', 'u32'):
        if any(k in name.lower() for k in ('chat', 'user', 'group')):
            return '123456789i64'
        return '0i64'
    if t == 'bool':    return 'true'
    if t in ('f64', 'f32'): return '0.0'
    if 'Into<String>' in t or t in ('String', '&str'):
        if 'token'   in name.lower(): return '"YOUR_BOT_TOKEN"'
        if any(k in name.lower() for k in ('text','message','caption')): return '"Hello from tgbotrs! 🦀"'
        if 'url'     in name.lower(): return '"https://example.com"'
        if 'chat_id' in name.lower(): return '"@yourchannel"'
        if 'name'    in name.lower(): return '"my_name"'
        return '"example"'
    if 'Into<ChatId>' in t: return '123456789i64'
    if t.startswith('Vec<'):
        inner = t[4:-1]
        return f'vec![]  // Vec<{inner}>'
    if t[0:1].isupper():
        return f'{t}::default()'
    return 'todo!()'


def generate_example(method, params_map):
    name       = method['name']
    param_list = method['param_list']
    has_opt    = name in params_map

    imports = ['use tgbotrs::{Bot, BotError};']
    if has_opt:
        s = params_map[name]['struct']
        imports.append(f'use tgbotrs::gen_methods::{{{s}}};')

    lines = imports + ['', '#[tokio::main]', 'async fn main() -> Result<(), BotError> {',
                       '    let bot = Bot::new("YOUR_BOT_TOKEN").await?;', '']

    call_args = []
    for p in param_list:
        pname, ptype = p['name'], p['type']
        if pname == 'params' and has_opt:
            pstruct = params_map[name]['struct']
            fields  = params_map[name].get('fields', [])
            if fields:
                chain = [f'    let params = {pstruct}::new()']
                for f in fields[:3]:
                    val = type_placeholder(f['type'], f['name'])
                    chain.append(f'        .{f["name"]}({val})')
                chain[-1] += ';'
                lines.append('    // Optional parameters')
                lines.extend(chain)
            else:
                lines.append(f'    let params = {pstruct}::new();')
            lines.append('')
            call_args.append('Some(params)')
        else:
            val = type_placeholder(ptype, pname)
            lines.append(f'    let {pname} = {val};')
            call_args.append(pname)

    lines.append('')
    args_str = ',\n        '.join(call_args)
    if call_args:
        lines.append(f'    let result = bot.{name}(\n        {args_str}\n    ).await?;')
    else:
        lines.append(f'    let result = bot.{name}().await?;')

    lines += ['    println!("Result: {result:?}");', '    Ok(())', '}']
    return '\n'.join(lines)


# ── Category Logic ────────────────────────────────────────────────────────────

CATEGORY_ORDER = [
    'Sending Messages', 'Getting Info', 'Editing', 'Deletion',
    'Forwarding & Copying', 'Answering Queries', 'Chat Administration',
    'Invite & Membership', 'Pinning', 'Configuration', 'Updates & Webhook',
    'Stickers', 'Forum Topics', 'Games', 'Payments & Stars',
    'Stories', 'Business', 'Other',
]

def categorize(name):
    n = name.lower()
    if n.startswith('send_'):               return 'Sending Messages'
    if n.startswith('get_'):                return 'Getting Info'
    if n.startswith('set_'):                return 'Configuration'
    if n.startswith('edit_'):               return 'Editing'
    if n.startswith('delete_'):             return 'Deletion'
    if n.startswith(('forward_', 'copy_')): return 'Forwarding & Copying'
    if n.startswith('answer_'):             return 'Answering Queries'
    if n.startswith(('ban_', 'unban_', 'restrict_', 'promote_')): return 'Chat Administration'
    if n.startswith(('create_', 'approve_', 'decline_', 'revoke_')): return 'Invite & Membership'
    if n.startswith(('pin_', 'unpin_')):    return 'Pinning'
    if 'sticker' in n or 'emoji' in n:     return 'Stickers'
    if 'forum' in n:                        return 'Forum Topics'
    if n in ('close', 'get_updates') or 'webhook' in n: return 'Updates & Webhook'
    if 'game' in n:                         return 'Games'
    if any(k in n for k in ('invoice', 'payment', 'shipping', 'star', 'gift', 'premium')): return 'Payments & Stars'
    if 'story' in n:                        return 'Stories'
    if 'business' in n:                     return 'Business'
    return 'Other'


# ── HTML Helpers ──────────────────────────────────────────────────────────────

def h(s):
    return (str(s)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def slug(name):
    return name.replace('_', '-')


# ── Build HTML Fragments ──────────────────────────────────────────────────────

def build_method_cards(categories, params_map, examples):
    html = ''
    for cat in CATEGORY_ORDER:
        if cat not in categories:
            continue
        cat_id = cat.lower().replace(' ', '-').replace('&', 'and')
        methods = categories[cat]
        html += f'''
    <section class="cat-section" id="cat-{cat_id}">
      <div class="cat-header">
        <h2 class="cat-title">{h(cat)}</h2>
        <span class="cat-count">{len(methods)} methods</span>
      </div>
      <div class="methods-grid">
'''
        for m in methods:
            name = m['name']
            s    = slug(name)
            doc  = h(m['doc'][:160] + ('…' if len(m['doc']) > 160 else ''))
            ret  = h(m['ret'])
            has_opt = name in params_map

            param_pills = ''.join(
                f'<span class="param-pill {"optional" if "Option<" in p["type"] or p["name"]=="params" else "required"}" '
                f'title="{h(p["type"])}">{h(p["name"])}</span>'
                for p in m['param_list']
            ) or '<span class="no-params">no parameters</span>'

            opt_html = ''
            if has_opt:
                fields = params_map[name].get('fields', [])
                rows   = ''.join(
                    f'<tr><td class="field-name">{h(f["name"])}</td>'
                    f'<td class="field-type">{h(f["type"])}</td>'
                    f'<td class="field-doc">{h(f.get("doc",""))}</td></tr>'
                    for f in fields[:10]
                )
                if len(fields) > 10:
                    rows += f'<tr><td colspan="3" class="more-fields">+{len(fields)-10} more fields…</td></tr>'
                struct_name = params_map[name]['struct']
                opt_html = f'''
            <div class="optional-section">
              <div class="section-label">Optional params — <code>{h(struct_name)}</code></div>
              <table class="fields-table">
                <thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
                <tbody>{rows}</tbody>
              </table>
            </div>'''

            code = h(examples.get(name, '// example not available'))

            html += f'''
        <div class="method-card" id="method-{s}" data-name="{name}" data-cat="{h(cat)}">
          <div class="method-header">
            <div class="method-name-row">
              <a class="method-name" href="#method-{s}">bot.{name}()</a>
              <div class="method-badges">
                <span class="badge badge-async">async</span>
                <span class="badge badge-ret">→ {ret}</span>
                {'<span class="badge badge-opt">+optional</span>' if has_opt else ''}
              </div>
            </div>
            <p class="method-doc">{doc}</p>
          </div>
          <div class="method-body">
            <div class="params-section">
              <div class="section-label">Parameters</div>
              <div class="param-pills">{param_pills}</div>
            </div>
            {opt_html}
            <div class="example-section">
              <div class="example-header">
                <div class="section-label">Example</div>
                <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
              </div>
              <pre class="code-block"><code class="language-rust">{code}</code></pre>
            </div>
            <div class="method-footer">
              <a href="{h(m["url"])}" target="_blank" class="tg-link">📖 Telegram Docs ↗</a>
              <a href="#method-{s}" class="anchor-link">🔗 Direct link</a>
            </div>
          </div>
        </div>
'''
        html += '      </div>\n    </section>\n'
    return html


def build_sidebar(categories):
    html = ''
    for cat in CATEGORY_ORDER:
        if cat not in categories:
            continue
        cat_id = cat.lower().replace(' ', '-').replace('&', 'and')
        methods = categories[cat]
        html += f'''
      <div class="sidebar-cat">
        <button class="cat-toggle" onclick="toggleCat(this)" data-cat-id="{cat_id}">
          <span class="cat-name">{h(cat)}</span>
          <span class="cat-cnt">{len(methods)}</span>
          <span class="cat-arrow">▾</span>
        </button>
        <div class="cat-methods collapsed" id="sidebar-{cat_id}">
'''
        for m in methods:
            s = slug(m['name'])
            html += f'          <a href="#method-{s}" class="sidebar-method">{h(m["name"])}</a>\n'
        html += '        </div>\n      </div>\n'
    return html


def build_types_html(types_list):
    html = ''
    for t in types_list[:60]:
        name = h(t['name'])
        fields = ''.join(
            f'<div class="type-field">'
            f'<span class="type-field-name">{h(f["name"])}</span>'
            f'<span class="type-field-type">{h(f["type"])}</span>'
            f'</div>'
            for f in t['fields'][:6]
        )
        if len(t['fields']) > 6:
            fields += f'<div class="type-more">+{len(t["fields"])-6} more…</div>'
        html += f'''
    <div class="type-card" id="type-{name.lower()}">
      <div class="type-name">{name}</div>
      <div class="type-fields">{fields}</div>
    </div>
'''
    return html


def build_enums_html(enums_list):
    html = ''
    for e in enums_list:
        name = h(e['name'])
        variants = ' '.join(
            f'<span class="enum-variant">{h(v)}</span>'
            for v in e['variants'][:12]
        )
        html += f'''
    <div class="enum-card" id="enum-{name.lower()}">
      <div class="enum-name">{name}</div>
      <div class="enum-variants">{variants}</div>
    </div>
'''
    return html


# ── Main Generation ───────────────────────────────────────────────────────────

print("\n🔍 Parsing methods...")
methods = parse_methods(gen_methods)
print(f"   Found {len(methods)} methods")

print("🔍 Parsing param structs...")
params_map = parse_param_structs(gen_methods)
print(f"   Found {len(params_map)} optional param structs")

print("🔍 Parsing types...")
types_structs = parse_structs(gen_types)
types_enums   = parse_enums(gen_types)
hand_structs  = parse_structs(hand_types)
hand_enums    = parse_enums(hand_types)
all_structs   = types_structs + hand_structs
all_enums     = types_enums + hand_enums
print(f"   Found {len(all_structs)} structs, {len(all_enums)} enums")

print("🔧 Generating code examples...")
examples = {m['name']: generate_example(m, params_map) for m in methods}
print(f"   Generated {len(examples)} examples")

print("📂 Categorizing methods...")
categories: dict = {}
for m in methods:
    cat = categorize(m['name'])
    categories.setdefault(cat, []).append(m)
for cat, ms in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"   {cat}: {len(ms)}")

print("\n🏗️  Building HTML fragments...")
method_cards = build_method_cards(categories, params_map, examples)
sidebar_html = build_sidebar(categories)
types_html   = build_types_html(all_structs)
enums_html   = build_enums_html(all_enums)

stats = {
    'methods': len(methods),
    'types':   len(all_structs),
    'enums':   len(all_enums),
    'param_structs': len(params_map),
}

# ── Assemble Full Page ────────────────────────────────────────────────────────

def assemble(method_cards, sidebar_html, types_html, enums_html, stats):
    S = stats
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>tgbotrs — Telegram Bot API for Rust</title>
  <meta name="description" content="Complete docs for tgbotrs — {S["methods"]} methods, {S["types"]} types, fully async. By Ankit Chaubey.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
  <style>
    :root {{
      --bg:#0d0f17;--bg2:#131622;--bg3:#1a1d2e;--bg4:#21253a;
      --border:#2a2f47;--border-bright:#3d4468;
      --accent:#7c6af7;--accent-h:#9585ff;--accent2:#38bdf8;--accent3:#34d399;--accent4:#f87171;
      --text:#e2e8f0;--text-dim:#94a3b8;--text-muted:#64748b;
      --rust:#f97316;--yellow:#fbbf24;--green:#4ade80;--red:#f87171;--blue:#60a5fa;--purple:#c084fc;
      --sidebar-w:280px;--header-h:64px;--radius:12px;--radius-sm:8px;
    }}
    *{{margin:0;padding:0;box-sizing:border-box}}
    html{{scroll-behavior:smooth}}
    body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6}}
    ::-webkit-scrollbar{{width:6px;height:6px}}
    ::-webkit-scrollbar-track{{background:var(--bg2)}}
    ::-webkit-scrollbar-thumb{{background:var(--border-bright);border-radius:3px}}
    ::-webkit-scrollbar-thumb:hover{{background:var(--accent)}}

    .top-header{{position:fixed;top:0;left:0;right:0;z-index:100;height:var(--header-h);background:rgba(13,15,23,.92);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;gap:24px}}
    .logo{{display:flex;align-items:center;gap:10px;text-decoration:none;flex-shrink:0}}
    .logo-icon{{width:38px;height:38px;background:linear-gradient(135deg,var(--accent),#e879f9);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800;color:#fff;box-shadow:0 2px 12px rgba(124,106,247,.4)}}
    .logo-text{{font-size:18px;font-weight:800;color:var(--text)}}
    .logo-version{{font-size:11px;color:var(--accent);background:rgba(124,106,247,.12);padding:2px 7px;border-radius:100px;font-weight:600}}
    .header-search{{flex:1;max-width:440px;position:relative}}
    .header-search input{{width:100%;padding:8px 16px 8px 40px;background:var(--bg3);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;font-family:inherit;transition:border-color .2s,box-shadow .2s;outline:none}}
    .header-search input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(124,106,247,.12)}}
    .header-search input::placeholder{{color:var(--text-muted)}}
    .search-icon{{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:14px}}
    .header-nav{{display:flex;align-items:center;gap:4px;margin-left:auto}}
    .header-nav a{{padding:6px 12px;border-radius:var(--radius-sm);color:var(--text-dim);text-decoration:none;font-size:13px;font-weight:500;transition:color .2s,background .2s;white-space:nowrap}}
    .header-nav a:hover{{color:var(--text);background:var(--bg3)}}
    .header-nav .btn-gh{{background:var(--accent);color:#fff;padding:6px 14px}}
    .header-nav .btn-gh:hover{{background:var(--accent-h)}}
    .layout{{display:flex;padding-top:var(--header-h);min-height:100vh}}
    .sidebar{{position:fixed;top:var(--header-h);bottom:0;left:0;width:var(--sidebar-w);overflow-y:auto;background:var(--bg2);border-right:1px solid var(--border);padding:16px 0 40px}}
    .sidebar-section-title{{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--text-muted);padding:12px 18px 6px}}
    .sidebar-link{{display:flex;align-items:center;gap:8px;padding:7px 18px;color:var(--text-dim);text-decoration:none;font-size:13px;font-weight:500;transition:color .15s,background .15s}}
    .sidebar-link:hover,.sidebar-link.active{{color:var(--text);background:var(--bg3)}}
    .sidebar-link .dot{{width:5px;height:5px;border-radius:50%;background:var(--accent);opacity:.6;flex-shrink:0}}
    .sidebar-divider{{height:1px;background:var(--border);margin:12px 0}}
    .cat-toggle{{width:100%;display:flex;align-items:center;padding:7px 18px;background:none;border:none;cursor:pointer;color:var(--text-dim);font-size:12px;font-weight:600;font-family:inherit;transition:color .15s,background .15s;letter-spacing:.02em}}
    .cat-toggle:hover{{color:var(--text);background:var(--bg3)}}
    .cat-name{{flex:1;text-align:left}}
    .cat-cnt{{font-size:10px;background:var(--bg4);color:var(--text-muted);padding:1px 6px;border-radius:100px;margin-right:6px}}
    .cat-arrow{{transition:transform .2s;font-size:11px}}
    .cat-toggle.open .cat-arrow{{transform:rotate(180deg)}}
    .cat-methods{{overflow:hidden;transition:max-height .25s ease;max-height:2000px}}
    .cat-methods.collapsed{{max-height:0}}
    .sidebar-method{{display:block;padding:4px 18px 4px 32px;color:var(--text-muted);text-decoration:none;font-size:12px;font-family:'JetBrains Mono',monospace;transition:color .15s,background .15s}}
    .sidebar-method:hover{{color:var(--accent);background:var(--bg3)}}
    .main{{margin-left:var(--sidebar-w);flex:1;min-width:0}}
    .hero{{background:linear-gradient(135deg,#0d0f17,#131622 50%,#1a1020);border-bottom:1px solid var(--border);padding:64px 48px;position:relative;overflow:hidden}}
    .hero::before{{content:'';position:absolute;top:-60px;right:-60px;width:400px;height:400px;background:radial-gradient(circle,rgba(124,106,247,.12),transparent 70%);pointer-events:none}}
    .hero::after{{content:'';position:absolute;bottom:-80px;left:100px;width:300px;height:300px;background:radial-gradient(circle,rgba(56,189,248,.08),transparent 70%);pointer-events:none}}
    .hero-content{{position:relative;z-index:1;max-width:780px}}
    .hero-badge{{display:inline-flex;align-items:center;gap:6px;background:rgba(124,106,247,.12);border:1px solid rgba(124,106,247,.25);color:var(--accent);padding:4px 12px;border-radius:100px;font-size:12px;font-weight:600;margin-bottom:20px}}
    .hero h1{{font-size:52px;font-weight:900;line-height:1.1;letter-spacing:-.03em;margin-bottom:16px}}
    .hero h1 .grad{{background:linear-gradient(135deg,var(--accent),#e879f9,var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
    .hero-desc{{font-size:17px;color:var(--text-dim);margin-bottom:32px;max-width:600px;line-height:1.7}}
    .hero-stats{{display:flex;gap:32px;flex-wrap:wrap;margin-bottom:36px}}
    .stat-item{{display:flex;flex-direction:column;gap:2px}}
    .stat-num{{font-size:28px;font-weight:800;color:var(--text)}}
    .stat-label{{font-size:12px;color:var(--text-muted);font-weight:500;letter-spacing:.04em}}
    .hero-btns{{display:flex;gap:12px;flex-wrap:wrap}}
    .btn{{display:inline-flex;align-items:center;gap:8px;padding:11px 22px;border-radius:var(--radius-sm);font-size:14px;font-weight:600;text-decoration:none;transition:all .2s;cursor:pointer;border:none;font-family:inherit}}
    .btn-filled{{background:var(--accent);color:#fff;box-shadow:0 4px 16px rgba(124,106,247,.3)}}
    .btn-filled:hover{{background:var(--accent-h);transform:translateY(-1px);box-shadow:0 8px 24px rgba(124,106,247,.4)}}
    .btn-outline{{background:transparent;border:1px solid var(--border-bright);color:var(--text-dim)}}
    .btn-outline:hover{{border-color:var(--accent);color:var(--accent);background:rgba(124,106,247,.06)}}
    .section{{padding:48px;border-bottom:1px solid var(--border)}}
    .section-h2{{font-size:26px;font-weight:800;margin-bottom:8px;display:flex;align-items:center;gap:10px}}
    .section-sub{{color:var(--text-dim);font-size:14px;margin-bottom:28px}}
    .install-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
    .install-card{{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px;overflow:hidden}}
    .install-card-title{{font-size:13px;font-weight:700;color:var(--text-dim);margin-bottom:12px;text-transform:uppercase;letter-spacing:.06em}}
    .features-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
    .feature-card{{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px;transition:border-color .2s,transform .2s}}
    .feature-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
    .feature-icon{{font-size:28px;margin-bottom:10px}}
    .feature-title{{font-size:15px;font-weight:700;margin-bottom:6px}}
    .feature-desc{{font-size:13px;color:var(--text-dim);line-height:1.6}}
    .filter-bar{{padding:20px 48px;background:var(--bg2);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;flex-wrap:wrap;position:sticky;top:var(--header-h);z-index:50}}
    .filter-label{{font-size:12px;color:var(--text-muted);font-weight:600}}
    .filter-chip{{padding:5px 12px;border-radius:100px;background:var(--bg3);border:1px solid var(--border);color:var(--text-dim);font-size:12px;font-weight:500;cursor:pointer;transition:all .15s;white-space:nowrap}}
    .filter-chip:hover,.filter-chip.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
    .results-count{{margin-left:auto;font-size:12px;color:var(--text-muted)}}
    .cat-section{{padding:0 48px 40px}}
    .cat-header{{display:flex;align-items:baseline;gap:12px;padding:40px 0 20px;border-bottom:1px solid var(--border);margin-bottom:24px}}
    .cat-title{{font-size:20px;font-weight:800}}
    .cat-count{{font-size:12px;background:var(--bg3);border:1px solid var(--border);padding:2px 8px;border-radius:100px;color:var(--text-muted)}}
    .methods-grid{{display:flex;flex-direction:column;gap:16px}}
    .method-card{{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:border-color .2s,box-shadow .2s;scroll-margin-top:calc(var(--header-h) + 60px)}}
    .method-card:hover{{border-color:var(--border-bright);box-shadow:0 2px 16px rgba(0,0,0,.3)}}
    .method-card:target{{border-color:var(--accent);box-shadow:0 0 0 2px rgba(124,106,247,.15)}}
    .method-header{{padding:18px 22px 14px;border-bottom:1px solid var(--border)}}
    .method-name-row{{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:6px}}
    .method-name{{font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:600;color:var(--accent);text-decoration:none}}
    .method-name:hover{{color:var(--accent-h);text-decoration:underline}}
    .method-badges{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
    .badge{{font-size:10px;font-weight:700;padding:2px 7px;border-radius:100px;letter-spacing:.04em}}
    .badge-async{{background:rgba(56,189,248,.12);color:var(--accent2);border:1px solid rgba(56,189,248,.2)}}
    .badge-ret{{background:rgba(52,211,153,.1);color:var(--accent3);border:1px solid rgba(52,211,153,.2);font-family:'JetBrains Mono',monospace}}
    .badge-opt{{background:rgba(251,191,36,.1);color:var(--yellow);border:1px solid rgba(251,191,36,.2)}}
    .method-doc{{font-size:13px;color:var(--text-dim);line-height:1.6;max-width:700px}}
    .method-body{{padding:0}}
    .params-section{{padding:14px 22px;border-bottom:1px solid var(--border)}}
    .optional-section{{padding:14px 22px;border-bottom:1px solid var(--border);overflow-x:auto}}
    .example-section{{padding:14px 22px;border-bottom:1px solid var(--border)}}
    .section-label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--text-muted);margin-bottom:8px}}
    .param-pills{{display:flex;flex-wrap:wrap;gap:6px}}
    .param-pill{{font-family:'JetBrains Mono',monospace;font-size:11px;padding:3px 9px;border-radius:6px;cursor:help}}
    .param-pill.required{{background:rgba(124,106,247,.12);color:var(--accent);border:1px solid rgba(124,106,247,.2)}}
    .param-pill.optional{{background:rgba(100,116,139,.08);color:var(--text-muted);border:1px solid var(--border)}}
    .no-params{{font-size:12px;color:var(--text-muted);font-style:italic}}
    .fields-table{{width:100%;border-collapse:collapse;font-size:12px}}
    .fields-table th{{text-align:left;padding:6px 10px;background:var(--bg3);color:var(--text-muted);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--border)}}
    .fields-table td{{padding:5px 10px;vertical-align:top;border-bottom:1px solid rgba(42,47,71,.5)}}
    .field-name{{font-family:'JetBrains Mono',monospace;color:var(--accent3);font-size:11px;white-space:nowrap}}
    .field-type{{font-family:'JetBrains Mono',monospace;color:var(--blue);font-size:11px}}
    .field-doc{{color:var(--text-muted);line-height:1.5}}
    .more-fields{{color:var(--text-muted);font-style:italic;padding:4px 10px}}
    .example-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
    .copy-btn{{font-size:11px;padding:4px 10px;border-radius:6px;background:var(--bg4);border:1px solid var(--border);color:var(--text-dim);cursor:pointer;font-family:inherit;transition:all .15s}}
    .copy-btn:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
    .copy-btn.copied{{background:var(--green);color:#000;border-color:var(--green)}}
    .code-block{{background:#1a1b2e!important;border-radius:var(--radius-sm);overflow:auto;font-size:12.5px;line-height:1.6;border:1px solid var(--border);margin:0}}
    .code-block code{{padding:14px 18px;display:block;font-family:'JetBrains Mono',monospace}}
    .method-footer{{padding:10px 22px;display:flex;gap:16px;align-items:center}}
    .tg-link,.anchor-link{{font-size:12px;color:var(--text-muted);text-decoration:none;transition:color .15s}}
    .tg-link:hover{{color:var(--accent2)}}
    .anchor-link:hover{{color:var(--accent)}}
    .types-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:16px}}
    .type-card{{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;transition:border-color .15s;scroll-margin-top:calc(var(--header-h) + 60px)}}
    .type-card:hover{{border-color:var(--border-bright)}}
    .type-name{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--purple);margin-bottom:8px}}
    .type-field{{display:flex;justify-content:space-between;gap:8px;padding:2px 0}}
    .type-field-name{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent3)}}
    .type-field-type{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--blue);opacity:.8}}
    .type-more{{font-size:11px;color:var(--text-muted);font-style:italic;padding-top:4px}}
    .enums-grid{{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}}
    .enum-card{{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px}}
    .enum-name{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--yellow);margin-bottom:8px}}
    .enum-variants{{display:flex;flex-wrap:wrap;gap:4px}}
    .enum-variant{{font-family:'JetBrains Mono',monospace;font-size:11px;background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.15);color:var(--yellow);padding:1px 7px;border-radius:4px}}
    .error-section{{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:16px}}
    .error-variant{{margin-bottom:20px}}
    .error-variant-name{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:600;color:var(--red);margin-bottom:4px}}
    .error-variant-desc{{font-size:13px;color:var(--text-dim)}}
    .tabs{{display:flex;gap:2px;border-bottom:1px solid var(--border);margin-bottom:24px}}
    .tab{{padding:10px 20px;border-radius:var(--radius-sm) var(--radius-sm) 0 0;font-size:13px;font-weight:600;cursor:pointer;color:var(--text-muted);background:none;border:none;font-family:inherit;border-bottom:2px solid transparent;transition:all .15s}}
    .tab:hover{{color:var(--text)}}
    .tab.active{{color:var(--accent);border-bottom-color:var(--accent)}}
    .tab-panel{{display:none}}
    .tab-panel.active{{display:block}}
    .method-card.hidden{{display:none}}
    .hljs{{background:transparent!important}}
    .footer{{margin-left:var(--sidebar-w);padding:40px 48px;border-top:1px solid var(--border);background:var(--bg2);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px}}
    .footer-links{{display:flex;gap:20px}}
    .footer-links a{{font-size:13px;color:var(--text-muted);text-decoration:none}}
    .footer-links a:hover{{color:var(--accent)}}
    @media(max-width:900px){{
      :root{{--sidebar-w:0px}}
      .sidebar,.header-nav{{display:none}}
      .footer{{margin-left:0}}
      .hero{{padding:40px 24px}}
      .hero h1{{font-size:36px}}
      .section{{padding:32px 24px}}
      .filter-bar{{padding:16px 24px}}
      .cat-section{{padding:0 24px 32px}}
      .install-grid,.features-grid{{grid-template-columns:1fr}}
    }}
  </style>
</head>
<body>

<header class="top-header">
  <a class="logo" href="#">
    <div class="logo-icon">🦀</div>
    <span class="logo-text">tgbotrs</span>
    <span class="logo-version">v0.1.4</span>
  </a>
  <div class="header-search">
    <span class="search-icon">🔍</span>
    <input type="text" id="globalSearch" placeholder="Search methods, types… (Ctrl+K)" autocomplete="off">
  </div>
  <nav class="header-nav">
    <a href="#quick-start">Quick Start</a>
    <a href="#methods">Methods</a>
    <a href="#types">Types</a>
    <a href="#errors">Errors</a>
    <a href="https://github.com/ankit-chaubey/tgbotrs" target="_blank" class="btn-gh">⭐ GitHub</a>
  </nav>
</header>

<div class="layout">
<aside class="sidebar">
  <div class="sidebar-section-title">Navigation</div>
  <a class="sidebar-link" href="#quick-start"><span class="dot"></span>Quick Start</a>
  <a class="sidebar-link" href="#installation"><span class="dot"></span>Installation</a>
  <a class="sidebar-link" href="#features"><span class="dot"></span>Features</a>
  <a class="sidebar-link" href="#methods"><span class="dot"></span>All Methods</a>
  <a class="sidebar-link" href="#types"><span class="dot"></span>Types ({S["types"]})</a>
  <a class="sidebar-link" href="#errors"><span class="dot"></span>Error Handling</a>
  <a class="sidebar-link" href="#polling"><span class="dot"></span>Long Polling</a>
  <a class="sidebar-link" href="#webhook"><span class="dot"></span>Webhook</a>
  <div class="sidebar-divider"></div>
  <div class="sidebar-section-title">Methods by Category</div>
  {sidebar_html}
</aside>

<main class="main">
  <div class="hero">
    <div class="hero-content">
      <div class="hero-badge">🦀 Telegram Bot API 9.4 · Fully Auto-Generated</div>
      <h1>The <span class="grad">complete</span> Rust<br>Telegram Bot library</h1>
      <p class="hero-desc"><strong>tgbotrs</strong> gives you every Telegram Bot API method and type — fully typed, fully async, auto-generated from the official spec. Built with Tokio, powered by Rust's safety guarantees.</p>
      <div class="hero-stats">
        <div class="stat-item"><span class="stat-num">{S["methods"]}</span><span class="stat-label">Methods</span></div>
        <div class="stat-item"><span class="stat-num">{S["types"]}</span><span class="stat-label">Types</span></div>
        <div class="stat-item"><span class="stat-num">9.4</span><span class="stat-label">API Version</span></div>
        <div class="stat-item"><span class="stat-num">100%</span><span class="stat-label">Async</span></div>
      </div>
      <div class="hero-btns">
        <a href="#quick-start" class="btn btn-filled">🚀 Get Started</a>
        <a href="https://crates.io/crates/tgbotrs" target="_blank" class="btn btn-outline">📦 crates.io</a>
        <a href="https://docs.rs/tgbotrs" target="_blank" class="btn btn-outline">📖 docs.rs</a>
        <a href="https://github.com/ankit-chaubey/tgbotrs" target="_blank" class="btn btn-outline">★ GitHub</a>
      </div>
    </div>
  </div>

  <section class="section" id="quick-start">
    <h2 class="section-h2">🚀 Quick Start</h2>
    <p class="section-sub">Get your first bot running in under 2 minutes.</p>
    <div style="display:flex;flex-direction:column;gap:16px;max-width:780px">
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
        <div style="font-size:13px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px">Step 1 — Get your bot token</div>
        <div style="font-size:13px;color:var(--text-dim)">Chat with <a href="https://t.me/BotFather" target="_blank" style="color:var(--accent2)">@BotFather</a> on Telegram → /newbot → copy your token.</div>
      </div>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
        <div style="font-size:13px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px">Step 2 — Cargo.toml</div>
        <div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Cargo.toml</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
        <pre class="code-block"><code class="language-toml">[dependencies]
tgbotrs = "0.1"
tokio   = {{ version = "1", features = ["full"] }}</code></pre>
      </div>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
        <div style="font-size:13px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px">Step 3 — src/main.rs</div>
        <div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">src/main.rs</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
        <pre class="code-block"><code class="language-rust">use tgbotrs::{{Bot, Poller, UpdateHandler}};

#[tokio::main]
async fn main() {{
    let bot = Bot::new("YOUR_BOT_TOKEN").await.unwrap();
    println!("Running as @{{}}", bot.me.username.as_deref().unwrap_or("?"));

    let handler: UpdateHandler = Box::new(|bot, update| {{
        Box::pin(async move {{
            let Some(msg) = update.message else {{ return }};
            let Some(text) = msg.text else {{ return }};
            let reply = match text.as_str() {{
                "/start" => "👋 Hello! Powered by tgbotrs 🦀".to_string(),
                "/help"  => "/start /help".to_string(),
                other    => format!("Echo: {{}}", other),
            }};
            let _ = bot.send_message(msg.chat.id, reply, None).await;
        }})
    }});

    Poller::new(bot, handler).timeout(30).start().await.unwrap();
}}</code></pre>
      </div>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
        <div style="font-size:13px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px">Step 4 — Run</div>
        <div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Terminal</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
        <pre class="code-block"><code class="language-bash">cargo run</code></pre>
      </div>
    </div>
  </section>

  <section class="section" id="installation">
    <h2 class="section-h2">📦 Installation</h2>
    <p class="section-sub">Full Cargo.toml configurations for every use-case.</p>
    <div class="install-grid">
      <div class="install-card">
        <div class="install-card-title">Standard (Long Polling)</div>
        <div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Cargo.toml</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
        <pre class="code-block"><code class="language-toml">[dependencies]
tgbotrs = "0.1"
tokio   = {{ version = "1", features = ["full"] }}</code></pre>
      </div>
      <div class="install-card">
        <div class="install-card-title">With Webhook Feature</div>
        <div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Cargo.toml</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
        <pre class="code-block"><code class="language-toml">[dependencies]
tgbotrs = {{ version = "0.1", features = ["webhook"] }}
tokio   = {{ version = "1", features = ["full"] }}</code></pre>
      </div>
      <div class="install-card">
        <div class="install-card-title">Dependencies Included</div>
        <div style="font-size:13px;color:var(--text-dim);line-height:1.9">
          ✅ reqwest (HTTP client)<br>
          ✅ serde + serde_json<br>
          ✅ tokio (async runtime)<br>
          ✅ thiserror (error types)<br>
          🔌 axum (webhook only)
        </div>
      </div>
      <div class="install-card">
        <div class="install-card-title">Env-based Token</div>
        <div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">src/main.rs</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
        <pre class="code-block"><code class="language-rust">let token = std::env::var("BOT_TOKEN")
    .expect("BOT_TOKEN not set");
let bot = Bot::new(token).await?;</code></pre>
      </div>
    </div>
  </section>

  <section class="section" id="features">
    <h2 class="section-h2">✨ Features</h2>
    <p class="section-sub">Everything you need to build powerful Telegram bots in Rust.</p>
    <div class="features-grid">
      <div class="feature-card"><div class="feature-icon">⚡</div><div class="feature-title">Fully Async</div><div class="feature-desc">Built on Tokio. Every API call is non-blocking. Handle thousands of concurrent updates.</div></div>
      <div class="feature-card"><div class="feature-icon">🔒</div><div class="feature-title">Strongly Typed</div><div class="feature-desc">Every method, parameter, and response is strongly typed. Catch mistakes at compile time.</div></div>
      <div class="feature-card"><div class="feature-icon">🤖</div><div class="feature-title">Auto-Generated</div><div class="feature-desc">All {S["methods"]} methods and {S["types"]} types auto-generated from the official Telegram API spec. Always up to date.</div></div>
      <div class="feature-card"><div class="feature-icon">🏗️</div><div class="feature-title">Builder Pattern</div><div class="feature-desc">Optional params use ergonomic builder structs. Chain like <code style="background:var(--bg4);padding:1px 5px;border-radius:3px">.parse_mode("HTML")</code>.</div></div>
      <div class="feature-card"><div class="feature-icon">🪝</div><div class="feature-title">Built-in Webhook</div><div class="feature-desc">Optional axum-based webhook server. One line to switch from polling to webhooks.</div></div>
      <div class="feature-card"><div class="feature-icon">📁</div><div class="feature-title">File Uploads</div><div class="feature-desc">Upload by path, URL, or bytes. InputFile handles multipart transparently.</div></div>
      <div class="feature-card"><div class="feature-icon">🎯</div><div class="feature-title">ChatId Flexibility</div><div class="feature-desc">Pass IDs as i64, &str, or @username — ChatId handles all conversions automatically.</div></div>
      <div class="feature-card"><div class="feature-icon">🎮</div><div class="feature-title">All Keyboard Types</div><div class="feature-desc">InlineKeyboard, ReplyKeyboard, ForceReply — all four keyboard types fully supported.</div></div>
      <div class="feature-card"><div class="feature-icon">🔧</div><div class="feature-title">Custom API Server</div><div class="feature-desc">Use <code style="background:var(--bg4);padding:1px 5px;border-radius:3px">Bot::with_api_url()</code> to point at your own local Bot API server.</div></div>
    </div>
  </section>

  <section class="section" id="polling">
    <h2 class="section-h2">🔄 Long Polling</h2>
    <p class="section-sub">The simplest way to receive updates — no external server needed.</p>
    <div style="max-width:780px">
      <div class="example-header" style="margin-bottom:8px"><span style="font-size:13px;font-weight:700;color:var(--text-dim)">Polling with inline keyboard + callback handler</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
      <pre class="code-block"><code class="language-rust">use tgbotrs::{{Bot, Poller, UpdateHandler}};
use tgbotrs::gen_methods::{{SendMessageParams, AnswerCallbackQueryParams}};
use tgbotrs::types::{{InlineKeyboardMarkup, InlineKeyboardButton}};
use tgbotrs::ReplyMarkup;

#[tokio::main]
async fn main() {{
    let bot = Bot::new("YOUR_BOT_TOKEN").await.unwrap();

    let handler: UpdateHandler = Box::new(|bot, update| {{
        Box::pin(async move {{
            if let Some(msg) = update.message {{
                if msg.text.as_deref() == Some("/start") {{
                    let keyboard = ReplyMarkup::InlineKeyboard(InlineKeyboardMarkup {{
                        inline_keyboard: vec![vec![
                            InlineKeyboardButton {{
                                text: "🔵 Primary Button".into(),
                                callback_data: Some("btn1".into()),
                                style: Some("primary".into()),
                                ..Default::default()
                            }},
                            InlineKeyboardButton {{
                                text: "🟢 Success".into(),
                                callback_data: Some("btn2".into()),
                                style: Some("success".into()),
                                ..Default::default()
                            }},
                        ]]
                    }});
                    let params = SendMessageParams::new()
                        .parse_mode("HTML".to_string())
                        .reply_markup(keyboard);
                    let _ = bot.send_message(msg.chat.id, "&lt;b&gt;Hello!&lt;/b&gt; Pick a button 👇", Some(params)).await;
                }}
            }}
            if let Some(cq) = update.callback_query {{
                let _ = bot.answer_callback_query(
                    cq.id,
                    Some(AnswerCallbackQueryParams::new().text("Button clicked! ✅".to_string()))
                ).await;
            }}
        }})
    }});

    Poller::new(bot, handler)
        .timeout(30).limit(100)
        .allowed_updates(vec!["message".into(), "callback_query".into()])
        .start().await.unwrap();
}}</code></pre>
      <div style="margin-top:20px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
        <div style="font-size:13px;font-weight:700;color:var(--text-dim);margin-bottom:12px">Poller Configuration</div>
        <table class="fields-table">
          <thead><tr><th>Method</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td class="field-name">.timeout(30)</td><td class="field-type">30</td><td class="field-doc">Long-poll timeout in seconds (0 = short poll)</td></tr>
            <tr><td class="field-name">.limit(100)</td><td class="field-type">100</td><td class="field-doc">Max updates per getUpdates call (1–100)</td></tr>
            <tr><td class="field-name">.allowed_updates(vec![...])</td><td class="field-type">all</td><td class="field-doc">Filter update types: message, callback_query, inline_query, etc.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="section" id="webhook">
    <h2 class="section-h2">🪝 Webhook Server</h2>
    <p class="section-sub">Production-ready built-in webhook server powered by Axum.</p>
    <div style="max-width:780px;display:flex;flex-direction:column;gap:16px">
      <div class="example-header" style="margin-bottom:8px"><span style="font-size:13px;font-weight:700;color:var(--text-dim)">Full webhook setup</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
      <pre class="code-block"><code class="language-rust">use tgbotrs::{{Bot, UpdateHandler, WebhookServer}};

#[tokio::main]
async fn main() {{
    let bot = Bot::new("YOUR_BOT_TOKEN").await.unwrap();

    let handler: UpdateHandler = Box::new(|bot, update| {{
        Box::pin(async move {{
            if let Some(msg) = update.message {{
                let _ = bot.send_message(msg.chat.id, "pong! 🏓", None).await;
            }}
        }})
    }});

    WebhookServer::new(bot, handler)
        .port(8080)
        .path("/webhook")
        .secret_token("my_secret_token")
        .max_connections(40)
        .drop_pending_updates()
        .allowed_updates(vec!["message".into(), "callback_query".into()])
        .start("https://yourdomain.com")
        .await.unwrap();
}}</code></pre>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);padding:20px">
        <div style="font-size:13px;font-weight:700;color:var(--text-dim);margin-bottom:12px">WebhookServer Configuration</div>
        <table class="fields-table">
          <thead><tr><th>Method</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td class="field-name">.port(8080)</td><td class="field-type">8080</td><td class="field-doc">Local bind port (Telegram supports 80, 88, 443, 8443)</td></tr>
            <tr><td class="field-name">.path("/webhook")</td><td class="field-type">/webhook</td><td class="field-doc">URL path Telegram POSTs to</td></tr>
            <tr><td class="field-name">.secret_token("...")</td><td class="field-type">None</td><td class="field-doc">Validates X-Telegram-Bot-Api-Secret-Token header</td></tr>
            <tr><td class="field-name">.max_connections(40)</td><td class="field-type">40</td><td class="field-doc">Max simultaneous connections from Telegram (1–100)</td></tr>
            <tr><td class="field-name">.drop_pending_updates()</td><td class="field-type">false</td><td class="field-doc">Clear update queue when registering webhook</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="methods">
    <div class="filter-bar">
      <span class="filter-label">Filter:</span>
      <button class="filter-chip active" onclick="filterCat('all',this)">All ({S["methods"]})</button>
      <button class="filter-chip" onclick="filterCat('Sending Messages',this)">📤 Send</button>
      <button class="filter-chip" onclick="filterCat('Getting Info',this)">ℹ️ Get</button>
      <button class="filter-chip" onclick="filterCat('Editing',this)">✏️ Edit</button>
      <button class="filter-chip" onclick="filterCat('Chat Administration',this)">🛡️ Admin</button>
      <button class="filter-chip" onclick="filterCat('Stickers',this)">😸 Stickers</button>
      <button class="filter-chip" onclick="filterCat('Payments & Stars',this)">💰 Payments</button>
      <button class="filter-chip" onclick="filterCat('Updates & Webhook',this)">🔄 Updates</button>
      <button class="filter-chip" onclick="filterCat('Business',this)">🏢 Business</button>
      <span class="results-count" id="resultsCount">{S["methods"]} methods</span>
    </div>
    <div id="methodsContainer">
{method_cards}
    </div>
  </section>

  <section class="section" id="types">
    <h2 class="section-h2">📐 Types Reference</h2>
    <p class="section-sub">All {S["types"]} Telegram types. Below shows commonly used types with their fields. See <a href="https://docs.rs/tgbotrs" target="_blank" style="color:var(--accent2)">docs.rs</a> for the complete list.</p>
    <div class="tabs">
      <button class="tab active" onclick="showTab('structs',this)">Structs ({S["types"]})</button>
      <button class="tab" onclick="showTab('enums',this)">Enums ({S["enums"]})</button>
      <button class="tab" onclick="showTab('special',this)">Special Types</button>
    </div>
    <div id="tab-structs" class="tab-panel active">
      <div class="types-grid">{types_html}</div>
    </div>
    <div id="tab-enums" class="tab-panel">
      <div class="enums-grid">{enums_html}</div>
    </div>
    <div id="tab-special" class="tab-panel">
      <div style="display:flex;flex-direction:column;gap:16px;max-width:780px">
        <div class="error-section">
          <div style="font-size:16px;font-weight:700;margin-bottom:12px;font-family:'JetBrains Mono',monospace;color:var(--purple)">ChatId</div>
          <p style="font-size:13px;color:var(--text-dim);margin-bottom:12px">Accepts numeric IDs or username strings transparently.</p>
          <pre class="code-block"><code class="language-rust">// All these work everywhere ChatId is accepted:
bot.send_message(123456789i64, "text", None).await?;
bot.send_message("@mychannel", "text", None).await?;
bot.send_message(ChatId::Id(123456789), "text", None).await?;</code></pre>
        </div>
        <div class="error-section">
          <div style="font-size:16px;font-weight:700;margin-bottom:12px;font-family:'JetBrains Mono',monospace;color:var(--purple)">InputFile</div>
          <p style="font-size:13px;color:var(--text-dim);margin-bottom:12px">Flexible file input — path, URL, or raw bytes.</p>
          <pre class="code-block"><code class="language-rust">use tgbotrs::InputFile;

let by_path  = InputFile::path("photo.jpg");
let by_url   = InputFile::url("https://example.com/photo.jpg");
let bytes    = std::fs::read("photo.jpg").unwrap();
let by_bytes = InputFile::bytes("photo.jpg", bytes);</code></pre>
        </div>
        <div class="error-section">
          <div style="font-size:16px;font-weight:700;margin-bottom:12px;font-family:'JetBrains Mono',monospace;color:var(--purple)">ReplyMarkup</div>
          <p style="font-size:13px;color:var(--text-dim);margin-bottom:12px">All four keyboard types unified in one enum.</p>
          <pre class="code-block"><code class="language-rust">use tgbotrs::ReplyMarkup;
use tgbotrs::types::{{InlineKeyboardMarkup, InlineKeyboardButton}};

let markup = ReplyMarkup::InlineKeyboard(InlineKeyboardMarkup {{
    inline_keyboard: vec![vec![
        InlineKeyboardButton {{
            text: "🔵 Click".into(),
            callback_data: Some("cb1".into()),
            style: Some("primary".into()), // Bot API 9.4
            ..Default::default()
        }}
    ]]
}});</code></pre>
        </div>
        <div class="error-section">
          <div style="font-size:16px;font-weight:700;margin-bottom:12px;font-family:'JetBrains Mono',monospace;color:var(--purple)">InputMedia</div>
          <p style="font-size:13px;color:var(--text-dim);margin-bottom:12px">Media group for send_media_group.</p>
          <pre class="code-block"><code class="language-rust">use tgbotrs::{{InputMedia, types::InputMediaPhoto}};
use tgbotrs::InputFileOrString;

let media = vec![
    InputMedia::Photo(InputMediaPhoto {{
        r#type: "photo".into(),
        media: InputFileOrString::String("file_id".into()),
        caption: Some("Caption 1".into()),
        ..Default::default()
    }}),
];</code></pre>
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="errors">
    <h2 class="section-h2">⚠️ Error Handling</h2>
    <p class="section-sub">All API calls return <code style="background:var(--bg3);padding:1px 6px;border-radius:4px">Result&lt;T, BotError&gt;</code> — handle specific errors with pattern matching.</p>
    <div style="max-width:780px;display:flex;flex-direction:column;gap:16px">
      <div class="error-section">
        <div style="font-size:15px;font-weight:700;margin-bottom:16px;font-family:'JetBrains Mono',monospace">BotError variants</div>
        <div class="error-variant">
          <div class="error-variant-name">BotError::Api {{ code, description, retry_after, migrate_to_chat_id }}</div>
          <div class="error-variant-desc">Telegram returned ok=false. Code 429 = flood wait, 403 = blocked, 400 = bad request.</div>
        </div>
        <div class="error-variant">
          <div class="error-variant-name">BotError::Http(reqwest::Error)</div>
          <div class="error-variant-desc">Network error — connection refused, timeout, DNS failure.</div>
        </div>
        <div class="error-variant">
          <div class="error-variant-name">BotError::Json(serde_json::Error)</div>
          <div class="error-variant-desc">Failed to (de)serialize request or response.</div>
        </div>
        <div class="error-variant">
          <div class="error-variant-name">BotError::InvalidToken</div>
          <div class="error-variant-desc">Token doesn't contain a colon — invalid format.</div>
        </div>
      </div>
      <div class="example-header" style="margin-bottom:8px"><span style="font-size:13px;font-weight:700;color:var(--text-dim)">Error handling patterns</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
      <pre class="code-block"><code class="language-rust">use tgbotrs::{{Bot, BotError}};

async fn send_safe(bot: &Bot, chat_id: i64, text: &str) {{
    match bot.send_message(chat_id, text, None).await {{
        Ok(msg) => println!("Sent #{{}}", msg.message_id),
        Err(BotError::Api {{ code: 403, .. }}) => {{
            println!("Bot was blocked by this user");
        }}
        Err(BotError::Api {{ code: 429, retry_after: Some(secs), .. }}) => {{
            println!("Flood wait: retry after {{}} seconds", secs);
            tokio::time::sleep(std::time::Duration::from_secs(secs as u64)).await;
        }}
        Err(BotError::Api {{ code, description, .. }}) => {{
            eprintln!("API [{{}}]: {{}}", code, description);
        }}
        Err(e) => eprintln!("Error: {{}}", e),
    }}
}}

// Built-in helpers:
let is_blocked = error.is_api_error_code(403);
let wait_secs  = error.flood_wait_seconds(); // Option&lt;i64&gt;</code></pre>
    </div>
  </section>

</main>
</div>

<footer class="footer">
  <div style="display:flex;align-items:center;gap:10px">
    <div class="logo-icon" style="width:32px;height:32px;font-size:16px">🦀</div>
    <div>
      <div style="font-size:14px;font-weight:700">tgbotrs v0.1.4</div>
      <div style="font-size:12px;color:var(--text-muted)">Developed by <a href="https://github.com/ankit-chaubey" target="_blank" style="color:var(--accent)">Ankit Chaubey</a></div>
    </div>
  </div>
  <div style="font-size:13px;color:var(--text-muted)">Telegram Bot API 9.4 · {S["methods"]} methods · {S["types"]} types · MIT License</div>
  <div class="footer-links">
    <a href="https://github.com/ankit-chaubey/tgbotrs" target="_blank">GitHub</a>
    <a href="https://crates.io/crates/tgbotrs" target="_blank">crates.io</a>
    <a href="https://docs.rs/tgbotrs" target="_blank">docs.rs</a>
    <a href="https://t.me/ankify" target="_blank">Telegram</a>
    <a href="mailto:ankitchaubey.dev@gmail.com">Email</a>
  </div>
</footer>

<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
  document.addEventListener('keydown', e => {{
    if ((e.ctrlKey||e.metaKey) && e.key==='k') {{e.preventDefault(); document.getElementById('globalSearch').focus();}}
  }});
}});

function copyCode(btn) {{
  const wrapper = btn.closest('.example-header');
  const pre = wrapper ? wrapper.nextElementSibling : btn.closest('[style]').querySelector('pre');
  const code = pre ? pre.innerText : '';
  navigator.clipboard.writeText(code.trim()).then(() => {{
    const orig = btn.textContent;
    btn.textContent = '✅ Copied!'; btn.classList.add('copied');
    setTimeout(() => {{ btn.textContent = orig; btn.classList.remove('copied'); }}, 2000);
  }});
}}

function toggleCat(btn) {{
  const id = btn.dataset.catId;
  const panel = document.getElementById('sidebar-' + id);
  if (!panel) return;
  const open = panel.classList.contains('collapsed');
  panel.classList.toggle('collapsed', !open);
  btn.classList.toggle('open', open);
}}

function showTab(id, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}}

function filterCat(cat, btn) {{
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  let visible = 0;
  document.querySelectorAll('.method-card').forEach(card => {{
    const show = cat === 'all' || card.dataset.cat === cat;
    card.classList.toggle('hidden', !show);
    if (show) visible++;
  }});
  document.getElementById('resultsCount').textContent = visible + ' methods';
  document.querySelectorAll('.cat-section').forEach(s => {{
    s.style.display = s.querySelectorAll('.method-card:not(.hidden)').length > 0 ? '' : 'none';
  }});
}}

let searchT;
document.getElementById('globalSearch').addEventListener('input', function() {{
  clearTimeout(searchT);
  searchT = setTimeout(() => {{
    const q = this.value.toLowerCase().trim();
    document.querySelectorAll('.filter-chip').forEach((c,i) => c.classList.toggle('active', i===0));
    let visible = 0;
    document.querySelectorAll('.method-card').forEach(card => {{
      const match = !q || card.dataset.name.includes(q) || card.textContent.toLowerCase().includes(q);
      card.classList.toggle('hidden', !match);
      if (match) visible++;
    }});
    document.getElementById('resultsCount').textContent = visible + ' methods';
    document.querySelectorAll('.cat-section').forEach(s => {{
      s.style.display = s.querySelectorAll('.method-card:not(.hidden)').length > 0 ? '' : 'none';
    }});
  }}, 150);
}});

// Sidebar active method highlight
const obs = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      const id = e.target.id;
      document.querySelectorAll('.sidebar-method').forEach(a => {{
        a.style.color = a.getAttribute('href') === '#'+id ? 'var(--accent)' : '';
      }});
    }}
  }});
}}, {{ rootMargin: '-10% 0px -70% 0px' }});
document.querySelectorAll('.method-card').forEach(c => obs.observe(c));
</script>
</body>
</html>'''


print("🏗️  Assembling final page...")
html = assemble(method_cards, sidebar_html, types_html, enums_html, stats)

output_path = SITE_DIR / "index.html"
output_path.write_text(html, encoding="utf-8")

size_kb = len(html.encode()) / 1024
print(f"\n✅ Generated: {output_path}")
print(f"   Size: {size_kb:.1f} KB")
print(f"   Methods: {stats['methods']}")
print(f"   Types: {stats['types']}")
print(f"   Enums: {stats['enums']}")
print(f"\n🎉 Documentation generation complete!")