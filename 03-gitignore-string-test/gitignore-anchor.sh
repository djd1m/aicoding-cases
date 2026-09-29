#!/usr/bin/env bash
# Тест, который проверяет СТРОКУ в .gitignore, против теста, который спрашивает git.
# Запуск: bash gitignore-anchor.sh   (нужен только git; работает во временном каталоге и удаляет его)
set -u
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T" && git init -q .
mkdir -p .dz packages/mypkg/.dz

string_test() {   # «защита есть»: строка на месте
  grep -qxF '.dz/usage.jsonl' .gitignore && echo "  строковый тест: ЗЕЛЁНЫЙ" || echo "  строковый тест: КРАСНЫЙ"
}
git_test() {      # «защита работает»: git подтверждает, что РЕАЛЬНО записанный файл игнорируется
  local path=$1
  git check-ignore -q "$path" && echo "  тест через git ($path): ЗЕЛЁНЫЙ" || echo "  тест через git ($path): КРАСНЫЙ"
}
leak() { git status --porcelain --untracked-files=all | grep -c 'usage.jsonl' ; }

echo "1) .gitignore содержит '.dz/usage.jsonl'; приложение пишет журнал в корень"
printf '.dz/usage.jsonl\n' > .gitignore
echo '{"cmd":"publish"}' > .dz/usage.jsonl
string_test; git_test .dz/usage.jsonl; echo "  файлов журнала видно git: $(leak)"

echo "2) то же правило; приложение пишет журнал во вложенный пакет (так было у нас)"
echo '{"cmd":"publish"}' > packages/mypkg/.dz/usage.jsonl
string_test; git_test packages/mypkg/.dz/usage.jsonl; echo "  файлов журнала видно git: $(leak)"

echo "3) защиту удалили: строки в .gitignore нет"
: > .gitignore
string_test; git_test packages/mypkg/.dz/usage.jsonl; echo "  файлов журнала видно git: $(leak)"

echo "4) правило без привязки к корню: '**/.dz/usage.jsonl'"
printf '**/.dz/usage.jsonl\n' > .gitignore
string_test; git_test .dz/usage.jsonl; git_test packages/mypkg/.dz/usage.jsonl; echo "  файлов журнала видно git: $(leak)"
