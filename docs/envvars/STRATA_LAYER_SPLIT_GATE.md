# `STRATA_LAYER_SPLIT_GATE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

自動レイヤー分割 (`--layer-split auto`) の開始可能性チェックが使う値を、標準エラーに診断行として出します。分割探索そのもののゲートを有効・無効にする設定ではありません。探索はこの変数が未設定でも同じ条件で候補を除外し、どの配置も開始可能でないときにはゲートを外して再探索します。

このコードは `src/program/generate.cpp` にある CUDA の複数 GPU レイヤー分割経路です。`multi_gpu && split_auto` のときだけ探索に入り、その候補チェックが `can_start()` を呼んだときにこの診断判定が行われます。

## 値と判定

| 状態 | 診断出力 |
|---|---|
| 未設定 | 出さない |
| 設定あり（空文字を含む） | 出す |

値の内容は読みません。`std::getenv(...) != nullptr` だけで判定するため、`0`、`false`、任意の文字列でも設定されていれば有効です。判定結果は関数内の `static const bool` に保存され、プロセス内で最初に `can_start()` が実行された後の環境変更は反映されません。

## 有効になる条件

- `--layer-split auto` を用いる複数 GPU の実行経路であること。
- 起動可能性ゲートの `can_start()` が呼ばれること。候補の評価・比較のタイミングで呼ばれ、全候補の各評価について必ず出るわけではありません。
- そのプロセスで最初の `can_start()` より前に環境変数が設定されていること。

これはログだけを制御します。`can_start()` は、各 stage が選択 chunk をキャッシュから貸せるか、貸せない場合に自身の prompt buffer 用メモリを確保できるかを判定します。探索は 512-token chunk を最後の手段として調べ、選択 chunk が 0 の場合は各 stage が 256-token 分の buffer と 1,536 MiB の余裕を持てるかを判定します。chunk を貸す場合は slot 数の見積もりも確認し、貸せない stage には選択 chunk の buffer と同じ余裕を要求します。これらの判定条件は変数の設定有無によって変わりません。

## 実行時の詳細

設定時、`can_start()` は `stderr` に `gate: K=... chunk=...` と各 stage の診断情報を一行で出します。stage ごとの項目は CUDA device、layer 開始位置 (`lb`)、保持 slot 数 (`cnt`)、使用量 (`used`)、容量 (`cap`)、残り容量 (`room`)、chunk の必要量 (`need`)、必要 slot 数の見積もり (`slots`) です。MiB 表示は byte 値を右シフトして整数化しています。chunk が 0 のとき `need` と `slots` は 256-token chunk で算出します。`K` は2 GPU時だけ第2 stage の layer 境界を表示し、3 GPU以上では 0 です。

どの配置も prompt path を開始できない場合は、通常の `stderr` メッセージ `strata generate: layer split auto: no placement can start the prompt path on the figures here; choosing by decode speed alone` を出し、ゲートなしで再探索します。この fallback と最終的に選ばれる配置への診断も、`STRATA_LAYER_SPLIT_GATE` の設定による違いはありません。

## 根拠

- `src/program/generate.cpp:3647-3649`: 複数 GPUかつ `split_auto` の自動探索条件。
- `src/program/generate.cpp:3797-3801`: ゲートが prompt path の開始可能性を調べ、512-token chunk を基準にする意図。
- `src/program/generate.cpp:3842-3901`: chunk と slot 数の算出、および開始可能性の判定。
- `src/program/generate.cpp:3875-3887`: 環境変数の設定有無による `stderr` 診断行。
- `src/program/generate.cpp:3929-3933,4020-4034,4142`: 候補選択と近似候補の評価におけるゲート呼び出し。
- `src/program/generate.cpp:4099-4106`: 開始可能な配置がない場合のゲート解除と再探索。

`STRATA_LAYER_SPLIT_GATE` の説明は `docs/DETAILS.md` および関連する設計資料では確認できませんでした。上記は対象 commit の実装から確認できる範囲です。
