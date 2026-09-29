#!/usr/bin/env python3
"""Сколько на самом деле проверял ваш CI и сколько он стоит по прейскуранту.

Использование:
  python3 ci-cost.py OWNER/REPO --since 2026-07-01 --until 2026-09-27 [--out DIR] [--validate 200]

Что делает:
  1. Через `gh api` выгружает все прогоны GitHub Actions за период (по дням, постранично).
  2. Прогон «без машины» — упавший (conclusion=failure) не позже чем через 15 секунд после старта. Задания таких
     прогонов не запрашиваются (их тысячи), но правило проверяется: --validate N запрашивает задания у N таких
     прогонов и печатает, у скольких было назначено исполнение (runner). Если не ноль — правило для вашего
     репозитория неверно, и числа «без машины» верить нельзя.
  3. Для остальных прогонов запрашивает задания; оплачиваемые минуты = длительность задания, округлённая вверх.
  4. Печатает по месяцам: прогоны, «без машины», минуты по ОС, стоимость по прейскуранту.

Пределы:
  - Это оценка по прейскуранту до вычета бесплатной квоты, а не счёт. Счёт — только в Settings → Billing.
  - Цены ниже — прейскурант GitHub для стандартных исполнителей, прочитан 27.09.2026; проверьте актуальные.
  - Токен берётся из `gh auth`; скрипт его не печатает и не сохраняет. Нужен доступ на чтение Actions.
"""
import argparse, collections, datetime as dt, gzip, json, math, os, random, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

PRICE = {'ubuntu': 0.006, 'windows': 0.010, 'macos': 0.062}  # $ за минуту, 2 ядра
BLOCKED_SECONDS = 15

ap = argparse.ArgumentParser()
ap.add_argument('repo'); ap.add_argument('--since', required=True); ap.add_argument('--until', required=True)
ap.add_argument('--out', default='ci-cost-data'); ap.add_argument('--validate', type=int, default=200)
ap.add_argument('--workers', type=int, default=6)
ap.add_argument('--offline', action='store_true', help='не ходить в API: считать по runs.jsonl.gz и jobs.jsonl.gz из --out')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
env = dict(os.environ); env.pop('GITHUB_TOKEN', None)

def get(path):
    for attempt in range(6):
        r = subprocess.run(['gh', 'api', path], env=env, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        time.sleep(15 * (attempt + 1))
    sys.exit(f'gh api не ответил: {path}: {r.stderr.strip()[:200]}')

ts = lambda x: dt.datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ')
blocked = lambda r: r['conclusion'] == 'failure' and r.get('run_started_at') and r.get('updated_at') and \
    (ts(r['updated_at']) - ts(r['run_started_at'])).total_seconds() <= BLOCKED_SECONDS

# 1. прогоны
runs = []
if a.offline:
    runs = [json.loads(l) for l in gzip.open(os.path.join(a.out, 'runs.jsonl.gz'), 'rt')]
    runs = [r for r in runs if a.since <= r['created_at'][:10] <= a.until]
day, end = dt.date.fromisoformat(a.since), dt.date.fromisoformat(a.until)
while not a.offline and day <= end:
    page = 1
    while True:
        d = get(f'repos/{a.repo}/actions/runs?created={day}&per_page=100&page={page}')
        runs += [{k: r.get(k) for k in ('id', 'name', 'event', 'conclusion', 'created_at', 'run_started_at', 'updated_at', 'head_sha')}
                 for r in d['workflow_runs']]
        if len(d['workflow_runs']) < 100:
            break
        page += 1
    day += dt.timedelta(days=1)
if not a.offline:
    with gzip.open(os.path.join(a.out, 'runs.jsonl.gz'), 'wt') as f:
        for r in runs: f.write(json.dumps(r) + '\n')
print(f'прогонов: {len(runs)}', file=sys.stderr)

def jobs_of(r):
    out, page = [], 1
    while True:
        d = get(f'repos/{a.repo}/actions/runs/{r["id"]}/jobs?filter=all&per_page=100&page={page}')
        out += [{'run_id': r['id'], 'workflow': r['name'], 'created_at': r['created_at'], 'labels': j.get('labels'),
                 'started_at': j.get('started_at'), 'completed_at': j.get('completed_at'), 'runner': j.get('runner_name'),
                 'job': j['name'], 'attempt': j.get('run_attempt')} for j in d['jobs']]
        if len(d['jobs']) < 100:
            return out
        page += 1

# 2. проверка правила «без машины» на выборке
B = [r for r in runs if blocked(r)]
if not a.offline:
    sample = random.Random(20260927).sample(B, min(a.validate, len(B)))
    with ThreadPoolExecutor(a.workers) as ex:
        with_runner = sum(1 for js in ex.map(jobs_of, sample) if any(j['runner'] for j in js))
    print(f'проверка правила «без машины»: из {len(sample)} таких прогонов исполнение было назначено у {with_runner}')

# 3. задания остальных прогонов
rest = [r for r in runs if not blocked(r)]
if a.offline:
    ids = {r['id'] for r in runs}
    jobs = [j for j in map(json.loads, gzip.open(os.path.join(a.out, 'jobs.jsonl.gz'), 'rt')) if j['run_id'] in ids]
else:
    with ThreadPoolExecutor(a.workers) as ex, gzip.open(os.path.join(a.out, 'jobs.jsonl.gz'), 'wt') as f:
        jobs = [j for js in ex.map(jobs_of, rest) for j in js]
        for j in jobs: f.write(json.dumps(j) + '\n')

# 4. расчёт
def osof(labels):
    l = ' '.join(labels or []).lower()
    return 'macos' if 'macos' in l else 'windows' if 'windows' in l else 'ubuntu'
seen, M = set(), collections.defaultdict(collections.Counter)
for j in jobs:
    k = (j['run_id'], j['job'], j['attempt'], j['started_at'])
    if k in seen or not j['runner'] or not j['started_at'] or not j['completed_at']:
        continue
    seen.add(k)
    sec = (ts(j['completed_at']) - ts(j['started_at'])).total_seconds()
    if sec > 0:
        M[j['created_at'][:7]][osof(j['labels'])] += math.ceil(sec / 60)
# прогон, названный путём к файлу (.github/workflows/…), — конвейер, чей файл GitHub не смог разобрать
badfile = lambda r: (r.get('name') or '').startswith('.github/')
print(f'\n{"месяц":8} {"прогонов":>9} {"без машины":>11} {"из них файл не разобран":>24} {"минут":>7}  по прейскуранту  (минуты по ОС)')
for mo in sorted({r['created_at'][:7] for r in runs}):
    rn = [r for r in runs if r['created_at'][:7] == mo]; c = M[mo]
    usd = sum(c[o] * PRICE[o] for o in c)
    print(f'{mo:8} {len(rn):9} {sum(1 for r in rn if blocked(r)):11} {sum(1 for r in rn if blocked(r) and badfile(r)):24} {sum(c.values()):7}  ${usd:9.2f}        {dict(c)}')
bf = [r for r in runs if blocked(r) and badfile(r)]
print('\nбыстрые отказы с именем-путём, по точному имени (первый и последний прогон):')
for name in sorted({r['name'] for r in bf}):
    g = sorted(r['created_at'] for r in bf if r['name'] == name)
    print(f'  {name}: {len(g)}  с {g[0]} по {g[-1]}')
allp = [r for r in runs if badfile(r)]
print(f'все прогоны с именем-путём (любой исход): {len(allp)}; из них быстрые отказы: {len(bf)}; исходы: {dict(collections.Counter(r["conclusion"] for r in allp))}')
print('\nпо дням, доля прогонов без машины (всего / из них файл не разобран):')
for d in sorted({r['created_at'][:10] for r in runs}):
    rn = [r for r in runs if r['created_at'][:10] == d]; k = sum(1 for r in rn if blocked(r)); f = sum(1 for r in rn if blocked(r) and badfile(r))
    print(f'  {d}  {len(rn):5} прогонов  без машины {k:5} ({k/len(rn):4.0%})  файл не разобран {f:4}')
