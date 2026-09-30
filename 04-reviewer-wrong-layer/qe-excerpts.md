# Выдержки из отчётов проверки фич (приватный репозиторий), строки с разобранными находками

## temp-root-post-run-check (строки 10 отчёта 08_qe_report.md)
| F1 | HIGH | shared-root last user leaves `DZ_VITEST_TMP_ROOT_USERS` at 1 | REFUTED by measurement: `vitest.dz-debris.shared.ts:177` `delete process.env[RUN_ROOT_USERS_ENV]` (pre-existing); AC-5 asserts `usersAfter: null` and passes. The reviewer saw only the diff hunks. |

## verify-pack-sweep-respects-files (строки 9 отчёта 08_qe_report.md)
| F1 | HIGH | `README-old`/`LICENSE-extra` should be always-included per `README*` | REFUTED by measurement: `/usr/lib/node_modules/npm/node_modules/npm-packlist/lib/index.js:283-286` — `readme{,.*[^~$]}`, `copying{,.*[^~$]}`, `license{,.*[^~$]}`, `licence{,.*[^~$]}`: bare name or name.<ext>, tails `~`/`$` excluded; `README-old` is NOT shipped. Our regex was still off (no `copying`; `~`/`$` tails accepted) — FIXED and pinned on 8 names (AC + COPYING/README-old/LICENSE.md~/README./license.md$). Requirement wording corrected. |

## codex-hook-root-provenance (строки 38,43 отчёта 08_qe_report.md)
## Круг 2 — Codex (`chrp-r2.log`)
**Grade C** — HIGH «статическая проверка не может проходить: JSDoc содержит третье вхождение».
**ОПРОВЕРГНУТО ИЗМЕРЕНИЕМ** (05:38): тест проходит, а `generateCodexHelpers()` даёт ровно 2 вхождения
в обоих хелперах — ревьюер смотрел на комментарий в ИСХОДНИКЕ TypeScript, тогда как проверка считает
по ПОРОЖДАЕМОМУ тексту. Воспроизводители в манифесте. MEDIUM «транскрипт захвата не мог быть
буквальным выводом показанного скрипта» — принято, это дефект аудиторской записи; LOW ×2 (счёт тестов

## no-match-means-no-results (строки 29,31 отчёта 08_qe_report.md)
**CONFIRMED as behaviour, REFUTED as a defect of this change.** Measured on BOTH trees: `x` returned
both records before and after. It is the tokenizer's one-character rule, and it predates the feature.
`xx` — a usable term matching nothing — went from both records to none, which is the feature working.

## no-match-means-no-results, таблица находок того же семейства, строка 39
| 1 | **critical** | parity was tested only with FTS5 DISABLED, so it says nothing about the shipping configuration; FTS5's implicit AND was predicted to diverge on the weak-match row | **gap CONFIRMED, prediction REFUTED by running** — 0 divergences over 8 rows with FTS5 on | a second parity test now runs the whole table in the shipping configuration |
