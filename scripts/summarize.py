# -*- coding: utf-8 -*-
"""OpenAI-compatible LLM client: translation + summarization.

Configurable endpoint (base_url / model / api key). Used by the pipeline and
by the web build. The API key is read from the environment (LLM_API_KEY) so it
never lands in the repo.

CLI:
    python summarize.py selftest            # quick connectivity check
"""
import json
import os
import re
import sys
import time
import urllib.request


def get_config(config_path=None):
    config_path = config_path or os.environ.get('DIGEST_CONFIG', 'config.yml')
    cfg = {
        'llm': {
            'base_url': os.environ.get('LLM_BASE_URL', 'https://api.llm.ustc.edu.cn/v1'),
            'model': os.environ.get('LLM_MODEL', 'deepseek-flash'),
            'temperature': 0.2,
            'max_tokens': 4000,
            'concurrency': 6,
        }
    }
    if os.path.exists(config_path):
        try:
            import yaml
            loaded = yaml.safe_load(open(config_path, encoding='utf-8')) or {}
            if 'llm' in loaded:
                cfg['llm'].update(loaded['llm'])
            for k in ('site_title', 'topics', 'window_hours', 'max_per_topic',
                      'deep_read_count', 'page_size'):
                if k in loaded:
                    cfg[k] = loaded[k]
        except Exception as ex:
            sys.stderr.write('config load warning: %s\n' % ex)
    return cfg


def _api_key():
    key = os.environ.get('LLM_API_KEY')
    if key:
        return key
    auth = os.path.expanduser('~/.local/share/opencode/auth.json')
    if os.path.exists(auth):
        try:
            data = json.load(open(auth, encoding='utf-8'))
            for v in data.values():
                if isinstance(v, dict) and v.get('key'):
                    return v['key']
        except Exception:
            pass
    if os.path.exists('keys.txt'):
        for line in open('keys.txt', encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    return None


def chat(messages, llm_cfg=None, retries=6, timeout=240):
    """OpenAI-compatible /chat/completions call."""
    cfg = llm_cfg or get_config()['llm']
    base = cfg['base_url'].rstrip('/')
    url = base + '/chat/completions'
    key = _api_key()
    if not key:
        raise RuntimeError('No LLM API key (set LLM_API_KEY or keys.txt)')
    body = json.dumps({
        'model': cfg['model'],
        'messages': messages,
        'temperature': cfg.get('temperature', 0.2),
        'max_tokens': cfg.get('max_tokens', 4000),
    }).encode('utf-8')
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + key,
        })
        try:
            resp = urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8')
            return json.loads(resp)['choices'][0]['message']['content']
        except Exception as ex:
            last = ex
            time.sleep(min(60, 5 * (attempt + 1)))
    raise last


def fix_escapes(s):
    """Repair invalid JSON backslash escapes (e.g. LaTeX \\times)."""
    out = []
    i = 0
    n = len(s)
    valid = set('"\\/bfnrtu')
    while i < n:
        c = s[i]
        if c == '\\':
            nxt = s[i + 1] if i + 1 < n else ''
            if nxt in valid:
                if nxt == 'u':
                    hexs = s[i + 2:i + 6]
                    if len(hexs) == 4 and all(h in '0123456789abcdefABCDEF' for h in hexs):
                        out.append(s[i:i + 6])
                        i += 6
                        continue
                    out.append('\\\\')
                    i += 1
                    continue
                out.append(s[i:i + 2])
                i += 2
                continue
            out.append('\\\\')
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def parse_json_obj(text):
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        raise ValueError('no JSON object in response')
    return json.loads(fix_escapes(m.group(0)))


def parse_json_array(text):
    m = re.search(r'\[.*\]', text, re.S)
    if not m:
        raise ValueError('no JSON array in response')
    return json.loads(fix_escapes(m.group(0)))


TRANSLATE_SYS = (
    "你是专业的学术翻译。把给定的论文标题和摘要翻译成准确、通顺的简体中文。"
    "专业术语、人名、arXiv 编号、模型名、化学式保留原文。"
    "数学符号请使用纯文本（例如 alpha、<=、->、H2O），不要使用反斜杠 LaTeX 命令。"
)


def translate_paper(title, abstract, llm_cfg=None):
    prompt = (TRANSLATE_SYS + "\n严格输出 JSON 对象："
              "{\"title_cn\": \"...\", \"abs_cn\": \"...\"}，无多余文字。\n\n"
              "TITLE: %s\nABS: %s" % (title, abstract))
    txt = chat([{'role': 'user', 'content': prompt}], llm_cfg)
    obj = parse_json_obj(txt)
    return obj.get('title_cn', ''), obj.get('abs_cn', '')


def summarize_batch(papers, llm_cfg=None):
    """One-line CN summaries for a batch of papers (for the review/overview page)."""
    items = "\n".join("[%d] %s" % (i, p['title']) for i, p in enumerate(papers))
    prompt = ("用一句简体中文概括下列每篇论文的核心贡献（不超过 40 字）。"
              "严格输出 JSON 数组：[{\"i\":序号,\"one\":\"...\"}]，无多余文字。\n\n" + items)
    txt = chat([{'role': 'user', 'content': prompt}], llm_cfg)
    arr = parse_json_array(txt)
    out = {}
    for it in arr:
        out[int(it['i'])] = it.get('one', '')
    return out


def deep_review(paper, llm_cfg=None):
    """Generate a structured CN review for a focus paper."""
    prompt = (
        "你是领域专家。为下面这篇论文写一段简明的中文解读，包含两部分："
        "(1) 摘要的忠实中译；(2) 一段点评，说明其方法论价值、适合的读者、"
        "以及可能与用户方向（物理/凝聚态/AI/化学）的关联。"
        "严格输出 JSON 对象：{\"abs_cn\":\"...\",\"comment\":\"...\"}，无多余文字。\n\n"
        "TITLE: %s\nAUTHORS: %s\nABS: %s" % (
            paper['title'], ', '.join(paper['authors'][:6]), paper['abstract']))
    txt = chat([{'role': 'user', 'content': prompt}], llm_cfg)
    obj = parse_json_obj(txt)
    return obj.get('abs_cn', ''), obj.get('comment', '')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        print('base_url:', get_config()['llm']['base_url'])
        print('model:', get_config()['llm']['model'])
        print('key present:', bool(_api_key()))
        t, a = translate_paper('World Models in Physics',
                               'We introduce a benchmark for physical consistency in video world models.')
        print('title_cn:', t)
        print('abs_cn:', a[:120])
