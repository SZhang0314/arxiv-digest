# -*- coding: utf-8 -*-
"""Render the static site into docs/.

Pages:
  docs/index.html          — overview + links
  docs/review.html         — weekly review (trends + deep reads)
  docs/topic-<key>.html    — full bilingual list per topic
History snapshot copied to docs/archive/<date>/.
"""
import json
import os
import html
from datetime import datetime, timezone

import summarize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
DATA = os.path.join(DOCS, 'data')

CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--card:#161b22;--bd:#30363d;--acc:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.6}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:900px;margin:0 auto;padding:24px}
header{border-bottom:1px solid var(--bd);padding:20px 0;margin-bottom:24px}
h1{font-size:1.6rem;margin:0 0 6px}.mut{color:var(--mut);font-size:.9rem}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:18px;margin:14px 0}
.card h3{margin:0 0 6px;font-size:1.05rem}
.tag{display:inline-block;background:#21262d;border:1px solid var(--bd);color:var(--mut);
font-size:.75rem;padding:1px 7px;border-radius:20px;margin-right:6px}
.en{color:var(--mut);font-size:.85rem;font-style:italic}
.abs{font-size:.95rem}.nav a{margin-right:16px}
.pager{display:flex;gap:8px;margin:20px 0;flex-wrap:wrap}
.pager a{padding:4px 10px;border:1px solid var(--bd);border-radius:6px}
.trends{white-space:pre-wrap}
footer{border-top:1px solid var(--bd);margin-top:40px;padding:20px 0;color:var(--mut);font-size:.85rem}
"""


def page(title, body, nav=True):
    navhtml = ('<div class="nav"><a href="index.html">首页</a>'
               '<a href="review.html">本周综述</a></div>') if nav else ''
    return """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title><style>%s</style></head><body><div class="wrap">
<header><h1>%s</h1>%s</header>%s
<footer>自动生成 · arXiv Weekly Digest · 数据来自 arXiv（内容版权归原作者）</footer>
</div></body></html>""" % (html.escape(title), CSS, html.escape(title), navhtml, body)


def esc(s):
    return html.escape(s or '')


def render_index(cfg, index):
    cards = []
    if os.path.exists(os.path.join(DATA, 'review.json')):
        cards.append('<div class="card"><h3><a href="review.html">'
                     '📄 本周综述（趋势 + 深读）</a></h3></div>')
    for t in index['topics']:
        cards.append('<div class="card"><h3><a href="topic-%s.html">%s</a></h3>'
                     '<div class="mut">%d 篇 · 中英对照清单</div></div>'
                     % (t['key'], esc(t['title']), t['total']))
    body = ('<p class="mut">窗口：最近 %d 小时 ｜ 生成：%s</p>%s'
            % (index['window_hours'], index['generated_at'][:19], ''.join(cards)))
    return page(cfg.get('site_title', 'arXiv Weekly Digest'), body)


def render_topic(cfg, key, title, papers, page_size):
    parts = []
    for p in papers:
        tags = '<span class="tag">%s</span>' % esc(p['primary_category'])
        cn_title = esc(p.get('title_cn') or p['title'])
        en_title = ('<div class="en">%s</div>' % esc(p['title'])) if p.get('title_cn') else ''
        abs_cn = ('<div class="abs">%s</div>' % esc(p['abs_cn'])) if p.get('abs_cn') else ''
        links = ('<div class="mut" style="margin-top:6px">%s'
                 '<a href="%s">arXiv</a> · <a href="%s">PDF</a></div>'
                 % (tags, p['abs_url'], p['pdf_url']))
        parts.append('<div class="card"><h3>%s</h3>%s%s%s</div>'
                     % (cn_title, en_title, abs_cn, links))
    body = ('<p class="mut">%d 篇</p>' % len(papers)) + ''.join(parts)
    return page('%s — %s' % (cfg.get('site_title', ''), title), body)


def render_review(cfg, review):
    parts = []
    for t in review['topics']:
        parts.append('<h2>%s</h2>' % esc(t['title']))
        if t.get('trends'):
            parts.append('<div class="card"><h3>本周态势</h3>'
                         '<div class="trends">%s</div></div>' % esc(t['trends']))
        for d in t['deep']:
            parts.append(
                '<div class="card"><h3>%s</h3><div class="en">%s</div>'
                '<div class="abs" style="margin-top:8px">%s</div>'
                '<div class="abs" style="margin-top:8px"><b>点评：</b>%s</div>'
                '<div class="mut" style="margin-top:6px">%s · '
                '<a href="%s">arXiv</a> · <a href="%s">PDF</a></div></div>'
                % (esc(d.get('title_cn') or d['title']), esc(d['title']),
                   esc(d['abs_cn']), esc(d['comment']),
                   esc(', '.join(d['authors'])), d['abs_url'], d['pdf_url']))
    body = '<p class="mut">窗口：最近 %d 小时</p>' % review['window_hours'] + ''.join(parts)
    return page('%s — 本周综述' % cfg.get('site_title', ''), body)


def main():
    cfg = summarize.get_config()
    page_size = cfg.get('page_size', 50)
    index = json.load(open(os.path.join(DATA, 'index.json'), encoding='utf-8'))

    open(os.path.join(DOCS, 'index.html'), 'w', encoding='utf-8').write(
        render_index(cfg, index))
    for t in index['topics']:
        data = json.load(open(os.path.join(DATA, '%s.json' % t['key']), encoding='utf-8'))
        open(os.path.join(DOCS, 'topic-%s.html' % t['key']), 'w', encoding='utf-8').write(
            render_topic(cfg, t['key'], t['title'], data['papers'], page_size))
    rp = os.path.join(DATA, 'review.json')
    if os.path.exists(rp):
        review = json.load(open(rp, encoding='utf-8'))
        open(os.path.join(DOCS, 'review.html'), 'w', encoding='utf-8').write(
            render_review(cfg, review))

    # archive snapshot
    date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    arch = os.path.join(DOCS, 'archive', date)
    os.makedirs(arch, exist_ok=True)
    for f in os.listdir(DATA):
        if f.endswith('.json'):
            open(os.path.join(arch, f), 'w', encoding='utf-8').write(
                open(os.path.join(DATA, f), encoding='utf-8').read())
    print('site built into docs/')


if __name__ == '__main__':
    main()
