# `strata-hy4 --spec-early`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--spec-early` |
| 別名 | なし |
| 値 | 浮動小数点数。ドラフト木の frontier reach に対する早期終了閾値 |

## 役割

DFly2 speculative decoding のドラフト木を展開するとき、最も reach の高い未展開 frontier が指定値を下回った段階で残りの展開を打ち切ります。これにより `hidden_correction` と `lm_head` を使うドラフト連鎖の追加評価を止めます。これはドラフト側の早期終了条件であり、値が実際に適用されるかは Spec の実行設定にも依存します。

## 使い方

```sh
# CUDA/HIP runner で DFly2 を使う推論例。ファイル名は実環境のものに置き換える。
strata-hy4 --model ./model.strata --tokens ./prompt.ids --gen 32 --draft dfly2 --spec-early 0.04
```

`--spec-early` は値を 1 つ取ります。オフラインで Spec 経路に入るには `--draft dfly2` と正の `--gen` が必要です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363, 701`）。

## 値と既定値

- 既定値は `0.04`（`SpecCfg::early_cut`）です。`--spec-early` を複数回指定すると、引数走査中に同じフィールドへ順に代入されるため、最後の指定値が残ります（`engine/src/hy4flash/run/hy4_spec.hip.h:18-31`、`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 414`）。
- parser は次の引数を `atof` で読み、`float` に変換します。Strata 側に値域検証や範囲補正はありません。値がない場合は stdout に `ERR --spec-early needs a value` を出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383, 414`）。
- 閾値判定は `early_cut > 0` の場合だけ行われます。`0` または負数は早期終了を無効にします（`engine/src/hy4flash/run/hy4_dfly2.hip.h:1231-1234, 1244-1246`）。

## 実行時の動作

parser が値を `scfg.early_cut` に格納し、`Spec::run` は有効条件を満たす場合に限ってこの値を DFly2 の `draft_tree` に渡します。`draft_tree` は frontier のうち reach が最大の候補を選び、その reach が閾値より小さく、既に root 以外のノードがある場合、残りの frontier 展開を終了します。選んだノードの子も、その reach が閾値未満なら追加展開しません（`engine/src/hy4flash/run/hy4_spec.hip.h:284-310`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:1223-1249`）。

値が `draft_tree` に渡るのは、`adaptive` が有効、`--spec-cut` の値が負、`sabotage` と `nodraft` が無効な場合です。従って `--spec-fixed`、`--spec-cut` に 0 以上の値、`--spec-sabotage`、`--spec-nodraft` と併用する経路では、このオプションの閾値は適用されません。`--spec-tree` が無効でも `early_cut` 自体は別の条件で渡され、frontier の早期終了判定は実行されます（`engine/src/hy4flash/run/hy4_spec.hip.h:287-310`）。

## 適用条件と副作用

- オフライン推論では、`--draft dfly2`、`--gen` が正、`--dfly-alloc-only` が無効で `spec_mode` に入った場合に `Spec::run` が使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:701, 992-1000`）。
- serve 経路も `ServeOpts` に `SpecCfg` を渡し、実際に speculative path を選ぶ場合は同じ `Spec::run` を呼び出します（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-558`、`engine/src/hy4flash/run/hy4_serve.hip.h:546-556`）。
- この値が変えるのはドラフト木の追加展開量です。ソース上、値の範囲による拒否や自動調整は確認できません。特定の値による速度・品質の推奨は、ここで確認したソースだけからは判断できません。

## 出力とエラー

Spec レポートは stderr に設定値を `early=...` として表示し、2 行目に `early_exits` の回数を含めます。設定値の表示は、上記の有効条件で値が使われたかどうかを示すものではありません（`engine/src/hy4flash/run/hy4_spec.hip.h:513-521`）。値なしは前述の stdout エラーと終了コード 2 です。専用の値域エラーはありません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 408-415` — CLI 引数の読み取り、値変換、`SpecCfg` への代入、値欠落時の終了。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-31, 284-310` — 既定値と閾値を渡す条件。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:1114-1122, 1223-1249` — ドラフト木生成、frontier reach による終了と子展開条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701, 992-1008`、`engine/src/hy4flash/run/hy4_serve.hip.h:546-556` — offline と serve における Spec 実行経路。
- `engine/src/hy4flash/run/hy4_spec.hip.h:513-521` — stderr の Spec レポート。

本書は索引で指定された CUDA/HIP の `root/` scope のみを扱います。Metal runner にも `--spec-early` があり、SYCL runner には `--spec-early-cut` がありますが、それぞれ parser と設定値が別のため本書の挙動には含めていません。
