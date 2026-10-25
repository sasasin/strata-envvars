# `STRATA_Q36_DRAFT_VOCAB`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソースコード。外部ライブラリの環境変数は対象外。

## 役割

Qwen3.6-35B-A3B 用エンジンの MTP draft head が候補にする語彙行数を指定します。値が正の数 `N` なら、draft は出力行列の先頭 `N` 行（低い token ID 側）だけで候補 token を選びます。これは draft 候補の制限であり、通常の greedy 結果をその範囲に制限するものではありません。検証 window が draft を採用するか決め、範囲外 token が正解なら draft が棄却されます。

環境変数を読むのは `src/qwen35/q36_engine.cu` の Qwen3.6 エンジン初期化経路だけです。`strata` は GGUF の model family が `qwen35moe` のときこのエンジンへ切り替わります。他の model family ではこの設定を読むコード経路に入りません。

## 値と判定

環境変数は `std::atoi` で変換し、文字列全体の妥当性検証はしません。値は `--draft-vocab` CLI 引数より優先度が低く、CLI 引数が指定されて値が 0 以上なら環境変数は参照されません。

| 入力 | 結果 |
|---|---|
| `--draft-vocab` が 0 以上 | CLI 値を使用。環境変数は読まない |
| CLI 引数なし（初期値 `-1`）または CLI 値が負 | 環境変数が設定されていれば `atoi` の結果を採用 |
| CLI が負で、環境変数も未設定 | 最終的な `draft_n` は 0 |
| CLI が負で、環境変数が空または数値変換できない文字列 | `atoi` が 0 を返し、最終的な `draft_n` は 0 |
| 変換結果が負 | `std::max(0, ...)` により 0 |

`atoi` は数値の前にある空白と符号を扱い、数値の後ろに続く文字列を検査しません。したがって、たとえば `128junk` は 128、`junk128` は 0 になります。変換範囲外の値について、ソースは追加の検証を行いません。

`draft_n == 0` は「候補を 0 個にする」意味ではなく、全語彙を使う設定です。また `draft_n >= 語彙数` や 8 の倍数でない値も、subset 専用計算の条件を満たさないため全語彙を使う経路にフォールバックします。

## 有効になる条件

環境変数値が設定されても、次の条件が必要です。

- Qwen3.6-35B-A3B (`qwen35moe`) のエンジン経路を実行している。
- モデルに MTP block があり、`--mtp N` で 1〜7 draft を有効にしている。MTP がないモデルでは `E.mtp_d` は 0 になり、draft head は使われません。
- draft head の subset 計算にはさらに `fast_k` が有効、値が `0 < draft_n < n_vocab` かつ 8 の倍数、出力 head の型が 8、入力幅が埋め込み幅と一致、`N / 32 == 64` という条件が必要です。これらの条件を満たさない場合、エンジンは全語彙に対する `head_rows()` を呼びます。

`--draft-vocab` に 0 以上を指定した場合は環境変数より優先されます。CLI の `--draft-vocab -1` のように負値を渡すと環境変数への fallback が起きます。

## 実行時の詳細

`run()` の CLI 解析時に `draft_vocab` は `-1` で初期化され、`--draft-vocab` があれば `atoi` の結果に置き換わります。モデル初期化後、MTP draft 数の設定と同じ初期化区間で、`draft_vocab < 0` の場合だけ環境変数を読み、`E.draft_n = std::max(0, draft_vocab)` に保存します。以降は `head_draft()` がその値を使います。各 generation request ごとに環境を読み直す処理はなく、プロセス起動後の環境変更は反映されません。

subset 経路では先頭 `draft_n` 行の logits で argmax を取り、draft token を提案します。条件を満たさない場合は同じ `head_draft()` から全語彙の logits と argmax を計算します。検証側が提案を棄却した場合も、最終回答は通常の greedy 結果です。この環境変数を読んだことを示す専用ログやエラー出力は実装にありません。

## 根拠

- `src/program/generate.cpp:2253-2265` — model family を見て Qwen3.6 エンジンへ切り替える。
- `src/qwen35/q36_engine.cu:3732-3738,3764-3772` — `run()` と `--draft-vocab` の解析、初期値。
- `src/qwen35/q36_engine.cu:2104-2128` — draft subset の意味、条件判定、全語彙 fallback。
- `src/qwen35/q36_engine.cu:3880-3885` — 環境変数の読み取り、CLI fallback、0 未満の clamp、MTP 有効条件。
