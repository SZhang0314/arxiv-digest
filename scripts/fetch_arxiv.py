# -*- coding: utf-8 -*-
"""Fetch arXiv papers for all configured topics (weekly window).

Reads config.yml, fetches each preset's categories, dedupes, caps per topic,
writes docs/data/<topic>.json and a combined docs/data/index.json.
"""
import json
import os
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import summarize  # local module (same dir)

NS = {'a': 'http://www.w3.org/2005/Atom',
      'arxiv': 'http://arxiv.org/schemas/atom'}

PRESETS = {
    "physics": ["cond-mat.str-el", "cond-mat.stat-mech", "cond-mat.mtrl-sci",
                "cond-mat.supr-con", "quant-ph", "hep-th", "hep-ph",
                "astro-ph.CO", "astro-ph.HE", "physics.gen-ph"],
    "ai": ["cs.LG", "cs.AI", "cs.CL", "cs.CV", "cs.IT", "cs.ET", "cs.AR",
           "eess.SP", "eess.SY", "eess.IV"],
    "chem": ["physics.chem-ph", "cond-mat.soft", "cond-mat.mtrl-sci",
             "physics.atm-clus", "physics.comp-ph", "q-bio.BM"],
    "math": ["math.AG", "math.AP", "math.CO", "math.DS", "math.NT",
             "math.OC", "math.PR", "math-ph"],
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')


def fetch_category(cat, max_results=200, timeout=90):
    q = urllib.parse.quote("cat:%s" % cat)
    url = ("https://export.arxiv.org/api/query?search_query=%s"
           "&start=0&max_results=%d&sortBy=submittedDate&sortOrder=descending"
           % (q, max_results))
    for attempt in range(5):
        try:
            return ET.fromstring(urllib.request.urlopen(url, timeout=timeout).read())
        except Exception as ex:
            print("  retry %d %s: %s" % (attempt + 1, cat, ex))
            time.sleep(10)
    return None


def parse_entry(e, cat):
    def t(tag):
        node = e.find(tag, NS)
        return node.text.strip() if node is not None and node.text else ""
    aid = t('a:id').rsplit('/', 1)[-1]
    primary = e.find('arxiv:primary_category', NS)
    prim = primary.attrib.get('term', cat) if primary is not None else cat
    return {
        "arxiv_id": aid,
        "title": " ".join(t('a:title').split()),
        "abstract": " ".join(t('a:summary').split()),
        "authors": [a.find('a:name', NS).text for a in e.findall('a:author', NS)],
        "primary_category": prim,
        "published": t('a:published'),
        "updated": t('a:updated'),
        "abs_url": "https://arxiv.org/abs/%s" % aid,
        "pdf_url": "https://arxiv.org/pdf/%s" % aid,
    }


def fetch_topic(key, hours, cap):
    cats = PRESETS.get(key)
    if not cats:
        return []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    seen = {}
    for cat in cats:
        root = fetch_category(cat)
        if root is None:
            continue
        for e in root.findall('a:entry', NS):
            p = parse_entry(e, cat)
            try:
                dt = datetime.strptime(p["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if dt < cutoff:
                continue
            seen[p["arxiv_id"]] = p
        time.sleep(3)
    papers = sorted(seen.values(), key=lambda x: x["updated"], reverse=True)
    return papers[:cap]


def main():
    cfg = summarize.get_config()
    hours = cfg.get('window_hours', 168)
    cap = cfg.get('max_per_topic', 400)
    os.makedirs(DATA, exist_ok=True)
    index = {'generated_at': datetime.now(timezone.utc).isoformat(),
             'window_hours': hours, 'topics': []}
    for topic in cfg.get('topics', []):
        key = topic['key']
        print('fetching topic:', key)
        papers = fetch_topic(key, hours, cap)
        payload = {
            'key': key,
            'title': topic.get('title', key),
            'window_hours': hours,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'total': len(papers),
            'papers': papers,
        }
        json.dump(payload, open(os.path.join(DATA, '%s.json' % key), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        index['topics'].append({'key': key, 'title': topic.get('title', key),
                                'total': len(papers)})
        print('  %s: %d papers' % (key, len(papers)))
    json.dump(index, open(os.path.join(DATA, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('done; index written')


if __name__ == '__main__':
    main()
