#!/usr/bin/env python3
"""
tgbotrs Documentation Generator  ·  v2 (improved)
===================================================
Parses tgbotrs Rust source files and generates a complete,
interactive, mobile-first documentation website.

  • Liquid-glass premium design
  • ALL fields shown — no truncation
  • Mobile-first: hamburger sidebar, bottom nav, theme toggle
  • Custom domain: auto-generates CNAME
  • Lowest supported version: 0.1.4

Developed by Ankit Chaubey <ankitchaubey.dev@gmail.com>
GitHub: https://github.com/ankit-chaubey/tgbotrs

Usage:
    python3 scripts/generate_docs.py

Output:
    site/index.html  — full self-contained docs site
    site/CNAME       — custom domain file for GitHub Pages
"""

import re
import json
import os
from pathlib import Path

CRATE_VERSION  = "0.1.4"
CUSTOM_DOMAIN  = "tgbotrs.ankitchaubey.in"

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR   = SCRIPT_DIR.parent
SRC_DIR    = ROOT_DIR / "tgbotrs" / "src"
SITE_DIR   = ROOT_DIR / "site"
SITE_DIR.mkdir(exist_ok=True)

print("📂 Source dir:", SRC_DIR)
print("📂 Site dir:",   SITE_DIR)

def load(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"⚠️  File not found: {path}")
        return ""

gen_methods = load(SRC_DIR / "gen_methods.rs")
gen_types   = load(SRC_DIR / "gen_types.rs")
hand_types  = load(SRC_DIR / "types.rs")
print("✅ Source files loaded")

# ── Parse Methods ───────────────────────────────────────────────────────────────
def parse_methods(content):
    all_blocks = re.split(r'\nimpl Bot \{', content)
    methods = []
    for block in all_blocks:
        m = re.search(
            r'/// (.*?)\n\s+/// See: (https://[^\n]+)\n\s+pub async fn (\w+)\(\s*&self,?(.*?)\)\s*->\s*Result<([^,\n{]+)',
            block, re.DOTALL)
        if not m: continue
        doc, url, name, raw_p, ret = m.group(1).strip(), m.group(2).strip(), m.group(3), m.group(4), m.group(5).strip()
        params_clean = re.sub(r'\s+', ' ', raw_p.strip()).rstrip(',')
        param_list   = _parse_param_list(params_clean)
        methods.append({'name':name,'doc':doc,'url':url,'params':params_clean,'param_list':param_list,'ret':ret})
    return methods

def _parse_param_list(raw):
    params=[]; depth,cur=0,''
    for ch in raw:
        if ch in '<([': depth+=1
        elif ch in '>)]': depth-=1
        if ch==',' and depth==0: _add_param(params,cur); cur=''
        else: cur+=ch
    _add_param(params,cur)
    return params

def _add_param(lst,raw):
    raw=raw.strip()
    if not raw: return
    parts=raw.split(':',1)
    if len(parts)==2: lst.append({'name':parts[0].strip(),'type':parts[1].strip()})

# ── Parse Optional Param Structs ────────────────────────────────────────────────
def parse_param_structs(content):
    pattern = re.compile(
        r'/// Optional parameters for \[`Bot::(\w+)`\]\n#\[derive[^\]]+\]\npub struct (\w+) \{(.*?)\}\n',
        re.DOTALL)
    result={}
    for method,struct_name,fields_raw in pattern.findall(content):
        fields=re.findall(r'/// ([^\n]+)\n\s+(?:#\[serde[^\]]+\]\n\s+)?pub (\w+): ([^,\n]+)',fields_raw)
        result[method]={'struct':struct_name,'fields':[{'doc':d.strip(),'name':n.strip(),'type':t.strip().rstrip(',')} for d,n,t in fields]}
    return result

# ── Parse Types ─────────────────────────────────────────────────────────────────
def parse_structs(content):
    structs=[]
    for name,body in re.findall(r'pub struct (\w+) \{([^}]+)\}',content):
        fields=re.findall(r'pub (\w+): ([^,\n]+)',body)
        structs.append({'name':name,'fields':[{'name':n,'type':t.strip().rstrip(',')} for n,t in fields]})
    return structs

def parse_enums(content):
    enums=[]
    for name,body in re.findall(r'pub enum (\w+) \{([^}]+)\}',content):
        variants=re.findall(r'\n\s+(\w+)',body)
        enums.append({'name':name,'variants':variants})
    return enums

# ── Code Example Generator ──────────────────────────────────────────────────────
def type_placeholder(t,name=''):
    t=t.strip()
    if t.startswith('Option<'): return 'None'
    if t in ('i64','i32','u64','u32'):
        if any(k in name.lower() for k in ('chat','user','group')): return '123456789i64'
        return '0i64'
    if t=='bool': return 'true'
    if t in ('f64','f32'): return '0.0'
    if 'Into<String>' in t or t in ('String','&str'):
        if 'token' in name.lower(): return '"YOUR_BOT_TOKEN"'
        if any(k in name.lower() for k in ('text','message','caption')): return '"Hello from tgbotrs! 🦀"'
        if 'url' in name.lower(): return '"https://example.com"'
        if 'chat_id' in name.lower(): return '"@yourchannel"'
        if 'name' in name.lower(): return '"my_name"'
        return '"example"'
    if 'Into<ChatId>' in t: return '123456789i64'
    if t.startswith('Vec<'): return f'vec![]  // Vec<{t[4:-1]}>'
    if t[0:1].isupper(): return f'{t}::default()'
    return 'todo!()'

def generate_example(method,params_map):
    name=method['name']; param_list=method['param_list']; has_opt=name in params_map
    imports=['use tgbotrs::{Bot, BotError};']
    if has_opt:
        s=params_map[name]['struct']
        imports.append(f'use tgbotrs::gen_methods::{{{s}}};')
    lines=imports+['','#[tokio::main]','async fn main() -> Result<(), BotError> {',
                   '    let bot = Bot::new("YOUR_BOT_TOKEN").await?;','']
    call_args=[]
    for p in param_list:
        pname,ptype=p['name'],p['type']
        if pname=='params' and has_opt:
            pstruct=params_map[name]['struct']; fields=params_map[name].get('fields',[])
            if fields:
                chain=[f'    let params = {pstruct}::new()']
                for f in fields[:5]:
                    val=type_placeholder(f['type'],f['name'])
                    chain.append(f'        .{f["name"]}({val})')
                if len(fields)>5: chain.append(f'        // ... +{len(fields)-5} more optional fields')
                chain[-1]+=';'
                lines.append('    // Optional parameters'); lines.extend(chain)
            else: lines.append(f'    let params = {pstruct}::new();')
            lines.append(''); call_args.append('Some(params)')
        else:
            val=type_placeholder(ptype,pname)
            lines.append(f'    let {pname} = {val};'); call_args.append(pname)
    lines.append('')
    args_str=',\n        '.join(call_args)
    if call_args: lines.append(f'    let result = bot.{name}(\n        {args_str}\n    ).await?;')
    else: lines.append(f'    let result = bot.{name}().await?;')
    lines+=['    println!("Result: {result:?}");','    Ok(())','}']; return '\n'.join(lines)

# ── Category Logic ──────────────────────────────────────────────────────────────
CATEGORY_ORDER=['Sending Messages','Getting Info','Editing','Deletion','Forwarding & Copying',
    'Answering Queries','Chat Administration','Invite & Membership','Pinning','Configuration',
    'Updates & Webhook','Stickers','Forum Topics','Games','Payments & Stars','Stories','Business','Other']

def categorize(name):
    n=name.lower()
    if n.startswith('send_'): return 'Sending Messages'
    if n.startswith('get_'): return 'Getting Info'
    if n.startswith('set_'): return 'Configuration'
    if n.startswith('edit_'): return 'Editing'
    if n.startswith('delete_'): return 'Deletion'
    if n.startswith(('forward_','copy_')): return 'Forwarding & Copying'
    if n.startswith('answer_'): return 'Answering Queries'
    if n.startswith(('ban_','unban_','restrict_','promote_')): return 'Chat Administration'
    if n.startswith(('create_','approve_','decline_','revoke_')): return 'Invite & Membership'
    if n.startswith(('pin_','unpin_')): return 'Pinning'
    if 'sticker' in n or 'emoji' in n: return 'Stickers'
    if 'forum' in n: return 'Forum Topics'
    if n in ('close','get_updates') or 'webhook' in n: return 'Updates & Webhook'
    if 'game' in n: return 'Games'
    if any(k in n for k in ('invoice','payment','shipping','star','gift','premium')): return 'Payments & Stars'
    if 'story' in n: return 'Stories'
    if 'business' in n: return 'Business'
    return 'Other'

def h(s):
    return (str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;'))
def slug(name): return name.replace('_','-')

def cat_icon(cat):
    return {'Sending Messages':'📤','Getting Info':'ℹ️','Editing':'✏️','Deletion':'🗑️',
        'Forwarding & Copying':'📋','Answering Queries':'💬','Chat Administration':'🛡️',
        'Invite & Membership':'🤝','Pinning':'📌','Configuration':'⚙️','Updates & Webhook':'🔄',
        'Stickers':'😸','Forum Topics':'🗂️','Games':'🎮','Payments & Stars':'💰',
        'Stories':'📖','Business':'🏢','Other':'🔧'}.get(cat,'📌')

# ── Build Method Cards ─────────────────────────────────────────────────────────
def build_method_cards(categories,params_map,examples):
    html=''
    for cat in CATEGORY_ORDER:
        if cat not in categories: continue
        cat_id=cat.lower().replace(' ','-').replace('&','and')
        methods=categories[cat]
        html+=f'\n    <section class="cat-section" id="cat-{cat_id}">\n      <div class="cat-header"><h2 class="cat-title">{h(cat)}</h2><span class="cat-count">{len(methods)}</span></div>\n      <div class="methods-grid">\n'
        for m in methods:
            name=m['name']; s=slug(name); doc=h(m['doc']); ret=h(m['ret']); has_opt=name in params_map
            param_pills=''.join(
                f'<span class="param-pill {"optional" if "Option<" in p["type"] or p["name"]=="params" else "required"}" title="{h(p["type"])}">{h(p["name"])}</span>'
                for p in m['param_list']
            ) or '<span class="no-params">no parameters</span>'
            opt_html=''
            if has_opt:
                fields=params_map[name].get('fields',[]); struct_name=params_map[name]['struct']
                # ALL FIELDS — no truncation
                rows=''.join(
                    f'<tr><td class="field-name">{h(f["name"])}</td><td class="field-type">{h(f["type"])}</td><td class="field-doc">{h(f.get("doc",""))}</td></tr>'
                    for f in fields
                )
                opt_html=f'''
            <div class="optional-section">
              <div class="section-label">Optional params — <code>{h(struct_name)}</code><span class="field-count">{len(fields)} fields</span></div>
              <div class="table-wrap"><table class="fields-table"><thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead><tbody>{rows}</tbody></table></div>
            </div>'''
            code=h(examples.get(name,'// example not available'))
            html+=f'''
        <div class="method-card" id="method-{s}" data-name="{name}" data-cat="{h(cat)}">
          <div class="method-header" onclick="toggleCard(this)">
            <div class="method-name-row">
              <span class="method-name">bot.{name}()</span>
              <div class="method-badges">
                <span class="badge badge-async">async</span>
                <span class="badge badge-ret">→ {ret}</span>
                {'<span class="badge badge-opt">+opts</span>' if has_opt else ''}
              </div>
              <span class="card-toggle-arrow">▾</span>
            </div>
            <p class="method-doc">{doc}</p>
          </div>
          <div class="method-body collapsed-body">
            <div class="params-section"><div class="section-label">Parameters</div><div class="param-pills">{param_pills}</div></div>
            {opt_html}
            <div class="example-section">
              <div class="example-header">
                <div class="section-label">Example</div>
                <div class="example-actions">
                  <a href="#method-{s}" class="anchor-btn" title="Link">🔗</a>
                  <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
                </div>
              </div>
              <pre class="code-block"><code class="language-rust">{code}</code></pre>
            </div>
            <div class="method-footer"><a href="{h(m["url"])}" target="_blank" class="tg-link">📖 Telegram Docs ↗</a></div>
          </div>
        </div>
'''
        html+='      </div>\n    </section>\n'
    return html

def build_sidebar(categories):
    html=''
    for cat in CATEGORY_ORDER:
        if cat not in categories: continue
        cat_id=cat.lower().replace(' ','-').replace('&','and'); methods=categories[cat]
        html+=f'''
      <div class="sidebar-cat">
        <button class="cat-toggle" onclick="toggleCat(this)" data-cat-id="{cat_id}">
          <span class="cat-icon">{cat_icon(cat)}</span>
          <span class="cat-name">{h(cat)}</span>
          <span class="cat-cnt">{len(methods)}</span>
          <span class="cat-arrow">▾</span>
        </button>
        <div class="cat-methods collapsed" id="sidebar-{cat_id}">
'''
        for m in methods:
            s=slug(m['name'])
            html+=f'          <a href="#method-{s}" class="sidebar-method" onclick="closeSidebar()">{h(m["name"])}</a>\n'
        html+='        </div>\n      </div>\n'
    return html

def build_types_html(types_list):
    html=''
    for t in types_list:
        name=h(t['name'])
        # ALL fields
        fields_html=''.join(
            f'<div class="type-field"><span class="type-field-name">{h(f["name"])}</span><span class="type-field-type">{h(f["type"])}</span></div>'
            for f in t['fields']
        ) or '<div class="type-empty">no public fields</div>'
        count=len(t['fields'])
        html+=f'\n    <div class="type-card" id="type-{name.lower()}"><div class="type-name">{name} <span class="type-field-count">{count}</span></div><div class="type-fields">{fields_html}</div></div>\n'
    return html

def build_enums_html(enums_list):
    html=''
    for e in enums_list:
        name=h(e['name'])
        variants=' '.join(f'<span class="enum-variant">{h(v)}</span>' for v in e['variants'])
        html+=f'\n    <div class="enum-card" id="enum-{name.lower()}"><div class="enum-name">{name}</div><div class="enum-variants">{variants}</div></div>\n'
    return html

# ── Main ────────────────────────────────────────────────────────────────────────
print("\n🔍 Parsing methods...")
methods=parse_methods(gen_methods)
print(f"   Found {len(methods)} methods")

print("🔍 Parsing param structs...")
params_map=parse_param_structs(gen_methods)
print(f"   Found {len(params_map)} optional param structs")

print("🔍 Parsing types...")
types_structs=parse_structs(gen_types); types_enums=parse_enums(gen_types)
hand_structs=parse_structs(hand_types); hand_enums=parse_enums(hand_types)
all_structs=types_structs+hand_structs; all_enums=types_enums+hand_enums
print(f"   Found {len(all_structs)} structs, {len(all_enums)} enums")

print("🔧 Generating code examples...")
examples={m['name']:generate_example(m,params_map) for m in methods}
print(f"   Generated {len(examples)} examples")

print("📂 Categorizing methods...")
categories={}
for m in methods:
    cat=categorize(m['name']); categories.setdefault(cat,[]).append(m)
for cat,ms in sorted(categories.items(),key=lambda x:len(x[1]),reverse=True):
    print(f"   {cat}: {len(ms)}")

print("\n🏗️  Building HTML fragments...")
method_cards=build_method_cards(categories,params_map,examples)
sidebar_html=build_sidebar(categories)
types_html=build_types_html(all_structs)
enums_html=build_enums_html(all_enums)
stats={'methods':len(methods),'types':len(all_structs),'enums':len(all_enums),'param_structs':len(params_map)}

# search index
_cat_colors={'Sending Messages':'#818cf8','Getting Info':'#38bdf8','Configuration':'#34d399',
    'Editing':'#fbbf24','Deletion':'#f87171','Forwarding & Copying':'#a78bfa',
    'Answering Queries':'#2dd4bf','Chat Administration':'#fb923c','Invite & Membership':'#c084fc',
    'Pinning':'#f472b6','Stickers':'#a3e635','Forum Topics':'#67e8f9','Updates & Webhook':'#818cf8',
    'Games':'#4ade80','Payments & Stars':'#fcd34d','Stories':'#fb7185','Business':'#94a3b8','Other':'#6b7280'}
_search_idx=[{'n':m['name'],'d':m['doc'][:100],'c':categorize(m['name']),'col':_cat_colors.get(categorize(m['name']),'#7c6af7')} for m in methods]
_search_json=json.dumps(_search_idx,separators=(',',':'))

S=stats

# ── Assemble ────────────────────────────────────────────────────────────────────
HTML = f'''<!DOCTYPE html>
<html lang="en" data-theme="amoled">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
  <title>tgbotrs v{CRATE_VERSION} — Telegram Bot API for Rust</title>
  <meta name="description" content="Complete docs for tgbotrs — {S["methods"]} methods, {S["types"]} types, fully async. By Ankit Chaubey.">
  <meta property="og:url" content="https://{CUSTOM_DOMAIN}">
  <link rel="canonical" href="https://{CUSTOM_DOMAIN}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
<style>
/* THEMES */
[data-theme="amoled"]{{--bg:#000;--bg2:#0a0a0a;--bg3:#111;--bg4:#1a1a1a;--border:rgba(255,255,255,.07);--border-bright:rgba(255,255,255,.14);--accent:#8b78ff;--accent-h:#a090ff;--accent2:#38bdf8;--accent3:#4ade80;--accent4:#f87171;--text:#f0f0f0;--text-dim:#aaa;--text-muted:#555;--rust:#fb923c;--yellow:#fbbf24;--green:#4ade80;--red:#f87171;--blue:#60a5fa;--purple:#c084fc;--glass:rgba(255,255,255,.04);--glass-b:rgba(255,255,255,.09);--glass-h:rgba(255,255,255,.07);--hdr:rgba(0,0,0,.88);--code-bg:#0d0d0d;--sb-bg:rgba(6,6,6,.98);--ga:rgba(139,120,255,.14);--gb:rgba(56,189,248,.09);}}
[data-theme="dark"]{{--bg:#0d0f17;--bg2:#131622;--bg3:#1a1d2e;--bg4:#21253a;--border:rgba(255,255,255,.08);--border-bright:rgba(255,255,255,.15);--accent:#7c6af7;--accent-h:#9585ff;--accent2:#38bdf8;--accent3:#34d399;--accent4:#f87171;--text:#e2e8f0;--text-dim:#94a3b8;--text-muted:#64748b;--rust:#f97316;--yellow:#fbbf24;--green:#4ade80;--red:#f87171;--blue:#60a5fa;--purple:#c084fc;--glass:rgba(255,255,255,.05);--glass-b:rgba(255,255,255,.1);--glass-h:rgba(255,255,255,.08);--hdr:rgba(13,15,23,.9);--code-bg:#1a1d2e;--sb-bg:rgba(10,12,20,.98);--ga:rgba(124,106,247,.18);--gb:rgba(56,189,248,.12);}}
[data-theme="light"]{{--bg:#f0f2fc;--bg2:#fff;--bg3:#edf0fb;--bg4:#e3e6f5;--border:rgba(0,0,0,.07);--border-bright:rgba(0,0,0,.13);--accent:#5b4fe8;--accent-h:#7466ef;--accent2:#0284c7;--accent3:#16a34a;--accent4:#dc2626;--text:#0e1117;--text-dim:#4a5568;--text-muted:#9ca3af;--rust:#ea580c;--yellow:#d97706;--green:#16a34a;--red:#dc2626;--blue:#2563eb;--purple:#7c3aed;--glass:rgba(255,255,255,.65);--glass-b:rgba(0,0,0,.08);--glass-h:rgba(255,255,255,.85);--hdr:rgba(240,242,252,.92);--code-bg:#1e1e2e;--sb-bg:rgba(255,255,255,.98);--ga:rgba(91,79,232,.11);--gb:rgba(2,132,199,.07);}}

/* RESET */
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6;-webkit-tap-highlight-color:transparent;transition:background .25s,color .25s}}
a{{color:inherit;text-decoration:none}}
button{{cursor:pointer;border:none;background:none;font-family:inherit;color:inherit}}
::-webkit-scrollbar{{width:5px;height:5px}}::-webkit-scrollbar-track{{background:var(--bg2)}}::-webkit-scrollbar-thumb{{background:var(--border-bright);border-radius:3px}}

/* LAYOUT */
:root{{--hdr-h:64px;--sb-w:272px;--r:14px;--rs:9px;--mob-h:60px}}
@media(max-width:768px){{:root{{--hdr-h:56px;--sb-w:288px}}}}

/* GLASS */
.glass{{background:var(--glass);backdrop-filter:blur(20px) saturate(1.5);-webkit-backdrop-filter:blur(20px) saturate(1.5);border:1px solid var(--glass-b)}}

/* HEADER */
.hdr{{position:fixed;top:0;left:0;right:0;z-index:200;height:var(--hdr-h);background:var(--hdr);backdrop-filter:blur(24px) saturate(1.8);-webkit-backdrop-filter:blur(24px) saturate(1.8);border-bottom:1px solid var(--glass-b);display:flex;align-items:center;padding:0 16px 0 20px;gap:12px}}
.logo{{display:flex;align-items:center;gap:9px;flex-shrink:0}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),#e879f9);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff;box-shadow:0 2px 14px rgba(139,120,255,.4);flex-shrink:0}}
.logo-text{{font-size:17px;font-weight:800}}
.logo-ver{{font-size:10px;color:var(--accent);background:rgba(139,120,255,.14);padding:2px 7px;border-radius:100px;font-weight:700;border:1px solid rgba(139,120,255,.25)}}
.hdr-search{{flex:1;max-width:420px;position:relative}}
.hdr-search input{{width:100%;padding:8px 36px 8px 36px;background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-radius:10px;color:var(--text);font-size:14px;font-family:inherit;outline:none;transition:border-color .2s,box-shadow .2s}}
.hdr-search input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(139,120,255,.15)}}
.hdr-search input::placeholder{{color:var(--text-muted)}}
.s-ico{{position:absolute;left:11px;top:50%;transform:translateY(-50%);font-size:13px;color:var(--text-muted);pointer-events:none}}
.s-kbd{{position:absolute;right:10px;top:50%;transform:translateY(-50%);font-size:9.5px;color:var(--text-muted);background:var(--bg4);border:1px solid var(--border-bright);padding:1px 5px;border-radius:4px;font-family:'JetBrains Mono',monospace;pointer-events:none}}
@media(max-width:480px){{.s-kbd{{display:none}}}}
.hdr-nav{{display:flex;align-items:center;gap:6px;margin-left:auto;flex-shrink:0}}
.hdr-nav a{{padding:6px 10px;border-radius:var(--rs);color:var(--text-dim);font-size:13px;font-weight:500;transition:all .15s;white-space:nowrap}}
.hdr-nav a:hover{{color:var(--text);background:var(--glass)}}
.btn-gh{{background:var(--accent)!important;color:#fff!important;padding:7px 13px!important;border-radius:var(--rs)!important;font-weight:600!important}}
.btn-gh:hover{{background:var(--accent-h)!important}}
@media(max-width:640px){{.nav-hide{{display:none}}}}
.theme-sw{{display:flex;gap:1px;background:var(--glass);border:1px solid var(--glass-b);border-radius:9px;padding:2px;flex-shrink:0}}
.th-btn{{padding:5px 8px;border-radius:7px;font-size:14px;transition:all .15s;line-height:1;color:var(--text-muted)}}
.th-btn:hover{{color:var(--text)}}
.th-btn.on{{background:var(--accent);color:#fff;box-shadow:0 1px 8px rgba(139,120,255,.4)}}
@media(max-width:480px){{.theme-sw{{display:none}}}}
.mob-menu-btn{{display:none;padding:8px;border-radius:9px;background:var(--glass);border:1px solid var(--glass-b);font-size:18px;flex-shrink:0;align-items:center;justify-content:center}}
@media(max-width:900px){{.mob-menu-btn{{display:flex}}}}

/* SIDEBAR */
.sidebar{{position:fixed;top:var(--hdr-h);bottom:0;left:0;width:var(--sb-w);overflow-y:auto;background:var(--sb-bg);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-right:1px solid var(--glass-b);padding:10px 0 env(safe-area-inset-bottom,0);z-index:150;transition:transform .28s cubic-bezier(.4,0,.2,1)}}
@media(max-width:900px){{.sidebar{{top:0;bottom:0;padding-top:calc(var(--hdr-h) + 8px);padding-bottom:env(safe-area-inset-bottom,16px);transform:translateX(-100%);box-shadow:4px 0 40px rgba(0,0,0,.5)}}.sidebar.open{{transform:translateX(0)}}}}
.sb-overlay{{display:none;position:fixed;inset:0;z-index:140;background:rgba(0,0,0,.6);backdrop-filter:blur(2px)}}
.sb-overlay.open{{display:block}}
.sb-search{{padding:8px 12px 4px}}
.sb-search input{{width:100%;padding:7px 12px;background:var(--glass);border:1px solid var(--glass-b);border-radius:8px;color:var(--text);font-size:13px;font-family:inherit;outline:none;transition:border-color .2s}}
.sb-search input:focus{{border-color:var(--accent)}}
.sb-search input::placeholder{{color:var(--text-muted)}}
.sb-ttl{{font-size:9.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--text-muted);padding:10px 16px 4px}}
.sb-link{{display:flex;align-items:center;gap:7px;padding:7px 16px;color:var(--text-dim);font-size:13px;font-weight:500;transition:all .15s}}
.sb-link:hover,.sb-link.active{{color:var(--text);background:var(--glass)}}
.sb-link .dot{{width:5px;height:5px;border-radius:50%;background:var(--accent);opacity:.5;flex-shrink:0}}
.sb-div{{height:1px;background:var(--glass-b);margin:8px 12px}}
.cat-toggle{{width:100%;display:flex;align-items:center;gap:6px;padding:7px 16px;background:none;color:var(--text-dim);font-size:12px;font-weight:600;font-family:inherit;letter-spacing:.02em;transition:all .15s}}
.cat-toggle:hover{{color:var(--text);background:var(--glass)}}
.cat-icon{{font-size:13px;flex-shrink:0}}.cat-name{{flex:1;text-align:left}}
.cat-cnt{{font-size:10px;background:var(--glass);color:var(--text-muted);padding:1px 6px;border-radius:100px;border:1px solid var(--glass-b)}}
.cat-arrow{{transition:transform .2s;font-size:10px}}.cat-toggle.open .cat-arrow{{transform:rotate(180deg)}}
.cat-methods{{overflow:hidden;max-height:3000px;transition:max-height .3s ease}}.cat-methods.collapsed{{max-height:0}}
.sidebar-method{{display:block;padding:4px 16px 4px 36px;color:var(--text-muted);font-size:11.5px;font-family:'JetBrains Mono',monospace;transition:all .12s}}
.sidebar-method:hover{{color:var(--accent);background:var(--glass)}}.sidebar-method.active{{color:var(--accent);font-weight:600}}

/* MOBILE BOTTOM NAV */
.mob-bnav{{display:none;position:fixed;bottom:0;left:0;right:0;z-index:180;background:var(--sb-bg);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-top:1px solid var(--glass-b);padding:8px 0 env(safe-area-inset-bottom,4px);height:var(--mob-h)}}
@media(max-width:900px){{.mob-bnav{{display:flex}}}}
.mob-nb{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;font-size:9.5px;font-weight:600;color:var(--text-muted);padding:4px 0;letter-spacing:.03em;transition:color .15s}}
.mob-nb:hover,.mob-nb.active{{color:var(--accent)}}
.mob-nb .ni{{font-size:18px}}

/* MOBILE THEME FAB */
.mob-fab{{display:none;position:fixed;bottom:calc(var(--mob-h) + 12px);right:16px;z-index:160;background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-radius:50%;width:44px;height:44px;font-size:18px;align-items:center;justify-content:center;box-shadow:0 4px 20px rgba(0,0,0,.35);transition:all .2s}}
.mob-fab:hover{{transform:scale(1.08)}}
@media(max-width:900px){{.mob-fab{{display:flex}}}}
.mob-tpicker{{display:none;position:fixed;bottom:calc(var(--mob-h) + 66px);right:12px;z-index:161;background:var(--sb-bg);border:1px solid var(--glass-b);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-radius:12px;padding:6px;flex-direction:column;gap:4px;box-shadow:0 8px 40px rgba(0,0,0,.45)}}
.mob-tpicker.open{{display:flex}}
.mob-topt{{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;font-size:13px;font-weight:500;color:var(--text-dim);transition:all .15s;white-space:nowrap}}
.mob-topt:hover,.mob-topt.on{{background:var(--glass);color:var(--text)}}
.mob-topt.on .tck{{opacity:1}}.tck{{opacity:0;font-size:12px;color:var(--accent)}}

/* LAYOUT */
.layout{{display:flex;padding-top:var(--hdr-h);min-height:100vh}}
.main{{margin-left:var(--sb-w);flex:1;min-width:0;padding-bottom:var(--mob-h)}}
@media(max-width:900px){{.main{{margin-left:0}}}}

/* HERO */
.hero{{position:relative;overflow:hidden;padding:72px 48px 60px;border-bottom:1px solid var(--glass-b)}}
.hero-bg{{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 60% 80% at 80% 20%,var(--ga),transparent),radial-gradient(ellipse 50% 60% at 10% 80%,var(--gb),transparent)}}
.hero-content{{position:relative;z-index:1;max-width:800px}}
.hero-badge{{display:inline-flex;align-items:center;gap:6px;background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(12px);color:var(--accent);padding:4px 12px;border-radius:100px;font-size:12px;font-weight:600;margin-bottom:22px}}
.hero h1{{font-size:clamp(36px,6vw,58px);font-weight:900;line-height:1.08;letter-spacing:-.03em;margin-bottom:18px}}
.grad{{background:linear-gradient(135deg,var(--accent),#e879f9 50%,var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.hero-desc{{font-size:16px;color:var(--text-dim);margin-bottom:32px;max-width:580px;line-height:1.75}}
.hero-stats{{display:flex;gap:32px;flex-wrap:wrap;margin-bottom:36px}}
.stat-item{{display:flex;flex-direction:column;gap:3px}}
.stat-num{{font-size:clamp(22px,4vw,30px);font-weight:800}}.stat-label{{font-size:11px;color:var(--text-muted);font-weight:600;letter-spacing:.05em;text-transform:uppercase}}
.hero-btns{{display:flex;gap:10px;flex-wrap:wrap}}
.btn{{display:inline-flex;align-items:center;gap:7px;padding:10px 20px;border-radius:var(--rs);font-size:14px;font-weight:600;transition:all .2s;border:none;font-family:inherit;cursor:pointer}}
.btn-p{{background:var(--accent);color:#fff;box-shadow:0 4px 18px rgba(139,120,255,.35)}}.btn-p:hover{{background:var(--accent-h);transform:translateY(-1px);box-shadow:0 8px 28px rgba(139,120,255,.45)}}
.btn-g{{background:var(--glass);border:1px solid var(--glass-b);color:var(--text-dim)}}.btn-g:hover{{background:var(--glass-h);color:var(--text);border-color:var(--accent)}}
@media(max-width:600px){{.hero{{padding:48px 20px 40px}}.hero-stats{{gap:20px}}}}

/* SECTIONS */
.sec{{padding:48px;border-bottom:1px solid var(--glass-b)}}
.sec-h2{{font-size:24px;font-weight:800;margin-bottom:8px}}
.sec-sub{{color:var(--text-dim);font-size:14px;margin-bottom:28px;line-height:1.7}}
@media(max-width:600px){{.sec{{padding:32px 20px}}}}

/* GRIDS */
.ig{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
.ic{{background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(16px);border-radius:var(--r);padding:20px;overflow:hidden}}
.ic-t{{font-size:12px;font-weight:700;color:var(--text-dim);margin-bottom:12px;text-transform:uppercase;letter-spacing:.07em}}
.fg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
.fc{{background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(16px);border-radius:var(--r);padding:20px;transition:all .2s}}
.fc:hover{{border-color:rgba(139,120,255,.4);background:var(--glass-h);transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,.2)}}
.fi{{font-size:26px;margin-bottom:10px}}.ft{{font-size:14px;font-weight:700;margin-bottom:5px}}.fd{{font-size:13px;color:var(--text-dim);line-height:1.6}}

/* FILTER BAR */
.fbar{{padding:13px 24px;background:var(--hdr);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid var(--glass-b);display:flex;align-items:center;gap:8px;flex-wrap:nowrap;overflow-x:auto;position:sticky;top:var(--hdr-h);z-index:100;scrollbar-width:none}}
.fbar::-webkit-scrollbar{{display:none}}
.fl{{font-size:11px;color:var(--text-muted);font-weight:700;flex-shrink:0;letter-spacing:.05em}}
.fc2{{padding:5px 12px;border-radius:100px;background:var(--glass);border:1px solid var(--glass-b);color:var(--text-dim);font-size:12px;font-weight:500;transition:all .15s;white-space:nowrap;flex-shrink:0}}
.fc2:hover,.fc2.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.rc{{margin-left:auto;font-size:11px;color:var(--text-muted);flex-shrink:0}}

/* METHOD CARDS */
.cat-section{{padding:0 24px 40px;scroll-margin-top:calc(var(--hdr-h)+60px)}}
@media(max-width:600px){{.cat-section{{padding:0 12px 32px}}}}
.cat-header{{display:flex;align-items:center;gap:10px;padding:36px 0 18px;border-bottom:1px solid var(--glass-b);margin-bottom:18px}}
.cat-title{{font-size:18px;font-weight:800}}.cat-count{{font-size:11px;background:var(--glass);border:1px solid var(--glass-b);padding:2px 9px;border-radius:100px;color:var(--text-muted)}}
.methods-grid{{display:flex;flex-direction:column;gap:10px}}
.method-card{{background:var(--glass);backdrop-filter:blur(16px) saturate(1.4);-webkit-backdrop-filter:blur(16px) saturate(1.4);border:1px solid var(--glass-b);border-radius:var(--r);overflow:hidden;transition:border-color .2s,box-shadow .2s;scroll-margin-top:calc(var(--hdr-h)+70px)}}
.method-card:hover{{border-color:var(--border-bright);box-shadow:0 2px 20px rgba(0,0,0,.2)}}.method-card:target{{border-color:var(--accent);box-shadow:0 0 0 2px rgba(139,120,255,.2)}}.method-card.hidden{{display:none}}
.method-header{{padding:15px 20px 11px;border-bottom:1px solid transparent;cursor:pointer;user-select:none;transition:background .15s}}
.method-header:hover{{background:var(--glass-h)}}.method-card.expanded .method-header{{border-bottom-color:var(--glass-b)}}
.method-name-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}}
.method-name{{font-family:'JetBrains Mono',monospace;font-size:clamp(13px,2.5vw,15px);font-weight:600;color:var(--accent)}}
.method-badges{{display:flex;gap:5px;align-items:center;flex-wrap:wrap;flex:1}}
.badge{{font-size:10px;font-weight:700;padding:2px 7px;border-radius:100px;letter-spacing:.04em}}
.badge-async{{background:rgba(56,189,248,.09);color:var(--accent2);border:1px solid rgba(56,189,248,.2)}}
.badge-ret{{background:rgba(52,211,153,.07);color:var(--accent3);border:1px solid rgba(52,211,153,.18);font-family:'JetBrains Mono',monospace;font-size:9.5px}}
.badge-opt{{background:rgba(251,191,36,.07);color:var(--yellow);border:1px solid rgba(251,191,36,.18)}}
.cta{{font-size:11px;color:var(--text-muted);transition:transform .22s;margin-left:auto;flex-shrink:0}}.method-card.expanded .cta{{transform:rotate(180deg)}}
.method-doc{{font-size:13px;color:var(--text-dim);line-height:1.6;max-width:720px}}
.method-body{{overflow:hidden;max-height:0;transition:max-height .3s ease}}.collapsed-body{{max-height:0}}.method-card.expanded .method-body{{max-height:99999px}}
.params-section{{padding:12px 20px;border-bottom:1px solid var(--glass-b)}}.optional-section{{padding:12px 20px;border-bottom:1px solid var(--glass-b)}}.example-section{{padding:12px 20px;border-bottom:1px solid var(--glass-b)}}
.section-label{{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--text-muted);margin-bottom:8px;display:flex;align-items:center;gap:8px}}
.field-count{{font-size:9px;background:var(--glass);border:1px solid var(--glass-b);padding:1px 6px;border-radius:100px;color:var(--accent);text-transform:none;letter-spacing:0}}
.param-pills{{display:flex;flex-wrap:wrap;gap:5px}}
.param-pill{{font-family:'JetBrains Mono',monospace;font-size:11px;padding:3px 9px;border-radius:6px;cursor:help}}
.param-pill.required{{background:rgba(139,120,255,.11);color:var(--accent);border:1px solid rgba(139,120,255,.22)}}
.param-pill.optional{{background:rgba(100,116,139,.06);color:var(--text-muted);border:1px solid var(--glass-b)}}
.no-params{{font-size:12px;color:var(--text-muted);font-style:italic}}
.table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:var(--rs)}}
.fields-table{{width:100%;border-collapse:collapse;font-size:12px;min-width:380px}}
.fields-table th{{text-align:left;padding:7px 10px;background:var(--glass);color:var(--text-muted);font-weight:700;font-size:9.5px;text-transform:uppercase;letter-spacing:.07em;border-bottom:1px solid var(--glass-b)}}
.fields-table td{{padding:6px 10px;vertical-align:top;border-bottom:1px solid rgba(255,255,255,.03)}}.fields-table tr:last-child td{{border-bottom:none}}.fields-table tr:hover td{{background:var(--glass)}}
.field-name{{font-family:'JetBrains Mono',monospace;color:var(--accent3);font-size:11px;white-space:nowrap;font-weight:500}}
.field-type{{font-family:'JetBrains Mono',monospace;color:var(--blue);font-size:11px}}.field-doc{{color:var(--text-dim);line-height:1.5}}
.example-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.example-actions{{display:flex;gap:6px;align-items:center}}
.anchor-btn{{font-size:14px;padding:4px 8px;border-radius:6px;background:var(--glass);border:1px solid var(--glass-b);color:var(--text-muted);transition:all .15s}}
.anchor-btn:hover{{color:var(--accent);border-color:var(--accent)}}
.copy-btn{{font-size:11px;padding:5px 11px;border-radius:7px;background:var(--glass);border:1px solid var(--glass-b);color:var(--text-dim);font-family:inherit;transition:all .15s;font-weight:600}}
.copy-btn:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}.copy-btn.copied{{background:var(--green);color:#000;border-color:var(--green)}}
.code-block{{background:var(--code-bg)!important;border-radius:var(--rs);overflow:auto;font-size:12.5px;line-height:1.65;border:1px solid var(--glass-b);-webkit-overflow-scrolling:touch}}
.code-block code{{padding:14px 18px;display:block;font-family:'JetBrains Mono',monospace}}
@media(max-width:480px){{.code-block{{font-size:11.5px}}}}
.method-footer{{padding:10px 20px;display:flex;gap:12px;align-items:center}}
.tg-link{{font-size:12px;color:var(--text-muted);transition:color .15s}}.tg-link:hover{{color:var(--accent2)}}

/* TYPES */
.types-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:16px}}
.type-card{{background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(12px);border-radius:var(--rs);padding:14px;transition:all .2s;scroll-margin-top:calc(var(--hdr-h)+60px)}}
.type-card:hover{{border-color:var(--border-bright);background:var(--glass-h)}}
.type-name{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--purple);margin-bottom:9px;display:flex;align-items:center;gap:7px}}
.type-field-count{{font-size:9px;background:var(--glass);border:1px solid var(--glass-b);padding:1px 5px;border-radius:100px;color:var(--text-muted);font-family:'Inter',sans-serif;font-weight:600}}
.type-field{{display:flex;justify-content:space-between;gap:8px;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.03)}}.type-field:last-child{{border-bottom:none}}
.type-field-name{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent3)}}
.type-field-type{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--blue);opacity:.8;text-align:right}}
.type-empty{{font-size:11px;color:var(--text-muted);font-style:italic}}
.enums-grid{{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}}
.enum-card{{background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(12px);border-radius:var(--rs);padding:14px}}
.enum-name{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--yellow);margin-bottom:8px}}
.enum-variants{{display:flex;flex-wrap:wrap;gap:4px}}
.enum-variant{{font-family:'JetBrains Mono',monospace;font-size:11px;background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.14);color:var(--yellow);padding:2px 8px;border-radius:5px}}

/* TABS */
.tabs{{display:flex;gap:2px;border-bottom:1px solid var(--glass-b);margin-bottom:24px;overflow-x:auto}}
.tab{{padding:10px 18px;border-radius:var(--rs) var(--rs) 0 0;font-size:13px;font-weight:600;color:var(--text-muted);background:none;border:none;font-family:inherit;border-bottom:2px solid transparent;transition:all .15s;white-space:nowrap}}
.tab:hover{{color:var(--text)}}.tab.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.tab-panel{{display:none}}.tab-panel.active{{display:block}}
.err-sec{{background:var(--glass);border:1px solid var(--glass-b);backdrop-filter:blur(12px);border-radius:var(--r);padding:22px;margin-bottom:14px}}
.ev{{margin-bottom:18px}}.ev:last-child{{margin-bottom:0}}
.ev-name{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--red);margin-bottom:4px}}
.ev-desc{{font-size:13px;color:var(--text-dim)}}

/* SEARCH DROP */
.search-drop{{position:fixed;background:var(--sb-bg);border:1px solid var(--glass-b);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.55);z-index:99999;display:none;overflow:hidden}}
.search-drop.open{{display:block}}
.sd-head{{padding:8px 14px 6px;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text-muted);background:var(--glass);border-bottom:1px solid var(--glass-b)}}
.sd-list{{max-height:340px;overflow-y:auto}}
.sd-row{{display:flex;align-items:center;gap:8px;padding:9px 14px;cursor:pointer;transition:background .1s;border-bottom:1px solid var(--glass-b)}}
.sd-row:last-child{{border-bottom:none}}.sd-row:hover,.sd-row.focus{{background:var(--glass)}}
.sd-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.sd-name{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--accent);flex-shrink:0}}
.sd-name mark{{background:rgba(139,120,255,.2);color:var(--accent);border-radius:2px;padding:0 1px;font-style:normal;font-weight:700}}
.sd-doc{{font-size:11px;color:var(--text-muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.sd-cat{{font-size:9.5px;color:var(--text-muted);background:var(--glass);border:1px solid var(--glass-b);padding:1px 6px;border-radius:4px;flex-shrink:0}}
.sd-empty{{padding:24px;text-align:center;color:var(--text-muted);font-size:13px}}
.sd-footer{{padding:6px 14px;font-size:10px;color:var(--text-muted);background:var(--glass);border-top:1px solid var(--glass-b);display:flex;justify-content:space-between}}
.sd-footer kbd{{background:var(--glass);border:1px solid var(--glass-b);border-radius:3px;padding:0 4px;font-family:'JetBrains Mono',monospace;font-size:9px}}
@media(max-width:600px){{.search-drop{{left:8px!important;right:8px!important;width:auto!important}}.sd-footer{{display:none}}}}

/* FOOTER */
.footer{{margin-left:var(--sb-w);padding:36px 48px;border-top:1px solid var(--glass-b);background:var(--glass);backdrop-filter:blur(16px);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px}}
@media(max-width:900px){{.footer{{margin-left:0;padding:28px 20px}}}}
.footer-links{{display:flex;gap:16px;flex-wrap:wrap}}
.footer-links a{{font-size:13px;color:var(--text-muted);transition:color .15s}}.footer-links a:hover{{color:var(--accent)}}
.hljs{{background:transparent!important}}[data-theme="light"] pre code{{color:#cdd6f4}}
</style>
</head>
<body>

<div class="search-drop" id="searchDrop">
  <div class="sd-head" id="sdHead">Methods</div>
  <div class="sd-list" id="sdList"></div>
  <div class="sd-footer"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> jump</span><span><kbd>Esc</kbd> close</span></div>
</div>

<div class="sb-overlay" id="sbOverlay" onclick="closeSidebar()"></div>

<!-- Mobile theme picker -->
<div class="mob-tpicker" id="mobTP">
  <button class="mob-topt" data-t="light" onclick="setTheme('light')">☀️ Light <span class="tck">✓</span></button>
  <button class="mob-topt" data-t="dark" onclick="setTheme('dark')">🌙 Dark <span class="tck">✓</span></button>
  <button class="mob-topt" data-t="amoled" onclick="setTheme('amoled')">⬛ AMOLED <span class="tck">✓</span></button>
</div>
<button class="mob-fab" id="mobFab" onclick="toggleMobTheme()" title="Change theme">🎨</button>

<header class="hdr">
  <button class="mob-menu-btn" onclick="openSidebar()" aria-label="Menu">☰</button>
  <a class="logo" href="https://{CUSTOM_DOMAIN}">
    <div class="logo-icon">🦀</div>
    <span class="logo-text">tgbotrs</span>
    <span class="logo-ver">v{CRATE_VERSION}</span>
  </a>
  <div class="hdr-search" id="searchOuter">
    <span class="s-ico">🔍</span>
    <input type="text" id="globalSearch" placeholder="Search {S["methods"]} methods… (Ctrl+K)" autocomplete="off">
    <span class="s-kbd">Ctrl K</span>
  </div>
  <nav class="hdr-nav">
    <a href="#quick-start" class="nav-hide">Start</a>
    <a href="#methods" class="nav-hide">Methods</a>
    <a href="#types" class="nav-hide">Types</a>
    <div class="theme-sw">
      <button class="th-btn" data-t="light" onclick="setTheme('light')" title="Light">☀️</button>
      <button class="th-btn" data-t="dark" onclick="setTheme('dark')" title="Dark">🌙</button>
      <button class="th-btn" data-t="amoled" onclick="setTheme('amoled')" title="AMOLED">⬛</button>
    </div>
    <a href="https://github.com/ankit-chaubey/tgbotrs" target="_blank" class="btn-gh">⭐ GitHub</a>
  </nav>
</header>

<div class="layout">
<aside class="sidebar" id="sidebar">
  <div class="sb-search"><input type="text" id="sbSearch" placeholder="🔍 Filter methods…" autocomplete="off"></div>
  <div class="sb-ttl">Navigation</div>
  <a class="sb-link" href="#quick-start" onclick="closeSidebar()"><span class="dot"></span>Quick Start</a>
  <a class="sb-link" href="#installation" onclick="closeSidebar()"><span class="dot"></span>Installation</a>
  <a class="sb-link" href="#features" onclick="closeSidebar()"><span class="dot"></span>Features</a>
  <a class="sb-link" href="#methods" onclick="closeSidebar()"><span class="dot"></span>All Methods</a>
  <a class="sb-link" href="#types" onclick="closeSidebar()"><span class="dot"></span>Types ({S["types"]})</a>
  <a class="sb-link" href="#errors" onclick="closeSidebar()"><span class="dot"></span>Error Handling</a>
  <a class="sb-link" href="#polling" onclick="closeSidebar()"><span class="dot"></span>Long Polling</a>
  <a class="sb-link" href="#webhook" onclick="closeSidebar()"><span class="dot"></span>Webhook</a>
  <div class="sb-div"></div>
  <div class="sb-ttl">Methods by Category</div>
  {sidebar_html}
</aside>

<main class="main">
<div class="hero">
  <div class="hero-bg"></div>
  <div class="hero-content">
    <div class="hero-badge">🦀 Telegram Bot API 9.4 · Fully Auto-Generated</div>
    <h1>The <span class="grad">complete</span> Rust<br>Telegram Bot library</h1>
    <p class="hero-desc"><strong>tgbotrs</strong> gives you every Telegram Bot API method and type — fully typed, fully async, auto-generated from the official spec. Built with Tokio. Lowest supported: <strong>v{CRATE_VERSION}</strong>.</p>
    <div class="hero-stats">
      <div class="stat-item"><span class="stat-num">{S["methods"]}</span><span class="stat-label">Methods</span></div>
      <div class="stat-item"><span class="stat-num">{S["types"]}</span><span class="stat-label">Types</span></div>
      <div class="stat-item"><span class="stat-num">9.4</span><span class="stat-label">API Version</span></div>
      <div class="stat-item"><span class="stat-num">100%</span><span class="stat-label">Async</span></div>
    </div>
    <div class="hero-btns">
      <a href="#quick-start" class="btn btn-p">🚀 Get Started</a>
      <a href="https://crates.io/crates/tgbotrs" target="_blank" class="btn btn-g">📦 crates.io</a>
      <a href="https://docs.rs/tgbotrs" target="_blank" class="btn btn-g">📖 docs.rs</a>
      <a href="https://github.com/ankit-chaubey/tgbotrs" target="_blank" class="btn btn-g">★ GitHub</a>
    </div>
  </div>
</div>

<section class="sec" id="quick-start">
  <h2 class="sec-h2">🚀 Quick Start</h2>
  <p class="sec-sub">Get your first bot running in under 2 minutes.</p>
  <div style="display:flex;flex-direction:column;gap:14px;max-width:800px">
    <div class="ic"><div class="ic-t">Step 1 — Get your bot token</div><div style="font-size:13px;color:var(--text-dim)">Chat with <a href="https://t.me/BotFather" target="_blank" style="color:var(--accent2)">@BotFather</a> → /newbot → copy your token.</div></div>
    <div class="ic"><div class="ic-t">Step 2 — Cargo.toml</div><div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Cargo.toml</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
    <pre class="code-block"><code class="language-toml">[dependencies]
tgbotrs = "{CRATE_VERSION}"
tokio   = {{ version = "1", features = ["full"] }}</code></pre></div>
    <div class="ic"><div class="ic-t">Step 3 — src/main.rs</div><div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">src/main.rs</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
    <pre class="code-block"><code class="language-rust">use tgbotrs::{{Bot, Poller, UpdateHandler}};

#[tokio::main]
async fn main() {{
    let bot = Bot::new("YOUR_BOT_TOKEN").await.unwrap();
    let handler: UpdateHandler = Box::new(|bot, update| {{
        Box::pin(async move {{
            let Some(msg) = update.message else {{ return }};
            let Some(text) = msg.text else {{ return }};
            let reply = match text.as_str() {{
                "/start" => "👋 Hello! Powered by tgbotrs 🦀".to_string(),
                other    => format!("Echo: {{}}", other),
            }};
            let _ = bot.send_message(msg.chat.id, reply, None).await;
        }})
    }});
    Poller::new(bot, handler).timeout(30).start().await.unwrap();
}}</code></pre></div>
    <div class="ic"><div class="ic-t">Step 4 — Run</div><pre class="code-block"><code class="language-bash">cargo run</code></pre></div>
  </div>
</section>

<section class="sec" id="installation">
  <h2 class="sec-h2">📦 Installation</h2>
  <p class="sec-sub">Minimum supported: <strong>v{CRATE_VERSION}</strong></p>
  <div class="ig">
    <div class="ic"><div class="ic-t">Standard (Long Polling)</div><div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Cargo.toml</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
    <pre class="code-block"><code class="language-toml">[dependencies]
tgbotrs = "{CRATE_VERSION}"
tokio   = {{ version = "1", features = ["full"] }}</code></pre></div>
    <div class="ic"><div class="ic-t">With Webhook Feature</div><div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">Cargo.toml</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
    <pre class="code-block"><code class="language-toml">[dependencies]
tgbotrs = {{ version = "{CRATE_VERSION}", features = ["webhook"] }}
tokio   = {{ version = "1", features = ["full"] }}</code></pre></div>
    <div class="ic"><div class="ic-t">Dependencies Included</div><div style="font-size:13px;color:var(--text-dim);line-height:2">✅ reqwest<br>✅ serde + serde_json<br>✅ tokio<br>✅ thiserror<br>🔌 axum (webhook only)</div></div>
    <div class="ic"><div class="ic-t">Env-based Token</div><div class="example-header" style="margin-bottom:8px"><span style="font-size:11px;color:var(--text-muted)">src/main.rs</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
    <pre class="code-block"><code class="language-rust">let token = std::env::var("BOT_TOKEN").expect("BOT_TOKEN not set");
let bot = Bot::new(token).await?;</code></pre></div>
  </div>
</section>

<section class="sec" id="features">
  <h2 class="sec-h2">✨ Features</h2>
  <p class="sec-sub">Everything you need to build powerful Telegram bots in Rust.</p>
  <div class="fg">
    <div class="fc"><div class="fi">⚡</div><div class="ft">Fully Async</div><div class="fd">Built on Tokio. Handle thousands of concurrent updates.</div></div>
    <div class="fc"><div class="fi">🔒</div><div class="ft">Strongly Typed</div><div class="fd">Every method, parameter and response is strongly typed. Compile-time safety.</div></div>
    <div class="fc"><div class="fi">🤖</div><div class="ft">Auto-Generated</div><div class="fd">All {S["methods"]} methods and {S["types"]} types auto-generated from the official spec.</div></div>
    <div class="fc"><div class="fi">🏗️</div><div class="ft">Builder Pattern</div><div class="fd">Chain optional params like <code style="background:var(--glass);padding:1px 5px;border-radius:3px">.parse_mode("HTML")</code>.</div></div>
    <div class="fc"><div class="fi">🪝</div><div class="ft">Built-in Webhook</div><div class="fd">Optional axum-based webhook server. One line to switch from polling.</div></div>
    <div class="fc"><div class="fi">📁</div><div class="ft">File Uploads</div><div class="fd">Upload by path, URL, or bytes. InputFile handles multipart transparently.</div></div>
    <div class="fc"><div class="fi">🎯</div><div class="ft">ChatId Flexibility</div><div class="fd">Pass IDs as i64, &str, or @username — all conversions automatic.</div></div>
    <div class="fc"><div class="fi">🎮</div><div class="ft">All Keyboard Types</div><div class="fd">InlineKeyboard, ReplyKeyboard, ForceReply — all four types supported.</div></div>
    <div class="fc"><div class="fi">🔧</div><div class="ft">Custom API Server</div><div class="fd">Use <code style="background:var(--glass);padding:1px 5px;border-radius:3px">Bot::with_api_url()</code> to point at your own server.</div></div>
  </div>
</section>

<section class="sec" id="polling">
  <h2 class="sec-h2">🔄 Long Polling</h2>
  <p class="sec-sub">Simplest way to receive updates — no external server needed.</p>
  <div style="max-width:800px">
    <div class="example-header" style="margin-bottom:8px"><span style="font-size:13px;font-weight:700;color:var(--text-dim)">Polling with inline keyboard</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
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
                        inline_keyboard: vec![vec![InlineKeyboardButton {{
                            text: "🔵 Click me".into(),
                            callback_data: Some("btn1".into()),
                            ..Default::default()
                        }}]]
                    }});
                    let params = SendMessageParams::new().reply_markup(keyboard);
                    let _ = bot.send_message(msg.chat.id, "Pick a button 👇", Some(params)).await;
                }}
            }}
            if let Some(cq) = update.callback_query {{
                let _ = bot.answer_callback_query(cq.id,
                    Some(AnswerCallbackQueryParams::new().text("Clicked! ✅".to_string()))
                ).await;
            }}
        }})
    }});
    Poller::new(bot, handler).timeout(30).limit(100).start().await.unwrap();
}}</code></pre>
  </div>
</section>

<section class="sec" id="webhook">
  <h2 class="sec-h2">🪝 Webhook Server</h2>
  <p class="sec-sub">Production-ready webhook server powered by Axum.</p>
  <div style="max-width:800px">
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
        .port(8080).path("/webhook")
        .secret_token("my_secret").max_connections(40)
        .start("https://yourdomain.com").await.unwrap();
}}</code></pre>
  </div>
</section>

<section id="methods">
  <div class="fbar">
    <span class="fl">Filter:</span>
    <button class="fc2 active" onclick="filterCat('all',this)">All ({S["methods"]})</button>
    <button class="fc2" onclick="filterCat('Sending Messages',this)">📤 Send</button>
    <button class="fc2" onclick="filterCat('Getting Info',this)">ℹ️ Get</button>
    <button class="fc2" onclick="filterCat('Editing',this)">✏️ Edit</button>
    <button class="fc2" onclick="filterCat('Deletion',this)">🗑️ Delete</button>
    <button class="fc2" onclick="filterCat('Chat Administration',this)">🛡️ Admin</button>
    <button class="fc2" onclick="filterCat('Stickers',this)">😸 Stickers</button>
    <button class="fc2" onclick="filterCat('Payments & Stars',this)">💰 Payments</button>
    <button class="fc2" onclick="filterCat('Updates & Webhook',this)">🔄 Updates</button>
    <button class="fc2" onclick="filterCat('Configuration',this)">⚙️ Config</button>
    <span class="rc" id="resultsCount">{S["methods"]} methods</span>
  </div>
  <div id="methodsContainer" style="padding:0 0 8px">
{method_cards}
  </div>
</section>

<section class="sec" id="types">
  <h2 class="sec-h2">📐 Types Reference</h2>
  <p class="sec-sub">All {S["types"]} Telegram types — every field shown. See <a href="https://docs.rs/tgbotrs" target="_blank" style="color:var(--accent2)">docs.rs</a> for full rustdoc.</p>
  <div class="tabs">
    <button class="tab active" onclick="showTab('structs',this)">Structs ({S["types"]})</button>
    <button class="tab" onclick="showTab('enums',this)">Enums ({S["enums"]})</button>
    <button class="tab" onclick="showTab('special',this)">Special Types</button>
  </div>
  <div id="tab-structs" class="tab-panel active"><div class="types-grid">{types_html}</div></div>
  <div id="tab-enums" class="tab-panel"><div class="enums-grid">{enums_html}</div></div>
  <div id="tab-special" class="tab-panel">
    <div style="display:flex;flex-direction:column;gap:14px;max-width:800px">
      <div class="err-sec"><div style="font-size:16px;font-weight:700;margin-bottom:12px;font-family:'JetBrains Mono',monospace;color:var(--purple)">ChatId</div><p style="font-size:13px;color:var(--text-dim);margin-bottom:12px">Accepts numeric IDs or username strings.</p><pre class="code-block"><code class="language-rust">bot.send_message(123456789i64, "text", None).await?;
bot.send_message("@mychannel", "text", None).await?;</code></pre></div>
      <div class="err-sec"><div style="font-size:16px;font-weight:700;margin-bottom:12px;font-family:'JetBrains Mono',monospace;color:var(--purple)">InputFile</div><p style="font-size:13px;color:var(--text-dim);margin-bottom:12px">Flexible file input — path, URL, or bytes.</p><pre class="code-block"><code class="language-rust">use tgbotrs::InputFile;
let by_path  = InputFile::path("photo.jpg");
let by_url   = InputFile::url("https://example.com/photo.jpg");
let by_bytes = InputFile::bytes("photo.jpg", std::fs::read("photo.jpg").unwrap());</code></pre></div>
    </div>
  </div>
</section>

<section class="sec" id="errors">
  <h2 class="sec-h2">⚠️ Error Handling</h2>
  <p class="sec-sub">All calls return <code style="background:var(--glass);padding:1px 6px;border-radius:4px">Result&lt;T, BotError&gt;</code></p>
  <div style="max-width:800px;display:flex;flex-direction:column;gap:14px">
    <div class="err-sec">
      <div style="font-size:15px;font-weight:700;margin-bottom:14px;font-family:'JetBrains Mono',monospace">BotError variants</div>
      <div class="ev"><div class="ev-name">BotError::Api {{ code, description, retry_after, migrate_to_chat_id }}</div><div class="ev-desc">Telegram returned ok=false. 429=flood, 403=blocked, 400=bad request.</div></div>
      <div class="ev"><div class="ev-name">BotError::Http(reqwest::Error)</div><div class="ev-desc">Network error — connection refused, timeout, DNS failure.</div></div>
      <div class="ev"><div class="ev-name">BotError::Json(serde_json::Error)</div><div class="ev-desc">Failed to (de)serialize request or response.</div></div>
      <div class="ev"><div class="ev-name">BotError::InvalidToken</div><div class="ev-desc">Token doesn't contain a colon — invalid format.</div></div>
    </div>
    <div class="example-header" style="margin-bottom:8px"><span style="font-size:13px;font-weight:700;color:var(--text-dim)">Error handling patterns</span><button class="copy-btn" onclick="copyCode(this)">📋 Copy</button></div>
    <pre class="code-block"><code class="language-rust">match bot.send_message(chat_id, text, None).await {{
    Ok(msg) => println!("Sent #{{}}", msg.message_id),
    Err(BotError::Api {{ code: 403, .. }}) => println!("Bot was blocked"),
    Err(BotError::Api {{ code: 429, retry_after: Some(secs), .. }}) => {{
        tokio::time::sleep(std::time::Duration::from_secs(secs as u64)).await;
    }}
    Err(e) => eprintln!("Error: {{}}", e),
}}</code></pre>
  </div>
</section>
</main>
</div>

<nav class="mob-bnav">
  <button class="mob-nb" onclick="scrollTo(0,0)"><span class="ni">🏠</span>Home</button>
  <button class="mob-nb" onclick="document.getElementById('methods').scrollIntoView({{behavior:'smooth'}})"><span class="ni">⚡</span>Methods</button>
  <button class="mob-nb" onclick="openSidebar()"><span class="ni">☰</span>Menu</button>
  <button class="mob-nb" onclick="document.getElementById('types').scrollIntoView({{behavior:'smooth'}})"><span class="ni">📐</span>Types</button>
  <button class="mob-nb" onclick="document.getElementById('globalSearch').focus();document.getElementById('globalSearch').select()"><span class="ni">🔍</span>Search</button>
</nav>

<footer class="footer">
  <div style="display:flex;align-items:center;gap:10px">
    <div class="logo-icon" style="width:32px;height:32px;font-size:16px">🦀</div>
    <div><div style="font-size:14px;font-weight:700">tgbotrs v{CRATE_VERSION}</div><div style="font-size:12px;color:var(--text-muted)">By <a href="https://github.com/ankit-chaubey" target="_blank" style="color:var(--accent)">Ankit Chaubey</a></div></div>
  </div>
  <div style="font-size:12px;color:var(--text-muted)">Telegram Bot API 9.4 · {S["methods"]} methods · {S["types"]} types · MIT</div>
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
const IDX={{SEARCH_INDEX_PLACEHOLDER}};
// Theme (apply early, no flash)
(function(){{const t=localStorage.getItem('tg-theme')||'amoled';document.documentElement.setAttribute('data-theme',t);}})();
function setTheme(t){{
  document.documentElement.setAttribute('data-theme',t);
  localStorage.setItem('tg-theme',t);
  document.querySelectorAll('.th-btn[data-t]').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
  document.querySelectorAll('.mob-topt[data-t]').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
  const icons={{light:'☀️',dark:'🌙',amoled:'⬛'}};
  document.getElementById('mobFab').textContent=icons[t]||'🎨';
  document.getElementById('mobTP').classList.remove('open');
}}
document.addEventListener('DOMContentLoaded',()=>{{
  setTheme(localStorage.getItem('tg-theme')||'amoled');
  document.querySelectorAll('pre code').forEach(el=>hljs.highlightElement(el));
}});
function toggleMobTheme(){{document.getElementById('mobTP').classList.toggle('open');}}
document.addEventListener('click',e=>{{
  const fab=document.getElementById('mobFab'),tp=document.getElementById('mobTP');
  if(!fab.contains(e.target)&&!tp.contains(e.target))tp.classList.remove('open');
}});
function openSidebar(){{document.getElementById('sidebar').classList.add('open');document.getElementById('sbOverlay').classList.add('open');document.body.style.overflow='hidden';}}
function closeSidebar(){{document.getElementById('sidebar').classList.remove('open');document.getElementById('sbOverlay').classList.remove('open');document.body.style.overflow='';}}
function copyCode(btn){{
  let el=btn,pre=null;
  for(let i=0;i<8;i++){{el=el.parentElement;if(!el)break;pre=el.querySelector('pre');if(pre)break;}}
  const text=pre?pre.innerText:'',orig=btn.textContent;
  navigator.clipboard.writeText(text.trim()).then(()=>{{
    btn.textContent='✅ Copied!';btn.classList.add('copied');
    setTimeout(()=>{{btn.textContent=orig;btn.classList.remove('copied');}},2000);
  }}).catch(()=>{{
    const ta=document.createElement('textarea');ta.value=text.trim();document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);
    btn.textContent='✅ Copied!';setTimeout(()=>btn.textContent=orig,2000);
  }});
}}
function toggleCard(header){{
  const card=header.closest('.method-card'),body=card.querySelector('.method-body');
  const isOpen=card.classList.contains('expanded');
  card.classList.toggle('expanded',!isOpen);body.classList.toggle('collapsed-body',isOpen);
}}
function toggleCat(btn){{
  const id=btn.dataset.catId,panel=document.getElementById('sidebar-'+id);
  if(!panel)return;
  const open=panel.classList.contains('collapsed');
  panel.classList.toggle('collapsed',!open);btn.classList.toggle('open',open);
}}
function showTab(id,btn){{
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');btn.classList.add('active');
}}
function filterCat(cat,btn){{
  document.querySelectorAll('.fc2').forEach(c=>c.classList.remove('active'));btn.classList.add('active');
  let visible=0;
  document.querySelectorAll('.method-card').forEach(card=>{{
    const show=cat==='all'||card.dataset.cat===cat;
    card.classList.toggle('hidden',!show);if(show)visible++;
  }});
  document.getElementById('resultsCount').textContent=visible+' methods';
  document.querySelectorAll('.cat-section').forEach(s=>{{s.style.display=s.querySelectorAll('.method-card:not(.hidden)').length>0?'':'none';}});
  closeSearch();
}}
const inp=document.getElementById('globalSearch'),drop=document.getElementById('searchDrop'),list=document.getElementById('sdList'),head=document.getElementById('sdHead');
let focused=-1;
function positionDrop(){{
  const r=document.getElementById('searchOuter').getBoundingClientRect(),mob=window.innerWidth<600;
  if(mob){{drop.style.top=(r.bottom+4)+'px';drop.style.left='8px';drop.style.right='8px';drop.style.width='auto';}}
  else{{drop.style.top=(r.bottom+5)+'px';drop.style.left=Math.max(8,r.left)+'px';drop.style.width=Math.max(420,r.width)+'px';}}
}}
function openSearch(){{positionDrop();drop.classList.add('open');}}
function closeSearch(){{drop.classList.remove('open');focused=-1;}}
function hl(str,q){{if(!q)return str;const i=str.toLowerCase().indexOf(q.toLowerCase());if(i<0)return str;return str.slice(0,i)+'<mark>'+str.slice(i,i+q.length)+'</mark>'+str.slice(i+q.length);}}
function renderResults(q){{
  const ql=q.toLowerCase(),all=IDX.filter(m=>m.n.includes(ql)||m.d.toLowerCase().includes(ql)),res=all.slice(0,20);
  head.textContent='Methods — '+all.length+' result'+(all.length!==1?'s':'');
  if(!res.length){{list.innerHTML='<div class="sd-empty">No methods match "<b>'+q+'</b>"</div>';}}
  else{{list.innerHTML=res.map(m=>`<div class="sd-row" data-anchor="method-${{m.n.replace(/_/g,'-')}}" onclick="goTo('method-${{m.n.replace(/_/g,'-')}}')"><span class="sd-dot" style="background:${{m.col}}"></span><span class="sd-name">${{hl('bot.'+m.n+'()',q)}}</span><span class="sd-doc">${{hl(m.d,q)}}</span><span class="sd-cat">${{m.c}}</span></div>`).join('');}}
  focused=-1;
}}
function goTo(anchor){{
  closeSearch();inp.value='';restoreAll();closeSidebar();
  const el=document.getElementById(anchor);
  if(el){{
    if(!el.classList.contains('expanded')){{el.classList.add('expanded');el.querySelector('.method-body')?.classList.remove('collapsed-body');}}
    el.scrollIntoView({{behavior:'smooth',block:'start'}});
    el.style.outline='2px solid var(--accent)';el.style.outlineOffset='3px';
    setTimeout(()=>{{el.style.outline='';el.style.outlineOffset='';}},1400);
  }}
}}
function restoreAll(){{
  document.querySelectorAll('.method-card').forEach(c=>c.classList.remove('hidden'));
  document.querySelectorAll('.cat-section').forEach(s=>s.style.display='');
  document.getElementById('resultsCount').textContent=IDX.length+' methods';
  document.querySelectorAll('.fc2').forEach((c,i)=>c.classList.toggle('active',i===0));
}}
inp.addEventListener('focus',()=>{{if(inp.value.trim())openSearch();}});
inp.addEventListener('input',function(){{
  const q=this.value.trim();if(!q){{closeSearch();restoreAll();return;}}
  renderResults(q);openSearch();
  const ql=q.toLowerCase();let visible=0;
  document.querySelectorAll('.method-card').forEach(card=>{{
    const match=card.dataset.name.includes(ql)||(card.querySelector('.method-doc')?.textContent||'').toLowerCase().includes(ql);
    card.classList.toggle('hidden',!match);if(match)visible++;
  }});
  document.getElementById('resultsCount').textContent=visible+' methods';
  document.querySelectorAll('.cat-section').forEach(s=>{{s.style.display=s.querySelectorAll('.method-card:not(.hidden)').length>0?'':'none';}});
  document.querySelectorAll('.fc2').forEach((c,i)=>c.classList.toggle('active',i===0));
}});
document.addEventListener('click',e=>{{if(!inp.contains(e.target)&&!drop.contains(e.target))closeSearch();}});
document.addEventListener('keydown',e=>{{
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){{e.preventDefault();inp.focus();inp.select();openSearch();}}
  if(e.key==='Escape'){{closeSearch();closeSidebar();document.getElementById('mobTP').classList.remove('open');}}
  if(drop.classList.contains('open')){{
    const rows=list.querySelectorAll('.sd-row');
    if(e.key==='ArrowDown'){{e.preventDefault();rows.forEach(r=>r.classList.remove('focus'));focused=Math.min(rows.length-1,focused+1);rows[focused]?.classList.add('focus');rows[focused]?.scrollIntoView({{block:'nearest'}});}}
    if(e.key==='ArrowUp'){{e.preventDefault();rows.forEach(r=>r.classList.remove('focus'));focused=Math.max(0,focused-1);rows[focused]?.classList.add('focus');rows[focused]?.scrollIntoView({{block:'nearest'}});}}
    if(e.key==='Enter'){{const f=list.querySelector('.sd-row.focus');if(f)goTo(f.dataset.anchor);}}
  }}
}});
window.addEventListener('resize',()=>{{if(drop.classList.contains('open'))positionDrop();}});
// Sidebar search filter
document.getElementById('sbSearch').addEventListener('input',function(){{
  const q=this.value.toLowerCase();
  document.querySelectorAll('.sidebar-method').forEach(a=>{{
    const match=!q||a.textContent.toLowerCase().includes(q);
    a.style.display=match?'':'none';
    if(match&&q){{const p=a.closest('.cat-methods');if(p){{p.classList.remove('collapsed');p.previousElementSibling?.classList.add('open');}}}}
  }});
}});
// Active sidebar highlight
const obs=new IntersectionObserver(entries=>{{
  entries.forEach(e=>{{
    if(e.isIntersecting){{
      const id=e.target.id;
      document.querySelectorAll('.sidebar-method').forEach(a=>a.classList.toggle('active',a.getAttribute('href')==='#'+id));
    }}
  }});
}},{{rootMargin:'-5% 0px -70% 0px'}});
document.querySelectorAll('.method-card').forEach(c=>obs.observe(c));
// Hash navigation
window.addEventListener('load',()=>{{
  if(location.hash){{
    const el=document.querySelector(location.hash);
    if(el){{
      if(el.classList.contains('method-card')&&!el.classList.contains('expanded')){{
        el.classList.add('expanded');el.querySelector('.method-body')?.classList.remove('collapsed-body');
      }}
      setTimeout(()=>el.scrollIntoView({{behavior:'smooth',block:'start'}}),250);
    }}
  }}
}});
</script>
</body>
</html>'''

HTML=HTML.replace('{SEARCH_INDEX_PLACEHOLDER}',_search_json)
(SITE_DIR/"index.html").write_text(HTML,encoding="utf-8")
(SITE_DIR/"CNAME").write_text(CUSTOM_DOMAIN,encoding="utf-8")

size_kb=len(HTML.encode())/1024
print(f"\n✅ Generated: {SITE_DIR/'index.html'}")
print(f"   Size: {size_kb:.1f} KB")
print(f"   Methods: {S['methods']}")
print(f"   Types: {S['types']}")
print(f"   Enums: {S['enums']}")
print(f"✅ CNAME: {CUSTOM_DOMAIN}")
print(f"\n🌐 Live at: https://{CUSTOM_DOMAIN}")
