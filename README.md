# KAGI Runtime

`KAGI_design.md` と `KAGI_core.lean` にある最小核を、そのまま実行できる core runtime です。

## CapIR v0

現在の lowering target は `CapIR v0` です。

- 定義: `src/kagi/ir.py`
- `frontend.py` は source を `ProgramIR` に lower する
- `runtime.py` は `ProgramIR` を実行するだけ
- `cli.py` は I/O と表示だけを持つ
- `assert_export` は IR 命令ではなく bootstrap 側の meta assertion

この境界を self-hosting 前の固定足場として扱います。

## Diagnostics

CLI では `--json` を受け付け、失敗時は構造化診断を返します。

- `phase`
- `code`
- `message`
- `line`
- `column`
- `snippet`

## Subset Language

self-hosting 用の最小 subset を追加しています。

- `fn`
- `let`
- `if / else`
- `return`
- `call`
- `string / int / bool`

利用できる builtin:

- `eq`
- `concat`
- `starts_with`
- `ends_with`
- `quote`
- `line_count`
- `line_at`
- `before_substring`
- `after_substring`
- `is_identifier`
- `extract_quoted`
- `trim`

## Self-Hosted Front Half

`examples/selfhost_frontend.ks` は KAGI subset で書いた tiny frontend です。
いまは `print "..."` 文を受け付ける極小言語を対象にしています。複数行の `print` 文、`print concat("a","b")` のような最小式、`let x = ...` と `print x`、さらに `eq(...)` と `if(cond, then, else)`、`if cond { ... } else { ... }`、`fn name() { ... }` / `fn name(x) { ... }` と `call name()` / `call name("...")` を処理できます。

現時点では parser の一部を self-hosted 側へ寄せ始めており、単純な `print "..."` 1 行ケース、`let x = "..."` / `print x` の 2 行ケース、`fn name(x) { print concat(x, "...") }` + `call name("...")` の固定形は `examples/selfhost_frontend.ks` 自身が判定して AST を返します。より広い構文はまだ Python seed builtin に fallback します。

Python 側には `src/kagi/selfhost.py` があり、self-hosted parser の返す AST JSON を typed bridge object に変換します。
さらに bridge は `TinyProgram -> CapIR fragment` の lowering を持ち、`src/kagi/capir_runtime.py` が tiny fragment を実行します。

役割は 3 つに分けています。

- `parse(source)`:
  - tiny source から最小 program AST JSON を作る
- `check(source)`:
  - program AST を bridge で受けたうえで tiny source を受理できるか判定する
- `lower(source)`:
  - program AST を bridge で受けて最小 JSON artifact を作る
- `compile(source)`:
  - 現在は `lower(source)` の alias

`selfhost-run` は compile の返す artifact をそのまま実行します。以前のように AST から横で再 lower するのではなく、compiler output を主経路として扱います。

```bash
export PATH="$HOME/.local/bin:$PATH"
kagi selfhost-parse --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-check --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-capir --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-emit --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-run --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-run /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
```

最後のコマンドは JSON ではなく、実行結果そのものを `stdout` に出します。

期待値の例:

```json
{
  "ok": true,
  "entry": "parse",
  "source": "/home/vagrant/kagi/examples/hello.ksrc",
  "ast": "{\"kind\":\"program\",\"functions\":[],\"statements\":[{\"kind\":\"print\",\"expr\":{\"kind\":\"string\",\"value\":\"hello, world!\"}}]}",
  "capir": {
    "effect": "print",
    "ops": [{"text":"hello, world!"}],
    "serialized": "print \"hello, world!\"\n"
  },
  "value": "hello, world!"
}
```

## 対応範囲

- owner / cell / heap
- loan state
  - `idle`
  - `mut key`
  - `shared epoch count`
- actions
  - `borrow_mut`
  - `end_mut`
  - `borrow_shared`
  - `end_shared`
  - `drop`
- well-formedness check
- exported summary
  - `idle`
  - `mut`
  - `shared epoch`

## DSL

```text
owner 0 alive idle
owner 1 alive idle

borrow_shared 0 10
borrow_shared 0 10
end_shared 0 10
borrow_mut 1 7
end_mut 1 7
drop 1
```

## Bootstrap Syntax

```text
let epoch e0 = 10
let key k0 = 7

owner cell alive idle

borrow_shared cell e0
assert_export cell shared e0
end_shared cell e0
borrow_mut cell k0
assert_export cell mut
end_mut cell k0
```

## 実行

```bash
cd /home/vagrant/kagi
python3 -m kagi.cli run examples/basic.kagi
```

または

```bash
cd /home/vagrant/kagi
PYTHONPATH=src python3 -m kagi.cli run examples/basic.kagi
```

## インストール

```bash
cd /home/vagrant/kagi
python3 -m venv .venv
.venv/bin/pip install -e .
mkdir -p ~/.local/bin
ln -sf /home/vagrant/kagi/bin/kagi ~/.local/bin/kagi
```

`~/.local/bin` が `PATH` に入っていれば、次のように実行できます。

```bash
kagi run /home/vagrant/kagi/examples/basic.kagi
kagi trace /home/vagrant/kagi/examples/basic.kagi
kagi check /home/vagrant/kagi/examples/basic.kagi
kagi exports /home/vagrant/kagi/examples/basic.kagi
kagi bootstrap-check /home/vagrant/kagi/examples/bootstrap.kg
kagi bootstrap-trace /home/vagrant/kagi/examples/bootstrap.kg
```
