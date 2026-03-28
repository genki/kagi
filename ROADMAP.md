# KAGI Self-Hosting Roadmap

## 方針

早い段階で self-hosting へ到達するには、最初からフル言語を作るより、

1. Lean で証明済みの `core kernel`
2. その上に乗る `bootstrap frontend`
3. bootstrap frontend 自身を KAGI で書き直せる `subset language`

の順に積み上げるのが現実的です。

## フェーズ

### Phase 0: Core Kernel

- owner / cell / heap
- loan state
- step semantics
- exported summary
- CLI 実行

状態:
- 実装済み

### Phase 1: Bootstrap Frontend

- 名前付き owner/key/epoch
- `let key`, `let epoch`
- 人間向け source file を core action 列へ lowering
- `assert_export`
- 実行 trace / check / exports

目的:
- KAGI の自己記述 compiler を書く前に、人が読み書きできる source format を持つ
- 将来の self-hosted compiler の出力ターゲットを固定する

状態:
- 今回ここまで進める

### Phase 2: Subset Language

- `fn`
- `let`
- `if`
- `match` 相当の最小分岐
- 整数 / 真偽 / 文字列 / 配列または list
- 標準入出力

目的:
- parser / checker / lowerer を KAGI 自身で書ける最小表現力を用意する

### Phase 3: Self-Hosted Frontend

- KAGI subset で parser を実装
- KAGI subset で checker を実装
- KAGI subset で lowerer を実装
- Python 実装と結果比較できる golden test を用意

目的:
- 「KAGI compiler の front half が KAGI で書かれている」状態にする

### Phase 4: Trust Reduction

- Python 実装は reference executor / differential tester の役割へ後退
- KAGI 実装が primary frontend になる
- frontier summary, capability envelope, module compilation を追加

状態:
- 未完了
- Stage 1: host dependency visibility は完了
  - canonical path がまだ依存する Python host pieces を test と doc の両方で固定した
  - `tests/test_bundle_kir_future.py`
  - `README.md` の `Current Self-Hosting Status`
- Stage 2: canonical string helper builtin 縮退は完了
  - canonical corpus の `parse/hir/kir/analysis/lower/compile/pipeline` から
    - `trim`
    - `starts_with`
    - `ends_with`
    - `extract_quoted`
    - `line_count`
    - `line_at`
    - `before_substring`
    - `after_substring`
    - `is_identifier`
    を外した
- Stage 3: bundle decoder の compatibility shim 化は完了
  - `compile_result.py` は raw bundle decoder を直接使わない
  - selfhost runtime の typed bundle API を主経路にした
- 現在の主 blocker:
  - Python KIR executor
  - Python core expression builtin (`concat`, `eq`)

## 当面のマイルストーン

### M1

- installable `kagi` command
- `run`, `trace`, `check`, `exports`

### M2

- `.kg` bootstrap syntax
- symbolic names
- `assert_export`
- examples を bootstrap syntax に移行

### M3

- subset parser
- self-hosting 用 stdlib
- self-hosted parser の最初の雛形

状態:
- 最小 subset evaluator と `selfhost-run` を追加
- tiny frontend に `check / lower / compile` を追加
- `print "..."` を JSON artifact へ lower できる
- tiny frontend に `parse` を追加し、program AST JSON を返せる
- Python 側の bridge が AST JSON を typed object として受けられる
- bridge が typed object を tiny CapIR fragment へ lower できる
- tiny CapIR fragment を実行する専用 runtime path がある
- tiny source は複数 `print` 文を扱える
- `front-half contracts v0` を追加
  - `surface_ast.py`
  - `hir.py`
  - `artifact.py`
  - `compile_result.py`
  - `compile_source_v1(...)`
- `split-subset-pipeline` を追加
  - `subset_ast.py`
  - `subset_lexer.py`
  - `subset_parser.py`
  - `subset_eval.py`
  - `subset_builtins.py`
  - `bootstrap_builders.py`
  - `subset.py` は facade
- `resolve-and-typecheck-v0` を追加
  - `resolve.py`
  - `typecheck.py`
  - `effects.py`
  - `compile_source_v1(...)` が静的パスを通る
- `compile-once-selfhost` を追加
  - `compile_source_v1(...)` は selfhost frontend の `parse` と `compile` だけを主経路で呼ぶ
  - `check/lower` は typed contract 側から導出する
- `front-half compile-once` を追加
  - `selfhost_frontend.ks` の `pipeline(source)` が parse/lower を 1 回で束ねる
  - `compile_source_v1(...)` は pipeline bundle を 1 回読む
- `typed-selfhost-bundle-abi` を追加
  - `selfhost_bundle.py`
  - `SelfhostPipelineBundleV1`
  - pipeline bundle decode を 1 箇所へ集約
- `kir-v0` を追加
  - `kir.py`
  - `kir_runtime.py`
  - `lower_hir_to_kir.py`
  - selfhost run path を print-only artifact から executable KIR へ載せ替える
  - current tiny language の `let / print / if / call` を KIR で実行できる

## 非目標

- 最初から optimizer を作ること
- 最初から full trait/dynamic dispatch を実装すること
- frontier summary を runtime と同時に全部作ること

## 実装上の判断

- 先に `lowering target` を固定する
- bootstrap syntax は syntax sugar に留める
- core semantics は Lean 最小核から逸脱しない

## Fully Self-Hosted までの 5 段階

1. Stage 1: host 依存の見える化
   - test と doc の両方で「なぜまだ fully self-hosted ではないか」を固定する
2. Stage 2: string helper builtin 縮退
   - canonical corpus で still required な string parsing / line helper 依存を削る
3. Stage 3: bundle decode の縮退
   - Python bundle decoder を compatibility shim へ後退させる
4. Stage 4: KIR runtime の縮退
   - Python KIR executor を oracle / fallback に後退させる
5. Stage 5: self-compile / self-freeze 主経路化
   - Python を bootstrap seed / differential oracle のみにする
