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

## 非目標

- 最初から optimizer を作ること
- 最初から full trait/dynamic dispatch を実装すること
- frontier summary を runtime と同時に全部作ること

## 実装上の判断

- 先に `lowering target` を固定する
- bootstrap syntax は syntax sugar に留める
- core semantics は Lean 最小核から逸脱しない
