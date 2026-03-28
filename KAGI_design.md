# KAGI: Keyed Affine Graph Inference

## 名前
**KAGI**

- **K**eyed: 借用は return key / epoch key で追う
- **A**ffine: 所有権は affine / linear に管理する
- **G**raph: 依存と要約は frontier graph に圧縮する
- **I**nference: 要約は関数ごとに局所合成する

「鍵」と読めるので、借用が終わると所有権が「鍵で戻る」という中心アイデアとも一致します。

## 未解決点への対策

### 1. 要約爆発
**frontier summary** を使います。

- 公開するのは「外部から観測可能な root / path frontier」だけ
- 内部 path は trie に集約し、兄弟は wildcard で畳み込む
- shared 借用は reader count を捨て、**epoch 色**だけ残す
- summary hash は正規化後の frontier graph に対して計算する

効果:
- body の局所変更が summary に波及しにくい
- 下流 crate は body hash ではなく summary hash にだけ依存する

### 2. shared borrow の ergonomics
**epoch coalescing** を使います。

- 同じ root に対する shared borrow は全部同じ epoch に合流
- reader の個数は内部 state だけが持つ
- 外部には `shared e` だけ見せる
- surface syntax は `view` ブロックに desugar し、shared end は極力自動挿入

効果:
- プログラマは key や reader count を見なくてよい
- verifier は `mut` と `shared e` の衝突だけ見ればよい

### 3. trait / dynamic dispatch
**capability envelope** を導入します。

- trait method は `Pre/Post/Alias/Eff` の envelope を持つ
- 各 impl はその envelope を refinement する証明書を object に添付
- call site は具体実装本体ではなく envelope だけを見る

効果:
- dynamic dispatch を残したまま separate compilation できる

### 4. ループ・再帰・固定点
**α-renamed key classes + SCC widening** を使います。

- key の実 ID は追わず、origin site / root / variance で同値類化
- ループ・相互再帰は SCC ごとに abstract interpretation
- widening は frontier antichain 上で行う

効果:
- summary synthesis が停止しやすい
- 再計算単位を SCC に閉じ込められる

### 5. 実装難度 / TCB
**proof-carrying summaries** を使います。

- front-end は CapSSA を作る
- verifier は CapSSA から summary と小さな証明書を生成
- object には native code と CapSSA shadow と証明書を同梱
- linker / loader は証明書だけ高速に再検査する

効果:
- 最適化系を大きく TCB から外せる
- 再ビルド時は summary と証明書の差分だけ追えばよい

## Lean で証明した最小核
Lean ファイル `KAGI_core.lean` では、shared reader count を export から隠しても安全判定が壊れない最小核を証明しています。

### 内部状態
- `idle`
- `mut k`
- `shared e n`  (`n + 1` 個の reader が epoch `e` に属する)

### 外部に公開する圧縮要約
- `idle`
- `mut`
- `shared e`

### 機械証明した性質
1. `WellFormed` は 1 step でも到達可能列でも保存される
2. `export ≠ idle` なら `drop` も `borrowMut` も禁止される
3. `export = mut` なら `borrowShared` は禁止される
4. `export = shared e1` なら、別 epoch `e2` の `borrowShared` は禁止される
5. `export = shared e` なら、reader count を公開しなくても同じ epoch の shared extension は構成できる

最後の 4, 5 が、
**「epoch と busy/idle の少数の情報だけ export すれば、reader count や key ID を捨てても separate compilation 用の判定に足りる」**
ことを示す最小の証明になっています。
