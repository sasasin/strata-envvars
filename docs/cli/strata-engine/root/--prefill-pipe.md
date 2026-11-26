# `strata` エンジン引数 `--prefill-pipe`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` によるサーバーモードを含む） |
| オプション | `--prefill-pipe` |
| 別名 | なし |
| 値 | 数値 `R`。`0` は無効、`0<R≤1` は均等化規則、`R>1` は `b/a` のトークン換算値 |

## 役割

layer split（複数段の GPU に層を分けた構成）で、プロンプトを読むときの chunk サイズを pipeline 向けに計画する opt-in 設定です。第1段が次の段と読み取りを重ねられるよう、プロンプト長、段数、バッファ上限および `R` から chunk を選びます。単一段では計画関数が無効値を返すため、この指定による chunk 変更はありません（`engine/src/prefill/prefill.cpp:3683-3687`）。

## 使い方

```sh
# サーバー起動引数で R=1 の均等化規則を指定（layer split 時に適用）
strata --native MODEL.gguf --serve --prefill-pipe 1

# 機材の b/a をトークン単位で指定する例（1024 は例示値）
strata --native MODEL.gguf --serve --prefill-pipe 1024
```

`--serve` を付けない通常のエンジン実行にも指定できます。`R>1` の値は機材ごとに異なるため、例の `1024` を推奨値として扱わないでください。エンジン自身が実測して値を決める処理は確認できません。

## 値と既定値

- 省略時は内部値 `-1` のままです。起動時に明示指定がなければ `STRATA_PREFILL_PIPE` を読み、未設定または空なら `0`（無効）になります（`engine/src/program/generate.cpp:995-998`、`engine/src/prefill/prefill.cpp:3615-3625`）。明示指定時は `Prefill::set_pipe` に設定され、環境変数より優先します（`engine/src/program/generate.cpp:6830`、`engine/src/prefill/prefill.cpp:3618-3625,3637-3639`）。環境変数の独立した調査文書はありません。
- `0` は無効、`0<R≤1` はすべて同じ均等化規則、`R>1` は機材の `b/a` 比（トークン単位）として扱われます。従って `0.5` と `1` は同じ規則です（`engine/src/prefill/prefill.cpp:3683-3687`）。
- `R≤1` の均等化は、現在のバッファ上限での chunk 数が複数あり、最後の短い chunk が `stream_all_min()` 以上の場合にだけ候補 chunk を均等化します。それ以外はバッファ上限を使います（`engine/src/prefill/prefill.cpp:3647-3659`）。
- `R>1` では候補 chunk 数のコストを比較し、256-token grid と最小 chunk floor を使って候補を評価します。現在の分割より少なくとも 3%低いコストにならなければ分割を変えません。最小 chunk floor は `STRATA_PREFILL_PIPE_FLOOR`（既定 512、256-token grid に切り上げ、256..4096 に clamp）で決まり、候補 chunk 数の探索上限は通常 64 ですが、バッファ上限ですでに必要な最小 chunk 数は下回りません。ratio は整数 token に丸め、計算では最大 `2^20` に制限されます（`engine/src/prefill/prefill.cpp:3627-3634,3641-3642,3647-3676`）。
- parser は `std::atof` で変換し `std::max(0.0, ...)` を適用します。厳密な数値形式・上限の validation はなく、変換できない値は `atof` の結果 `0` として無効扱い、負値も `0` になります。引数を省略すると stderr に `--prefill-pipe needs a value` を出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3847,4033`）。同じ引数を複数回指定した場合は parser のループで後の指定が `o.prefill_pipe` を置き換えます（`engine/src/program/generate.cpp:3842-3847,4033`）。

## 実行時の動作

- `--prefill` 等により決まる実バッファ chunk `cap` と段数を使い、第1段が prompt segment 全体の長さ `n` に対して一度 chunk を計画します。pipe が無効、段数が 1、または後段の場合は計画を使いません（`engine/src/prefill/prefill.cpp:3683-3687`）。
- 計画 chunk が選ばれると、その segment の各実行部分へ同じ chunk と計画状態を引き継ぎます。serve 中に分割読込・BYIELD・checkpoint から再開する場合も、保存された計画が現在の段数上限内で、pipe 設定キーも一致すれば再利用します。不一致時は stderr に再計画の通知を出します（`engine/src/program/generate.cpp:20769-20810`）。
- Serve の request tuning に `pipe` があると、その request の設定が起動時設定より優先されます。各 request の開始時に値が設定され、次の request に持ち越されません（`engine/src/program/generate.cpp:18864-18865,18922-18926,18943`）。Terminal server は `strata_tune.prefill_pipe` が bool 以外の数値かつ `0..262144` の場合に `pipe=` キーへ変換します（`terminal/serve/server.py:1388-1398`）。
- planned chunk が通常のバッファ chunk より小さい読み取りでは stderr に `strata prefill: ... (--prefill-pipe ...)` の計画行を出します。また serve の monitor 用 stdout `INFO` 行には実効 `prefill_pipe` 値が含まれます（`engine/src/prefill/prefill.cpp:3694-3700`、`engine/src/program/generate.cpp:16179-16223`）。
- pipe 計画由来の chunk では、CPU pool が存在し、CPU share が有効で、他条件も満たす場合でも、その読み取りの CPU share は取得しません。段間で chunk が重なるためです（`engine/src/prefill/prefill.cpp:4299-4302,4630-4640`）。

## 適用条件と副作用

この設定が chunk 計画に反映されるのは複数段の layer split の第1段です。layer split のない実行では値は受理されますが、`plan_chunk()` が `0` を返してバッファ chunk の動作が続きます。GPU/backend ごとの数値推奨や性能向上の保証はソースから確認できません（`engine/src/prefill/prefill.cpp:3683-3687`）。

## 出力とエラー

- 引数値がない場合は stderr に `--prefill-pipe needs a value` を出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3847`）。
- 実際に計画 chunk が通常の上限より小さくなると、計画内容を stderr に出力します。起動時 `INFO` 行の `prefill_pipe` は stdout に出ます（`engine/src/prefill/prefill.cpp:3694-3700`、`engine/src/program/generate.cpp:16200-16223`）。
- 不正な数値文字列を専用エラーとして拒否する分岐は parser にありません。`atof` と非負クランプの結果が使われます（`engine/src/program/generate.cpp:4033`）。

## 根拠

- `engine/src/program/generate.cpp:995-998,1377-1383` — オプションの内部既定値と help の説明。
- `engine/src/program/generate.cpp:3842-3847,4033,6830` — 引数取得、変換・クランプ、起動時の反映。
- `engine/src/prefill/prefill.cpp:3615-3644` — CLI／`STRATA_PREFILL_PIPE`／request 値の優先順位と設定値の変換。
- `engine/src/prefill/prefill.cpp:3627-3634,3647-3687` — floor の既定値・clamp、chunk 選択規則、3% 条件、段数・第1段の適用条件。
- `engine/src/program/generate.cpp:18864-18943,20769-20810` — request ごとの上書き、計画の作成・再利用。
- `terminal/serve/server.py:1388-1398` — Terminal server から request tuning を転送する条件。
- `engine/src/prefill/prefill.cpp:4295-4302,4630-4640` — 計画 chunk の適用と CPU share 条件。
- `engine/src/prefill/prefill.cpp:3694-3700`、`engine/src/program/generate.cpp:16200-16223` — stderr の計画ログと stdout の起動情報。
