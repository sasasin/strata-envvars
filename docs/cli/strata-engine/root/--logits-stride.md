# `--logits-stride`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--logits-stride` |
| 別名 | なし |
| 値 | 正の10進 `int64`。符号、空白、接尾辞なし |

## 役割

`--dump-logits` が保存する logits 行を、位置番号が stride の倍数となる行と最後の入力位置に絞ります。これは保存対象の選択であり、プロンプトの入力位置を飛ばす設定ではありません。既定値 `1` では全位置が選ばれます。【`src/program/generate.cpp:428-429`; `include/strata/program/logits_selection.hpp:9-10,20-28`】

## 使い方

```sh
strata --tokens 1,2,3,4 --max-new 1 --dump-logits /tmp/logits.bin --logits-stride 2
```

これは標準 engine parser の例です。`--tokens` は前処理済み token ID の入力です。stride が 1 より大きいときは `--max-new 1` と `--dump-logits` の両方を指定してください。【`src/program/generate.cpp:810-812,881-882,3286-3288`】

## 値と既定値

- 未指定時は `1` です。【`src/program/generate.cpp:428-429`】
- `parse_stride` は空でない文字列の先頭が数字であること、変換が int64 範囲内で全体を消費すること、値が 0 より大きいことを検証します。したがって `0`、負数、先頭の `+`、空白、数値の後ろの文字列、空文字列、int64 範囲外は受理されません。【`include/strata/program/logits_selection.hpp:11-17`】
- 同一コマンドラインで2回以上指定すると、stderr に `--logits-stride must be supplied only once` を出して終了コード `2` で終了します。無効値も stderr に `--logits-stride requires a positive decimal int64` を出し、終了コード `2` です。【`src/program/generate.cpp:2415-2416,2461-2466`】
- 値が欠けている場合、共通の値取得処理が `--logits-stride needs a value` を stderr に出して終了コード `2` で終了します。【`src/program/generate.cpp:2418-2421`】

## 実行時の動作

engine は `dump_positions = tokens.size() - 1 + max_new` を対象位置数として、0始まりの位置 `pos` ごとに `pos % stride == 0` または最後の位置である場合に logits 行を選びます。最後の位置が stride の倍数でも重複して数えず、出力行数も同じ選択規則で計算します。【`src/program/generate.cpp:7065,7083-7084,15994-15995`; `include/strata/program/logits_selection.hpp:20-28`】

stride が 1 より大きい場合、parser 後の検査で `--max-new 1` かつ `--dump-logits` が必要です。どちらかを欠くと stderr に要件を表示し、終了コード `2` で終了します。stride が 1 の場合、この追加条件はありません。【`src/program/generate.cpp:3286-3288`】

stride が 1 より大きい場合でも、対象外の位置を含む入力位置の計算・条件付けは維持されます。通常の logits 読み戻しは引き続き行われ、`--stream-token` 経路でも選択行を保存する位置では logits を読み戻します。【`include/strata/program/logits_selection.hpp:9`; `src/program/generate.cpp:15994-16001`】

## 適用条件と副作用

- `--dump-logits` と組み合わせた保存行の選別として作用します。オプション単独でファイルを作りません。stride が 1 より大きいときに `--dump-logits` がなければ parser 後の条件検査で拒否されます。【`src/program/generate.cpp:3286-3288,7066-7075`】
- 指定した出力先は `fopen(..., "wb")` で開かれるため、既存ファイルがあれば切り詰められます。ファイルを開けない場合は stderr に `cannot write <path>` を出し、終了コード `1` です。【`src/program/generate.cpp:7071-7074`】
- 出力は先頭に2個の `int32`（語彙数、選択行数）を持ち、その後に各選択位置の `n_vocab` 個の `float` logits が続くバイナリです。ヘッダーは最初の行と同時に書き込まれます。モデル経路が logits の保存位置に到達しない場合は、出力ファイルが空のままになることがあります。【`src/program/generate.cpp:7061-7064,7076-7084,16010-16020`】
- 出力対象位置数または語彙数が `INT32_MAX` を超える場合は、ファイルを開く前に stderr へ `logits dump dimensions exceed int32` を出し終了コード `2` です。ヘッダー・logits の書き込み失敗およびファイルの close 失敗は、それぞれエラーを stderr に出して終了コード `1` になります。【`src/program/generate.cpp:7066-7074,16010-16020,16843-16845`】
- 標準 engine parser より前に Qwen35 family を専用実装へ振り分ける経路があります。その専用 parser の確認範囲には `--logits-stride` の定義がなく、標準 parser と同じ適用を確認できません。従って本書の説明は標準 `src/program/generate.cpp` parser の経路を対象とします。【`src/program/generate.cpp:2393-2407`; `src/qwen35/q36ref.cu:746,761`】
- SYCL 版にも同じ parser 検証、stride と `--max-new` / `--dump-logits` の条件、共有選択 helper の利用があります。【`sycl/src/program/generate.cpp:1802-1808,2452-2455,5621-5622,12254-12256`; `include/strata/program/logits_selection.hpp:20-28`】

## 出力とエラー

生成が完了し dump stream を閉じられた場合、stdout に `logits dumped <path>` が出ます。ファイルを開けない、ヘッダーまたは行を書けない、close に失敗する場合は stderr のエラーと終了コード `1` が記録されています。【`src/program/generate.cpp:7071-7074,16010-16020,16843-16845,17017`】

## 根拠

- `src/program/generate.cpp:418-429` — 既定値を含む `Options`。
- `src/program/generate.cpp:2413-2421,2460-2467` — 標準 parser、重複・値検証・欠落値。
- `src/program/generate.cpp:3286-3288` — stride と `--max-new` / `--dump-logits` の組み合わせ条件。
- `include/strata/program/logits_selection.hpp:9-28` — 正の int64 検証、選択規則、行数。
- `src/program/generate.cpp:7060-7084,15994-16020,16843-16845,17017` — 出力ファイル、位置選択、書き込み・終了時処理。
- `src/program/generate.cpp:2393-2407`、`src/qwen35/q36ref.cu:746,761` — Qwen35 への振り分けと専用 parser の確認範囲。
- `sycl/src/program/generate.cpp:1802-1808,2452-2455,5621-5622,12254-12256` — SYCL 側の対応箇所。

同一 revision の CLI `--help` 実行と Release 配布物の照合は行っていません。記述は指定 commit のソース確認に基づきます。
