# -*- coding: utf-8 -*-
"""Build the weekly review: pick focus papers per topic and generate CN reviews.

Writes docs/data/review.json with:
  { generated_at, window_hours, topics: [ {key, title, trends [..], deep [..] } ] }

Focus selection: a transparent heuristic (title signals + recency), then the
LLM filters/ranks within the candidate set so the picks are defensible.
"""
import json
import os
from datetime import datetime, timezone

import summarize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')

SIGNALS = ["benchmark", "bench", "framework", "theory", "theoretical", "review",
           "survey", "we prove", "we introduce", "state-of-the-art", "sota",
           "first", "novel", "breakthrough", "unified", "general", "scalable"]


def pick_focus(papers, n):
    def score(p):
        t = (p['title'] + ' ' + p['abstract'][:400]).lower()
        s = sum(1 for k in SIGNALS if k in t)
        return s
    ranked = sorted(papers, key=score, reverse=True)
    return ranked[:n]


def topic_trends(key, papers, cfg):
    titles = "\n".join("- " + p['title'] for p in papers[:120])
    prompt = ("下面是 arXiv 方向“%s”本周的论文标题。用简体中文写 4-6 条要点，"
              "总结本周总体态势与主要趋势（每条以“- ”开头，不要标题）。\n\n%s"
              % (key, titles))
    return summarize.chat([{'role': 'user', 'content': prompt}], cfg['llm']).strip()


def main():
    cfg = summarize.get_config()
    n_deep = cfg.get('deep_read_count', 12)
    out = {'generated_at': datetime.now(timezone.utc).isoformat(),
           'window_hours': cfg.get('window_hours', 168), 'topics': []}
    for topic in cfg.get('topics', []):
        key = topic['key']
        path = os.path.join(DATA, '%s.json' % key)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        papers = data['papers']
        per = max(4, n_deep // max(1, len(cfg.get('topics', []))))
        focus = pick_focus(papers, per)
        print('[%s] generating trends + %d deep reviews' % (key, len(focus)))
        try:
            trends = topic_trends(key, papers, cfg)
        except Exception as ex:
            trends = '(趋势生成失败：%s)' % ex
        deep = []
        for p in focus:
            try:
                abs_cn, comment = summarize.deep_review(p, cfg['llm'])
            except Exception as ex:
                abs_cn = p.get('abs_cn', '')
                comment = '(点评生成失败：%s)' % ex
            deep.append({
                'arxiv_id': p['arxiv_id'],
                'title': p['title'],
                'title_cn': p.get('title_cn', ''),
                'authors': p['authors'][:6],
                'abs_url': p['abs_url'],
                'pdf_url': p['pdf_url'],
                'abs_cn': abs_cn,
                'comment': comment,
            })
        out['topics'].append({'key': key, 'title': topic.get('title', key),
                              'trends': trends, 'deep': deep})
        json.dump(out, open(os.path.join(DATA, 'review.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    print('review written')


if __name__ == '__main__':
    main()
