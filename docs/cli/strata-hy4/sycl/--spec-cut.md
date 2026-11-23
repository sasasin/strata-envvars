# `--spec-cut`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--spec-cut` |
| 別名 | なし |
| 値 | 数値を1個取り、`float` に変換 |

## 役割

DFly2 の適応的な speculative verification で、検証するドラフトノード数を confidence 閾値で選びます。非負値を指定すると、計測コストに基づく幅選択を使わず、閾値を超える confidence が続く範囲を検証します。これは DFly2 が実際に動く場合だけ効果があります（`engine/src/hy4flash/sycl/sy_spec.h:88-103`）。

## 使い方

```sh
# エンジン line protocol で DFly2 を有効にし、confidence 閾値 0.2 を指定
strata-hy4-sycl --serve --native model.strata --draft dfly2 --spec-cut 0.2

# オフライン生成でも DFly2 と生成数を指定
strata-hy4-sycl --model model.strata --tokens ids.txt --draft dfly2 --gen 64 --spec-cut 0.2
```

## 値と既定値

- 引数を `atof` で読み、`float` にして `SpecCfg.cut` に格納します。既定値は `-1.0` です（`engine/src/hy4flash/sycl/sy_main.cpp:93-96,179-183`、`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。
- `cut < 0` では閾値分岐に入らず、適応的なコストモデルで検証幅を選びます。`cut >= 0` では、confidence が `cut` より大きい間ノードを数え、その数を検証幅として返します（`engine/src/hy4flash/sycl/sy_spec.h:88-103`）。
- parser は数値の範囲や変換成否を検証していません。したがって、値の有効範囲を CLI が拒否する経路は確認できません（`engine/src/hy4flash/sycl/sy_main.cpp:179-183`）。値の推奨範囲はソースから確認できません。
- 引数自体を省略すると `nxt()` が `ERR --spec-cut needs a value` を標準出力へ出し、終了コード `2` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,182`）。

## 実行時の動作

適応モードでは各ドラフト後、`choose_m` が `node_conf` を閾値と比較して検証幅を決めます。`cut >= 0` の場合、適応的な実測コストモデルによる選択と、その反復時間に応じた自動 backoff は行われません（`engine/src/hy4flash/sycl/sy_spec.h:88-103,131-150`）。

`--spec-cut` と `--spec-fixed` を同時に指定した場合、`choose_m` は最初に `adaptive == false` を判定して全ドラフト幅を返すため、閾値は使われません（`engine/src/hy4flash/sycl/sy_main.cpp:180-183`、`engine/src/hy4flash/sycl/sy_spec.h:88-94`）。`cut >= 0` の場合はドラフトチェーンの early-cut も無効になります（`engine/src/hy4flash/sycl/sy_spec.h:201-205`）。

## 適用条件と副作用

- 通常のオフライン実行では `--draft` の既定値が `off` で、生成数が正かつ `--draft dfly2` の場合に限り speculative decoding が実行されます。そのとき `Spec` に設定が渡ります（`engine/src/hy4flash/sycl/sy_main.cpp:250,276-280,379-386`）。
- `--serve` では `--draft` の既定値は `auto` です。モデルに drafter があり、chunk が8以上で DFly2 の初期化に成功した場合に `Spec` が作られます。`--draft off`、drafter がない、chunk が8未満、または `auto` で初期化に失敗した場合、speculative path は使われず、この値も適用されません。明示的な `--draft dfly2` で drafter がない場合や chunk が8未満の場合は、serve 側がエラーを返します（`engine/src/hy4flash/sycl/sy_serve.h:248-278,303-307,468-479`）。
- 閾値指定は検証する幅を変え、早期終了と適応 backoff を抑止します。ファイルや環境変数を書き換える処理は、このオプションの利用箇所では確認できません。

## 出力とエラー

オプション単独の成功メッセージや警告はありません。値の欠落は標準出力の `ERR --spec-cut needs a value` と終了コード `2` になります。数値範囲の validation エラーは実装されていません（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,179-183`）。serve 中に speculative run 自体が失敗すると `ERR spec: ...` を line protocol に出して終了コード `1` を返しますが、これは `--spec-cut` 固有のエラーではありません（`engine/src/hy4flash/sycl/sy_serve.h:470-475`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-115,179-196` — 設定の初期値、値の取得、欠落引数と未知引数の処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,250-280,307-317,379-390` — serve/offline の設定引き渡しと DFly2 実行条件。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30,65-72` — `SpecCfg` の既定値と構成。
- `engine/src/hy4flash/sycl/sy_spec.h:88-103,131-150,201-205` — 検証幅選択、backoff の条件、early-cut との相互作用。
- `engine/src/hy4flash/sycl/sy_serve.h:248-278,303-307,468-479` — serve 時の DFly2 適用条件と失敗出力。
