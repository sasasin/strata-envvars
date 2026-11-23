# `--spec-tree`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（トップレベル） |
| オプション | `--spec-tree` |
| 別名 | なし（反対の設定を行う `--no-spec-tree` がある） |
| 値 | 値を取らないフラグ |

## 役割

DFly2 speculative decoding の draft 時に、通常の最有力候補に加えて条件を満たす第2候補も分岐候補として作る Tree-8 経路を有効にします。この設定は speculative decoding を有効化するものではありません。SYCL の `SpecCfg` では tree が既定で有効です。通常の生成経路で使うには `--draft dfly2` と正の `--gen` が必要で、server 経路では drafter を利用できるモデルと `--draft` の設定が必要です。`--no-spec-tree` を使うと無効化できます。

## 使い方

```sh
# SYCL server で DFly2 を明示し、draft 候補の tree 分岐を有効にする
strata-hy4-sycl --serve --native model.strata --draft dfly2 --spec-tree

# 位置引数入力の生成経路で DFly2 を使う場合
strata-hy4-sycl --model model.strata --engram Engram.strata --tokens prompt-ids.txt --draft dfly2 --gen 64 --spec-tree
```

## 値と既定値

値は不要です。引数解析時に `scfg.tree = true` を設定し、値の変換や範囲検証はありません。`SpecCfg::tree` の初期値も `true` です。`--no-spec-tree` は同じフィールドを `false` にするため、両方を指定した場合は引数列で後に処理された方が最終設定になります（`engine/src/hy4flash/sycl/sy_main.cpp:96,107-115,187-188`、`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。

## 実行時の動作

通常の CLI 生成経路では `--draft` の省略値は `off` であり、`--draft dfly2` かつ `--gen > 0` の場合に限り speculative decode が実行されます。`--spec-tree` は `SpecCfg` を通じて `Spec::run` に渡り、各 draft step で `draft_tree(..., cfg.tree, ...)` の tree 有効フラグになります（`engine/src/hy4flash/sycl/sy_main.cpp:179-189,246-253,279-280,379-386`、`engine/src/hy4flash/sycl/sy_spec.h:21-30,201-209`）。

Tree 有効時、greedy 系候補生成では最有力候補に加え第2候補を調べ、スコア差から算出した第2枝の重み `p2` が `0.05` を超える場合に枝へ追加します。確率的 sampling 経路では候補分布から第1候補を選んだ後、残余分布の総量 `z2` が `0.08` を超える場合に第2候補をサンプルし、`p2 > 0.05` の場合に枝へ追加します。上限は `min(K + 1, DFLY_BMAX)` ノードです。tree を無効にしても DFly2 の speculative decoding は継続し、第2候補による分岐生成だけが抑止されます（`engine/src/hy4flash/sycl/sy_dfly2.h:790-805,824-850,852-883`）。

検証は生成された候補構造に応じて行われます。枝がない場合は通常の chunk forward、枝がある場合は tree 情報を渡す forward を使います（`engine/src/hy4flash/sycl/sy_spec.h:235-249`）。server では `--draft off` なら speculative decoding を使わず、`auto` は drafter の有無と chunk 条件で有効化が決まります。`--draft dfly2` はモデルに drafter tensor がない場合、または `--chunk < 8` の場合にエラーとなります（`engine/src/hy4flash/sycl/sy_serve.h:248-256`）。

## 適用条件と副作用

- `--spec-tree` 単独では DFly2 を初期化せず、speculative decoding も開始しません。通常生成では `--draft dfly2` と `--gen > 0` が必要です。server で明示的に使うなら `--draft dfly2` が必要です。
- server は `--draft dfly2` の場合、drafter tensor の有無と `--chunk >= 8` を検査します。違反時はプロトコル `ERR` を出して終了コード `2` を返します。`auto` で drafter 初期化が成立しない場合は speculative decoding を使わない経路になります（`engine/src/hy4flash/sycl/sy_serve.h:248-278`）。
- このフラグ固有のファイル書き換えやネットワーク操作はありません。通常生成経路の DFly2 モードでは、tree の設定にかかわらず `--out` で指定したディレクトリ（既定 `.`）へ `gen_ids.txt` を書き出します。最終的な speculative 設定は `[spec] ... tree=<0|1>` として標準エラーに報告されます（`engine/src/hy4flash/sycl/sy_main.cpp:104,406-408`、`engine/src/hy4flash/sycl/sy_spec.h:414-420`）。

## 出力とエラー

このフラグには専用の validation error はありません。未知の引数は標準エラーへ `unknown arg ...` を出して終了コード `2` になりますが、`--spec-tree` 自体は parser に登録されています（`engine/src/hy4flash/sycl/sy_main.cpp:187-197`）。生成時に drafter の初期化や draft が失敗した場合はそれぞれの処理がエラーを返しますが、`--spec-tree` 固有の失敗経路とは確認できません（`engine/src/hy4flash/sycl/sy_main.cpp:330-341`、`engine/src/hy4flash/sycl/sy_spec.h:203-208`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:96,179-189` — `SpecCfg` の生成、既定 draft mode、`--spec-tree` と `--no-spec-tree` の parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:246-253,279-280,303-316,379-386,406-408` — 通常生成での DFly2/spec 条件、設定の受け渡し、実行報告。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30,201-209,235-249,414-420` — tree の既定値、draft 呼び出し、分岐の検証方法、実行報告。
- `engine/src/hy4flash/sycl/sy_dfly2.h:790-805,824-850,852-883` — tree 構築と `enable_tree` による第2候補追加条件。
- `engine/src/hy4flash/sycl/sy_serve.h:248-278` — server の drafter 有無、chunk 条件、speculative 初期化条件。

ソースから確認した範囲は上記 SYCL 実装です。実行バイナリの `--help` は参照していません。
