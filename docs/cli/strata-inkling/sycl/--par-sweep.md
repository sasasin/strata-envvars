# `strata-inkling-sycl --par-sweep`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--par-sweep` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

SYCL Inkling-2-Mini エンジンを読み込んだ後、同じ runner 上で同時 slot 数を 1、4、8、32、64 と変え、各条件の 16 step の推論スループットを測定して表示します。サーバーを起動するフラグではなく、固定入力を使う診断・ベンチマーク経路です。SYCL 版の parser にのみ確認でき、Metal 版の同名オプションの挙動とは別です（`engine/src/inkling2/sycl/ink_sy_main.cpp:101-124`、`engine/src/inkling2/metal/ink_metal_main.cpp:428-457`）。

## 使い方

```sh
# Inkling-2-Mini のモデルを読み込み、SYCL で並列 slot 数を走査する
strata-inkling-sycl --model ./model.strata --par-sweep
```

`--model` は必須です。省略時は usage を標準エラーへ出し、終了コード 1 で終了します（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-169`）。

## 値と既定値

- フラグで、値・別名・数値範囲はありません。引数解析時に `do_par_sweep` を `true` にします（`engine/src/inkling2/sycl/ink_sy_main.cpp:109-124`）。
- 未指定時は sweep を実行しません（同 `:109`）。
- sweep の条件はソースに固定された `{1, 4, 8, 32, 64}` slot、各 `16` step です（同 `:267-269`）。
- `--parallel N`（alias `-p`）も受理されますが、`--par-sweep` 指定時は runner 初期化 slot 数が 64 になります。`--parallel` の値は sweep 中の条件列を変えません（同 `:127`、`:198-201`）。

## 実行時の動作

モデルをロードし、任意の Vision 処理を済ませた後、`do_par_sweep` が真なら 64 slot の runner を初期化します。batch 容量も最低 64 です。Runner は slot 数を 1〜64 に制限し、slot/context/batch に応じた各種 device buffer を確保します。したがって sweep は最大条件に合わせて初期化時から大きな device memory を使用し、`--parallel 1` の通常初期化より使用量が増える場合があります（`engine/src/inkling2/sycl/ink_sy_main.cpp:171-203`、`engine/src/inkling2/sycl/ink_sy_runner.h:223-229`、`:240-266`）。

各条件では対象 slot を reset し、入力 token に prompt の要素を循環利用して初期 token を作ります。最初の forward を warmup として行った後、16 回、直前の argmax token を次の入力にして forward します。これらの forward は speculative/D-Spark 記録を無効にして実行します。経過秒数から `agg_tps = slot数 × 16 / 秒数` と `per_req_tps = agg_tps / slot数` を算出し、条件ごとに `[PAR-SWEEP]` 行を標準出力へ出します（`engine/src/inkling2/sycl/ink_sy_main.cpp:267-285`）。

この測定ループは `--gen` の生成数を使わず、`--prompt-tokens` / `--prompt-ids` で与えた token 列は各 slot の初期入力に使います。空の列になった場合は既定 token 列 `{1,2,3,4,5,6,7,8}` を使います（同 `:103-105`、`:144`、`:206-207`、`:272-280`）。`--no-dspark` は runner 初期化時の D-Spark 有効化に作用しますが、sweep の forward 自体は D-Spark を記録せず実行します（同 `:110`、`:201`、`:275-280`）。

## 適用条件と副作用

- 対象は `strata-inkling-sycl` の SYCL 経路です。モデルのロードと runner/device buffer の初期化を行うため、モデルファイルと利用可能な SYCL device が必要です。ロード失敗時は `[ERROR]` を標準エラーに出して終了コード 1 になります（`engine/src/inkling2/sycl/ink_sy_main.cpp:171-184`）。
- `--info` はモデル情報を probe して出力した後、runner 初期化より前に終了するため、同時指定しても sweep には到達しません（同 `:173-180`）。
- `--selfcheck`、`--spec-check`、`--bench` は sweep より前に処理されます。同時指定するとそれらの処理後に sweep も実行します（同 `:209-265`）。`--vision` と `--image` の両方がある場合も、Vision のロード・画像 encoding が sweep に先行します（同 `:185-196`）。
- sweep の各 forward は `forward_batch` の戻り値を検査していません。runner 実装で確認できる明示的な `false` 条件は `M <= 0` または `M > max_batch` ですが、この sweep では `M` が slot 数以下で batch 容量は最低64です。ほかの device 実行失敗時の伝播・表示方法は、この呼び出し側のソースだけでは確定できません（`engine/src/inkling2/sycl/ink_sy_main.cpp:275-280`、`engine/src/inkling2/sycl/ink_sy_runner.h:421-428`）。

## 出力とエラー

各設定の測定結果を stdout に `[PAR-SWEEP] c=... steps=16 dt=... agg_tps=... per_req_tps=...` 形式で表示します（`engine/src/inkling2/sycl/ink_sy_main.cpp:281-285`）。`--par-sweep` 固有の入力値 validation やエラー出力はありません。正常に最後まで到達した場合、main は終了コード 0 を返します（同 `:288`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — SYCL CLI の引数 parser、`--par-sweep` の boolean 設定、`--parallel`・prompt 関連オプション。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-203` — 必須モデル確認、ロード、sweep 時の 64 slot 初期化と runner 起動。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:206-207,257-285` — prompt 既定値、先行 benchmark 処理、sweep の slot/step 列・測定と表示。
- `engine/src/inkling2/sycl/ink_sy_runner.h:223-229,240-266` — runner slot/context/batch 上限と buffer 初期化。
- `engine/src/inkling2/sycl/ink_sy_runner.h:421-428` — `forward_batch` の batch 範囲チェックと失敗戻り値。
