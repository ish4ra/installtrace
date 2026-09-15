"""Portable snapshot validation, conservative diffing and offline reporting."""
import json
import html
import os
import tempfile
from collections import Counter
from pathlib import Path

CATEGORIES = ('files', 'registry', 'services', 'tasks')


def validate(s):
    if not isinstance(s, dict) or s.get('schema') != 1:
        raise ValueError('Unsupported snapshot format (expected schema 1).')
    for key in ('machine', 'scope', 'sections'):
        if not isinstance(s.get(key), dict):
            raise ValueError('Invalid snapshot: ' + key)
    for category in CATEGORIES:
        sec = s['sections'].get(category)
        if not isinstance(sec, dict) or not isinstance(sec.get('records'), dict):
            raise ValueError('Missing section: ' + category)
        if sec.get('status') not in ('complete', 'partial', 'unavailable'):
            raise ValueError('Invalid section status: ' + category)
        if not isinstance(sec.get('errors'), list):
            raise ValueError('Invalid errors: ' + category)
        if any(not isinstance(v, dict) for v in sec['records'].values()):
            raise ValueError('Invalid records: ' + category)
    return s


def load(path):
    if Path(path).stat().st_size > 200 * 1024 * 1024:
        raise ValueError('Snapshot exceeds the 200 MiB import limit.')
    return validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.installtrace-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def comparable(a, b):
    validate(a); validate(b)
    if a['machine'] != b['machine']:
        raise ValueError('Snapshots must come from the same machine, user and elevation level.')
    if a['scope'] != b['scope']:
        raise ValueError('Scan scopes differ. Use the same folders and hashing settings for every snapshot.')


def priority(category, key):
    if category in ('services', 'tasks') or '\\run' in key.lower() or '\\startup\\' in key.lower():
        return 'Review persistence'
    return 'Review change'


def compare(a, b):
    comparable(a, b)
    changes, warnings = [], []
    for cat in CATEGORIES:
        left, right = a['sections'][cat], b['sections'][cat]
        if left['status'] != 'complete' or right['status'] != 'complete':
            warnings.append(f'{cat}: incomplete coverage; one-sided records are uncertain, not confirmed additions/removals.')
        for key in sorted(left['records'].keys() | right['records'].keys()):
            old, new = left['records'].get(key), right['records'].get(key)
            if old == new:
                continue
            if old is None:
                kind = 'added' if left['status'] == 'complete' else 'uncertain'
            elif new is None:
                kind = 'removed' if right['status'] == 'complete' else 'uncertain'
            else:
                kind = 'modified'
            changes.append({'category': cat, 'key': key, 'kind': kind,
                            'priority': priority(cat, key), 'before': old, 'after': new})
    return {'schema': 1, 'mode': 'comparison', 'before': a.get('created'),
            'after': b.get('created'), 'warnings': warnings, 'changes': changes}


def leftovers(baseline, installed, uninstalled):
    comparable(baseline, uninstalled)
    initial = compare(baseline, installed)
    final = compare(baseline, uninstalled)
    tracked = {(c['category'], c['key']) for c in initial['changes']}
    final['changes'] = [c for c in final['changes'] if (c['category'], c['key']) in tracked]
    final['mode'] = 'leftovers'
    final['warnings'] = list(dict.fromkeys(initial['warnings'] + final['warnings']))
    final['warnings'].append('Candidates only: changes may be unrelated to the installer. No automatic cleanup is performed.')
    return final


def report_html(result):
    esc = lambda v: html.escape(str(v), quote=True)
    counts = Counter(c['kind'] for c in result['changes'])
    cards = ''.join(f'<div class="card"><strong>{counts[k]}</strong>{k.title()}</div>' for k in ('added','modified','removed','uncertain'))
    rows = []
    for c in result['changes']:
        old = esc(json.dumps(c['before'], ensure_ascii=False, indent=2))
        new = esc(json.dumps(c['after'], ensure_ascii=False, indent=2))
        rows.append(f'<details><summary><b>{esc(c["kind"].upper())}</b> · {esc(c["category"])} · {esc(c["key"])}</summary><p>{esc(c["priority"])}</p><div class="diff"><section><h3>Before</h3><pre>{old}</pre></section><section><h3>After</h3><pre>{new}</pre></section></div></details>')
    warnings = ''.join(f'<li>{esc(w)}</li>' for w in result['warnings'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>InstallTrace report</title><style>
body{{background:#0c1420;color:#dce7f4;font:15px system-ui;margin:0;padding:5vw;line-height:1.6}}main{{max-width:1200px;margin:auto}}h1{{font-size:42px;margin:0}}.eyebrow,b{{color:#69e4bd}}.cards,.diff{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.diff{{grid-template-columns:1fr 1fr}}.card,details{{background:#152232;border:1px solid #2b3b50;border-radius:12px;padding:20px;margin:14px 0}}strong{{display:block;font-size:32px}}summary{{cursor:pointer;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}p,li{{color:#aabbd0}}@media(max-width:650px){{.cards,.diff{{grid-template-columns:1fr}}}}</style><main><div class="eyebrow">INSTALLTRACE / LOCAL EVIDENCE</div><h1>What changed?</h1><p>{esc(result['mode'].title())} · {esc(result['before'])} → {esc(result['after'])}</p><div class="cards">{cards}</div><p>Observed state differences, not proof of installer attribution or malware. Reports may contain private paths and command arguments. Review before sharing.</p><ul>{warnings}</ul>{''.join(rows) or '<p>No observed differences.</p>'}</main></html>'''
