# `--par-sweep`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal） |
| オプション | `--par-sweep` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデルと Metal runner の初期化後に、並列 slot 数を 1、4、8、32、64 と変えて連続バッチの prefill と decode を計測し、各段階の throughput を標準出力へ表示します。実行時に 64 slot まで使える上限を設定するため、モデルの読込み・warm-up・runner 初期化も含めて通常より大きな Metal 資源を確保することがあります。

## 使い方

```sh
# モデルを読み込み、既定の prompt 長・生成 step 数で並列度を計測する
strata-inkling-metal --model ./model.strata --par-sweep

# 計測で使う prompt 長と decode step 数を指定する
strata-inkling-metal --model ./model.strata --par-sweep --prompt-len 128 --gen 32

# 走査する最大 slot 数を 8 に制限する（オプションの順序に注意）
strata-inkling-metal --model ./model.strata --par-sweep --parallel 8
```

## 値と既定値

`--par-sweep` 自体は値を取りません。既定では sweep は無効です。指定すると `do_par_sweep` を有効にし、その時点で `max_slots` が64未満なら64に設定します。実際の測定候補は `[1, 4, 8, 32, 64]` で、`max_slots` を超える候補に達するとそこで終了します。runner 側は slot 数を1〜64に clamp します（`engine/src/inkling2/metal/ink_metal_main.cpp:421-428,457,606-609`; `engine/src/inkling2/metal/ink_metal_runner.h:236-238`）。

prompt 長と生成 step 数は `--prompt-len` と `--gen` で指定し、既定値はそれぞれ128と32です。両値は `atoi` で整数化されますが、この parser では数値形式や正の範囲を検証しません（`engine/src/inkling2/metal/ink_metal_main.cpp:423-424,451-452`）。負数や0を指定した場合の有効性は保証されず、特に0 step では計測出力の step あたり時間の計算に0が使われます（`engine/src/inkling2/metal/ink_metal_main.cpp:409-412`）。

## 実行時の動作

`--par-sweep` の設定は左から順に引数を解析した時点で `max_slots` を更新します。このため `--par-sweep --parallel 8` は後続の `--parallel` が上限を8に戻して1・4・8を測定します。一方、`--parallel 8 --par-sweep` は sweep が64へ引き上げるため64までの候補が対象になります。runner 初期化時には最終 slot 数を1〜64へ丸めて保持します（`engine/src/inkling2/metal/ink_metal_main.cpp:449,457`; `engine/src/inkling2/metal/ink_metal_runner.h:236`）。

測定では各 slot を reset し、slot ごとに合成 token ID の prompt を投入して prefill し、続けて全 slot をまとめた decode step を `--gen` 回実行します。結果は `[PAR c=...]` 行として stdout に出力されます。`--bench` を同時に指定した場合は通常の単一 slot bench が先に実行され、その後に並列 sweep が続きます（`engine/src/inkling2/metal/ink_metal_main.cpp:363-412,589-614`）。

## 適用条件と副作用

`--model FILE.strata` が必要です。モデル読込み、既定で有効な warm-up、Metal runner 初期化の後に sweep へ進みます。slot 数は runner の KV／state 資源量に関係し、workspace 見積りでも `max_slots` に比例する要素があります。従って sweep 有効時は起動時の割当量が増えたり、working-set 制約に応じて context 長が調整されたりすることがあります（`engine/src/inkling2/metal/ink_metal_main.cpp:470-493`; `engine/src/inkling2/metal/ink_metal_runner.h:236-239,385-400,758-764`）。

この処理は Metal 上でモデル計算を実行して時間を計測します。確認した sweep 経路には結果ファイルへの書込みはなく、結果は標準出力、デバイス・runner 情報や失敗理由は標準エラーに出ます（`engine/src/inkling2/metal/ink_metal_main.cpp:475-479,606-616`; `engine/src/inkling2/metal/ink_metal_runner.h:758-764`）。

## 出力とエラー

slot の prefill または decode に失敗すると sweep はその場で中断し、stderr に `[ERROR] par c=<slot数>: <理由>` を出して終了コード1を返します。モデル読込みまたは runner 初期化の失敗も stderr にエラーを出して終了コード1です。モデル指定がない場合は usage をstderrに表示し、終了コード2で終了します（`engine/src/inkling2/metal/ink_metal_main.cpp:470-493,606-612`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:421-428,449-457` — 既定値、`--parallel` と `--par-sweep` の parser、順序依存の slot 上限設定。
- `engine/src/inkling2/metal/ink_metal_main.cpp:363-412` — 各 slot の reset、合成 prompt の prefill、decode、throughput 出力。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493,589-616` — モデル必須条件、初期化、`--bench` との実行順、sweep の候補列と失敗経路。
- `engine/src/inkling2/metal/ink_metal_runner.h:236-239,385-400,758-764` — runner の slot 上限、slot 数に応じた workspace 見積り、初期化情報の出力。
