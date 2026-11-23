# `--spec-fixed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL、root） |
| オプション | `--spec-fixed` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

DFly2 speculative decoding の検証幅を適応的に縮めず、各 draft で生成された tree 全体を検証対象にします。検証幅の適応選択、性能に応じた plain decode へのバックオフ、適応モード時の draft 早期終了を止めます。`--spec-k` が draft の上限幅を設定しますが、実際に生成された tree の大きさは draft の結果にも依存します。

## 使い方

```sh
# 通常の生成モードで DFly2 を使い、固定幅で検証する
strata-hy4-sycl --model model.strata --engram engram.strata \
  --tokens prompt-ids.txt --gen 128 --draft dfly2 --spec-fixed

# server モードで DFly2 を使う場合も設定を渡せる
strata-hy4-sycl --serve --native model.strata --engram engram.strata \
  --draft dfly2 --chunk 8 --spec-fixed
```

## 値と既定値

値を取りません。parser はこの引数を読むと `scfg.adaptive = false` を設定します。省略時の `SpecCfg::adaptive` は `true` です。引数値の検証や数値範囲はありません。値を続けて指定すると、その文字列は別引数として処理され、未知引数エラーになります。繰り返し指定しても同じ false を設定するだけです。parser と既定値は `engine/src/hy4flash/sycl/sy_main.cpp:96-97,179-189`、`engine/src/hy4flash/sycl/sy_spec.h:21-31` にあります。

## 実行時の動作

`Spec::choose_m()` は adaptive が false の場合、コストモデルや `--spec-cut` の判定に入らず、draft tree の全ノード数 `tr.M` を選びます。adaptive が false だと `note_iter()` も即時に戻るため、反復時間に基づく plain decode へのバックオフを行いません。また draft に渡す early-exit 閾値は 0 になります。これらの分岐は `engine/src/hy4flash/sycl/sy_spec.h:88-104,131-151,201-215` です。

このフラグだけでは speculative decoding を有効化しません。通常生成モードでは `--draft dfly2` かつ `--gen` が正の場合に限り Spec 経路を実行します（`engine/src/hy4flash/sycl/sy_main.cpp:279-280,379-386`）。server モードでは `--draft` が `off` でなく、モデルに DFly2 drafter tensor があり、chunk が 8 以上の場合に Spec を使います。既定の `--draft auto` もこの条件で対象になります（`engine/src/hy4flash/sycl/sy_serve.h:248-257,271-307,468-472`）。

他の関連設定との関係:

- `--spec-k` は draft 幅の上限を設定します。`Spec` 構築時に実装上限へ丸められ、1 未満も 1 に補正されます（`engine/src/hy4flash/sycl/sy_spec.h:65-70`）。
- `--spec-cut` が指定されても、fixed 分岐が先に適用されるため検証幅選択には使われません（`engine/src/hy4flash/sycl/sy_spec.h:88-94`）。
- 通常生成モードでは `--draft` の既定値は `off` です。server モードでは `draft` が空なら `auto` に設定されます（`engine/src/hy4flash/sycl/sy_main.cpp:93,179,250`、`engine/src/hy4flash/sycl/sy_main.cpp:241`）。

通常生成モードの speculative 実行では、結果 ID を stdout に出し、spec の集計に `fixed` と表示します。また生成 ID を `--out` で指定したディレクトリの `gen_ids.txt` に書きます（`engine/src/hy4flash/sycl/sy_main.cpp:392-408`、`engine/src/hy4flash/sycl/sy_spec.h:414-429`）。

## 適用条件と副作用

SYCL 版 `strata-hy4-sycl` の root parser に適用されます。設定自体にファイル変更や追加プロセス起動はありません。Spec 経路が有効なら、検証する tree が適応モードより大きくなることがあり、GPU 上の draft/verify 処理量に影響します。固定モードでも、draft が利用できない位置や context 上限などでは通常の plain step に進む経路があります（`engine/src/hy4flash/sycl/sy_spec.h:176-208`）。

## 出力とエラー

このフラグ専用の警告・エラー出力はありません。値を付けた場合など、parser が認識しない引数は stderr に `unknown arg ...` を出し、終了コード 2 を返します（`engine/src/hy4flash/sycl/sy_main.cpp:190-197`）。Spec 実行中に draft が失敗した場合は通常生成モードで stderr に `spec: draft failed` を出して終了コード 1、server モードではプロトコル出力に `ERR spec: ...` を返して終了コード 1 となります（`engine/src/hy4flash/sycl/sy_spec.h:205-208`、`engine/src/hy4flash/sycl/sy_main.cpp:386-391`、`engine/src/hy4flash/sycl/sy_serve.h:470-476`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:96-97,179-189` — `SpecCfg` の生成と parser 定義。値を読まず adaptive を false にする。
- `engine/src/hy4flash/sycl/sy_spec.h:21-31,65-70` — adaptive の既定値と K の補正。
- `engine/src/hy4flash/sycl/sy_spec.h:88-104,131-151,201-215` — 固定検証幅、バックオフ、draft 早期終了閾値の適用。
- `engine/src/hy4flash/sycl/sy_main.cpp:279-280,379-408` — 通常モードでの適用条件と出力。
- `engine/src/hy4flash/sycl/sy_serve.h:248-257,271-307,468-476` — server モードの適用条件と Spec 呼び出し・失敗経路。
- `engine/src/hy4flash/sycl/sy_main.cpp:190-197` — 未知引数の出力と終了コード。
