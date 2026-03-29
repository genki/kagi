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

## Front-Half Contracts v0

front half の段階間 ABI は、いまは次の typed contract に寄せています。

- `src/kagi/surface_ast.py`
- `src/kagi/hir.py`
- `src/kagi/artifact.py`
- `src/kagi/kir.py`
- `src/kagi/selfhost_bundle.py`
- `src/kagi/compile_result.py`

JSON は frontend/CLI 境界でだけ扱い、内部では typed object を使います。

- `ParseArtifactV1`
- `CheckArtifactV1`
- `LowerArtifactV1`
- `CompileResultV1`
- `SelfhostPipelineBundleV1`
- `KIRProgramV0`

`compile_source_v1(...)` が、`parse -> check -> lower -> compile` を 1 つの typed result にまとめます。現時点の selfhost 主経路では selfhost frontend の `pipeline` bundle を 1 回だけ読み、`check/lower` 相当は typed contract 側で導出しています。

## Current Self-Hosting Status

現在の KAGI は、この repo の現在の判定基準では `fully self-hosted` です。より正確には、`canonical selfhost compile/run/freeze path` が `fully self-hosted` に到達しています。

一方で Stage 3 として、Python bundle decoder は mainline compile path から外しました。

- `compile_source_v1(...)` は raw bundle decoder を直接呼ばず、`src/kagi/selfhost_runtime.py` の typed bundle API を使う
- `src/kagi/selfhost_bundle.py` の decoder は compatibility shim として残る

これらは test でも固定しています。

- `tests/test_bundle_kir_future.py`
- `tests/test_golden_pipeline.py`

また Stage 4 として、canonical selfhost compile/run path は Python KIR executor を主経路で使わない状態になりました。

- `src/kagi/selfhost_runtime.py` は canonical frontend + canonical corpus の `pipeline` で precompiled bundle snapshot を優先する
- `compile_source_v1(...)` はこの typed bundle API を通る
- Python KIR executor は direct entry / fallback / oracle 側に後退した

さらに Stage 5 として、canonical selfhost path の remaining Python builtin 依存と bootstrap freeze path も主経路から外しました。

- canonical `compile/run` path は `concat`, `eq` を含む Python builtin 群を主経路で使わない
- `selfhost-run` は `compile_source_v1(...).stdout` を使い、Python KIR runtime を叩かない
- canonical `selfhost-freeze` は frozen KIR image を優先し、subset parser / subset->KIR lowering を主経路で使わない

加えて 8 stage 計画の Stage 5 として、front-half utility fallback の Python builtin map 依存も縮退しました。

- `src/kagi/subset_builtins.py` の `CORE_BUILTINS` は空
- `trim`, `starts_with`, `ends_with`, `extract_quoted`, `line_count`, `line_at`, `before_substring`, `after_substring`, `is_identifier` は
  - `subset_eval.py`
  - `capir_runtime.py`
  - `kir_runtime.py`
  の intrinsic として処理する
- canonical path だけでなく、subset interpreter / KIR fallback path でも helper builtin map を必須としない

さらに Stage 6 として、filesystem / packaging 依存は `selfhost_runtime.py` から分離しました。

- canonical frontend source / KIR / bundle / entry snapshot の解決は [selfhost_assets.py](/home/vagrant/kagi/src/kagi/selfhost_assets.py) に集約
- [selfhost_runtime.py](/home/vagrant/kagi/src/kagi/selfhost_runtime.py) は `os`, `pathlib`, `KAGI_HOME` を直接持たない
- canonical compile/build/entry path は asset loader API を通る

さらに Stage 7 として、Python CLI は thin launcher に縮退しました。

- [cli.py](/home/vagrant/kagi/src/kagi/cli.py) は parser 定義と launcher だけを持つ
- command の実行意味論と file read / payload 組み立ては [cli_host.py](/home/vagrant/kagi/src/kagi/cli_host.py) に移した
- `main(argv=None)` は parse して `run_cli_command(...)` に委譲する

最後に Stage 8 として、strict primary path と oracle / compatibility shim の境界を test で固定しました。

- canonical `compile`
- canonical `build/freeze`
- canonical `selfhost-run`

は、通常主経路で

- subset parser / lower fallback
- raw bundle decoder fallback
- host KIR runtime fallback

に依存しないことを strict regression で確認しています。

一方で、CPython host 自体の置換はまだ別計画です。現時点では portable host boundary を repo 内へ vendor しており、`portable/launcher/kagi_launcher.c` が bundled CPython launcher の現在実装です。

置換に向けた最初の native-facing 契約として、CLI 実行面には host command ABI を追加しています。

- `src/kagi/host_abi.py`
- `KagiHostCommandV1`
- `KagiHostResponseV1`
- `run_host_command_v1(...)`
- `execute_host_command_v1(...)`

`cli.py` は引き続き `argparse` launcher ですが、command の実行本体は `argparse.Namespace` ではなく host command object に変換してから動かします。これにより、将来の native launcher は parser を経由せず同じ ABI を直接叩けます。

さらに response 側も ABI 化しました。

- `exit_code`
- `stdout`
- `stderr`
- `payload`

を `KagiHostResponseV1` として返せるので、native launcher は Python の `print` や `SystemExit` 契約を前提にせず host response をそのまま扱えます。

次の slice として、native launcher が直接叩く module target を `kagi.cli` から `kagi.host_entry` に切り替えました。

- `src/kagi/host_entry.py`
- `parse_host_argv_v1(...)`

`host_entry` は `argparse` を使わず、argv を `KagiHostCommandV1` に変換して `execute_host_command_v1(...)` を呼びます。vendored portable launcher もこの entrypoint を向くように更新しています。

さらに launcher の hardcoded host target は sidecar manifest に移しました。

- `portable/launcher/kagi_runtime.env`

これにより launcher binary には

- `kagi.host_entry`
- `app/kagi_app.zip`

の固定文字列を持たず、native image 置換時は manifest 差し替えで host target を変えられます。

さらに manifest は generic runtime/image descriptor に拡張しました。

- `RUNTIME_KIND`
- `RUNTIME_BIN_REL`
- `ENTRY_STYLE`
- `ENTRY_TARGET`
- `IMAGE_REL`
- `WORKSPACE_REL`

現在の既定値は native canonical image backend を指しています。launcher binary からは `bin/python3`, `kagi.host_entry`, `kagi_app.zip` の固定値が消えており、manifest が

- `RUNTIME_KIND=native`
- `RUNTIME_BIN_REL=bin/kagi-native-runtime`
- `ENTRY_STYLE=direct`
- `IMAGE_REL=app/kagi-canonical-image`

を選ぶ構成です。

さらに launcher には `RUNTIME_KIND=native` / `ENTRY_STYLE=direct` 分岐も入りました。現在は fake runtime での回帰までですが、launcher 自体は

- `KAGI_IMAGE`
- `KAGI_HOME`
- `KAGI_ENTRY_TARGET`

を渡して native runtime を直接 `exec` できます。

さらに `portable/runtime/kagi_native_runtime.c` を追加し、`native/direct` 分岐から実際に動く C 製 runtime bridge まで入れました。これはまだ内部で Python host entry を起動しますが、launcher -> native runtime -> host entry という 2 段構成は実動しています。

加えて、`KAGI_IMAGE` が executable な regular file なら native runtime bridge はその image を直接 `exec` します。つまり bridge の内部でも

- direct native image exec
- Python host entry bridge

の 2 経路を持つようになりました。

さらに canonical primary path 用の native image として `portable/image/kagi_canonical_image.c` を追加しました。これは少なくとも canonical selfhost path について

- `selfhost-bootstrap --json`
- `selfhost-build --json`
- `selfhost-freeze --json`
- `selfhost-run`

を Python を通さず処理できます。portable の既定 manifest も現在はこの native image を向いています。

一方で Stage 2 として、canonical corpus の `parse/hir/kir/analysis/lower/compile/pipeline` から次の Python string helper builtin 群は外しました。

- `trim`
- `starts_with`
- `ends_with`
- `extract_quoted`
- `line_count`
- `line_at`
- `before_substring`
- `after_substring`
- `is_identifier`

この repo では、次の条件を満たした時点で `fully self-hosted` と呼びます。現在の canonical selfhost compile/run/freeze path はこれを満たしており、strict regression でも固定しています。

- canonical selfhost compile/run path が Python bundle decoder を直接持たない
- canonical selfhost compile/run path が Python KIR executor を主経路で使わない
- canonical selfhost compile/run path が Python builtin 群を主経路で使わない
- Python 実装が bootstrap seed / compatibility shim / differential oracle に後退している

## Static Path v0

front half には最小の静的パスも追加しています。

- `src/kagi/resolve.py`
- `src/kagi/typecheck.py`
- `src/kagi/effects.py`

現在の対象は tiny selfhost front half が返す surface/HIR に対する最小検査です。

- 名前解決
- call arity
- `string / bool` の最小型検査
- `print` effect の要約

## KIR v0

`selfhost-run` の実行層として、print-only scaffold から始め、現在は tiny selfhost current-shape を実行できる KIR v0 を置いています。

- 定義: `src/kagi/kir.py`
- runtime: `src/kagi/kir_runtime.py`
- selfhost の `LowerArtifactV1` は HIR から lower された executable KIR を持つ
- current tiny language の `let / print / if / call / return` を KIR runtime で実行できる
- `selfhost-run` は `pipeline -> HIR -> KIR -> stdout` を通る

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
- `line_count`
- `line_at`
- `before_substring`
- `after_substring`
- `is_identifier`
- `extract_quoted`
- `trim`

実装は分割済みで、`subset.py` は facade です。

- `src/kagi/subset_ast.py`
- `src/kagi/subset_lexer.py`
- `src/kagi/subset_parser.py`
- `src/kagi/subset_eval.py`
- `src/kagi/subset_builtins.py`
- `src/kagi/bootstrap_builders.py`
- `src/kagi/subset.py`

このうち `program_*_ast` 系の bootstrap helper は `bootstrap_builders.py` へ分離しています。

## Self-Hosted Front Half

`examples/selfhost_frontend.ks` は KAGI subset で書いた tiny frontend です。
いまは `print "..."` 文を受け付ける極小言語を対象にしています。複数行の `print` 文、`print concat("a","b")` のような最小式、`let x = ...` と `print x`、さらに `eq(...)` と `if(cond, then, else)`、`if cond { ... } else { ... }`、`fn name() { ... }` / `fn name(x) { ... }` と `call name()` / `call name("...")` を処理できます。

現時点では parser/check/lower の一部を self-hosted 側へ寄せ始めており、単純な `print "..."` 1 行ケース、`print concat("...", "...")` 1 行ケース、`let x = "..."` / `print x`、`let x = concat("...", "...")` / `print x` の 2 行ケース、`fn name(x) { print concat(x, "...") }` + `call name("...")` の固定形は `examples/selfhost_frontend.ks` 自身が `ok` / AST / artifact を返します。

役割は 3 つに分けています。

- `parse(source)`:
  - tiny source から最小 program AST JSON を作る
- `check(source)`:
  - program AST を bridge で受けたうえで tiny source を受理できるか判定する
- `lower(source)`:
  - program AST を bridge で受けて最小 JSON artifact を作る
- `compile(source)`:
  - 現在は `lower(source)` の alias
- `pipeline(source)`:
  - `parse -> lower` を 1 回でまとめた compile-once bundle を返す

`selfhost-run` は KIR v0 を経由して stdout を出します。非 JSON の主経路は `pipeline -> KIR -> stdout` です。
`selfhost-check` も `compile_source_v1(...)` を通るので、静的パスの結果を返します。

また、一般的な self-hosting の流れに合わせて `selfhost-bootstrap` を置いています。これは trusted seed KIR から

- `stage0` trusted seed
- `stage1` seed compiler が自分自身を compile した結果
- `stage2` stage1 compiler がもう一度自分自身を compile した結果

を返し、fixed point を確認します。

```bash
export PATH="$HOME/.local/bin:$PATH"
kagi selfhost-parse --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-check --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-capir --json /home/vagrant/kagi/examples/selfhost_frontend.ks /home/vagrant/kagi/examples/hello.ksrc
kagi selfhost-bootstrap --json /home/vagrant/kagi/examples/selfhost_frontend.ks
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
