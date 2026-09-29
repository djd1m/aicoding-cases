#!/usr/bin/env python3
"""Что меняли отправки (push), за которые CI заплатил: код или только документы.

Использование (из рабочей копии того же репозитория, после ci-cost.py):
  python3 push-kinds.py --data ci-cost-data --since 2026-09-19 [--docs 'docs/,features/,*.md'] [--tools 'scripts/,.github/,.claude/']

Для каждой отправки (event=push) с хотя бы одним заданием, получившим исполнение, берёт список файлов
`git diff --name-only <родитель> <коммит>` и относит отправку к одному классу:
  «только документы» — все файлы подходят под --docs;
  «инструменты» — не код, но есть файлы из --tools;
  «код» — всё остальное.
Стоимость отправки — сумма её оплачиваемых минут по прейскуранту (как в ci-cost.py).
Предел: отправка из нескольких коммитов оценивается по диффу от родителя последнего коммита; для точного
ответа по пачке нужен дифф от предыдущей отправленной вершины (--range-from-previous).
"""
import argparse, collections, datetime as dt, fnmatch, gzip, json, math, subprocess

PRICE = {'ubuntu': 0.006, 'windows': 0.010, 'macos': 0.062}
ap = argparse.ArgumentParser()
ap.add_argument('--data', default='ci-cost-data'); ap.add_argument('--since', required=True)
ap.add_argument('--docs', default='docs/,features/,*.md'); ap.add_argument('--tools', default='scripts/,.github/,.claude/')
ap.add_argument('--range-from-previous', action='store_true')
a = ap.parse_args()
ts = lambda x: dt.datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ')
runs = {r['id']: r for r in map(json.loads, gzip.open(f'{a.data}/runs.jsonl.gz', 'rt'))}
jobs = [json.loads(l) for l in gzip.open(f'{a.data}/jobs.jsonl.gz', 'rt')]
osof = lambda l: 'macos' if 'macos' in ' '.join(l or []).lower() else 'windows' if 'windows' in ' '.join(l or []).lower() else 'ubuntu'
cost, seen = collections.defaultdict(float), set()
for j in jobs:
    r = runs.get(j['run_id'])
    k = (j['run_id'], j['job'], j['attempt'], j['started_at'])
    if not r or r['event'] != 'push' or r['created_at'][:10] < a.since or k in seen or not j['runner'] or not j['started_at'] or not j['completed_at']:
        continue
    seen.add(k)
    sec = (ts(j['completed_at']) - ts(j['started_at'])).total_seconds()
    if sec > 0:
        cost[r['head_sha']] += math.ceil(sec / 60) * PRICE[osof(j['labels'])]
match = lambda f, pats: any(f.startswith(p) if p.endswith('/') else fnmatch.fnmatch(f.split('/')[-1], p) for p in pats)
DOCS, TOOLS = a.docs.split(','), a.tools.split(',')
order = sorted(cost, key=lambda s: min(r['created_at'] for r in runs.values() if r['head_sha'] == s))
res, prev, missing = collections.defaultdict(lambda: [0, 0.0]), None, 0
for sha in order:
    base = prev if (a.range_from_previous and prev) else f'{sha}^'
    p = subprocess.run(['git', 'diff', '--name-only', base, sha], capture_output=True, text=True)
    prev = sha
    if p.returncode != 0:
        missing += 1; continue
    files = [f for f in p.stdout.split('\n') if f]
    kind = 'только документы' if files and all(match(f, DOCS) for f in files) else \
           'инструменты' if files and all(match(f, DOCS) or match(f, TOOLS) for f in files) else 'код'
    res[kind][0] += 1; res[kind][1] += cost[sha]
print(f'отправок с оплаченными заданиями: {len(order)} (не найдено в git: {missing})')
for k in ('только документы', 'код', 'инструменты'):
    print(f'  {k:18} {res[k][0]:5} отправок  ${res[k][1]:8.2f}')
