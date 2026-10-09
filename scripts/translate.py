# -*- coding: utf-8 -*-
"""Translate all papers in docs/data/<topic>.json (adds title_cn / abs_cn).

Uses a thread pool (OpenAI-compatible client is IO-bound). Resumable: skips
papers that already have abs_cn. Writes back in place.
"""
import json
import os
import sys
import threading
import concurrent.futures as cf

import summarize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')
_lock = threading.Lock()


def translate_topic(key, cfg):
    path = os.path.join(DATA, '%s.json' % key)
    if not os.path.exists(path):
        print('skip missing', path)
        return
    data = json.load(open(path, encoding='utf-8'))
    papers = data['papers']
    todo = [p for p in papers if not p.get('abs_cn')]
    print('[%s] %d total, %d to translate' % (key, len(papers), len(todo)))

    def work(p):
        try:
            tc, ac = summarize.translate_paper(p['title'], p['abstract'], cfg['llm'])
            p['title_cn'] = tc
            p['abs_cn'] = ac
        except Exception as ex:
            p['title_cn'] = p.get('title_cn', '')
            p['abs_cn'] = p.get('abs_cn', '')
            with _lock:
                print('  ERR %s: %s' % (p['arxiv_id'], ex))
        return p

    conc = cfg['llm'].get('concurrency', 6)
    done = 0
    with cf.ThreadPoolExecutor(max_workers=conc) as ex:
        for _ in ex.map(work, todo):
            with _lock:
                done += 1
                if done % 20 == 0:
                    json.dump(data, open(path, 'w', encoding='utf-8'),
                              ensure_ascii=False, indent=1)
                    print('  %s: %d/%d' % (key, done, len(todo)))
    json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[%s] done' % key)


def main():
    cfg = summarize.get_config()
    keys = [t['key'] for t in cfg.get('topics', [])]
    if len(sys.argv) > 1:
        keys = [sys.argv[1]]
    for k in keys:
        translate_topic(k, cfg)


if __name__ == '__main__':
    main()
