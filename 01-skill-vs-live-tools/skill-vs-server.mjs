#!/usr/bin/env node
// Сверка: какие инструменты MCP-сервера упоминает SKILL.md и какие из них сервер реально знает.
// Использование: node skill-vs-server.mjs <SKILL.md> -- <команда сервера> [аргументы...]
// Скрипт шлёт серверу по stdio два запроса JSON-RPC (initialize, tools/list) и печатает пересечение.
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';

const sep = process.argv.indexOf('--');
if (sep < 3 || sep === process.argv.length - 1) {
  console.error('usage: node skill-vs-server.mjs <SKILL.md> -- <server command> [args...]');
  process.exit(2);
}
const skillPath = process.argv[2];
const [cmd, ...args] = process.argv.slice(sep + 1);
const PREFIX = process.env.TOOL_PREFIX || ''; // например agentdb_ — если имена в документе несут префикс

const doc = readFileSync(skillPath, 'utf8');
// имя инструмента = идентификатор в обратных кавычках или в ячейке таблицы: snake_case минимум из двух частей
const documented = new Set();
for (const m of doc.matchAll(/`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`/g)) documented.add(m[1]);
for (const m of doc.matchAll(/\|\s*([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\s*\|/g)) documented.add(m[1]);
const docNames = [...documented].filter((n) => !PREFIX || n.startsWith(PREFIX)).sort();

const child = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'inherit'] });
let buf = '';
const pending = new Map();
child.stdout.on('data', (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line) continue;
    let msg; try { msg = JSON.parse(line); } catch { continue; }
    if (msg.id !== undefined && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  }
});
const rpc = (id, method, params) => new Promise((res) => {
  pending.set(id, res);
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
});
const timer = setTimeout(() => { console.error('таймаут: сервер не ответил за 300 с'); child.kill(); process.exit(3); }, 300000);

const init = await rpc(1, 'initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'skill-vs-server', version: '1' } });
child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
if (init.error || !init.result) { console.error('initialize: ошибка сервера', JSON.stringify(init.error || init)); child.kill(); process.exit(4); }
// tools/list может отдаваться страницами (nextCursor) — читаем все страницы
const live = new Set();
let cursor, id = 2, pages = 0;
do {
  const list = await rpc(id++, 'tools/list', cursor ? { cursor } : {});
  if (list.error || !Array.isArray(list.result?.tools)) { console.error('tools/list: ошибка сервера', JSON.stringify(list.error || list)); child.kill(); process.exit(4); }
  for (const t of list.result.tools) live.add(t.name);
  cursor = list.result.nextCursor; pages++;
} while (cursor && pages < 100);
clearTimeout(timer);
child.kill();
if (cursor) { console.error('tools/list: больше 100 страниц — список не дочитан, сверка не выполнена'); process.exit(5); }

const exist = docNames.filter((n) => live.has(n));
const missing = docNames.filter((n) => !live.has(n));
const server = init.result?.serverInfo || {};
console.log(`server: ${server.name || '?'} ${server.version || '?'}`);
console.log(`documented: ${docNames.length}   live: ${live.size}   (tools/list pages: ${pages})`);
console.log(`documented names that exist:        ${exist.length}  ${exist.join(', ')}`);
console.log(`documented names that do NOT exist: ${missing.length}`);
for (const n of missing) console.log(`  - ${n}`);
