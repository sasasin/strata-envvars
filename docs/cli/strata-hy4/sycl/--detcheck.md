# `strata-hy4-sycl --detcheck`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--detcheck` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される反復回数。正数のとき比較処理を実行する |

## 役割

SYCL runner でモデルと token 列を通常どおり prefill した後、greedy decode で必要なら数 token 進め、同じ token・位置・KV prefix に対する 1 token forward を指定回数実行します。各反復の層ごとの tap と logits を最初の反復とビット単位で比較し、同一入力 step の再現性を確認する診断用オプションです。parser と比較処理はいずれも `engine/src/hy4flash/sycl/sy_main.cpp` にあります。

## 使い方

```sh
# model.strata と ids.txt を使い、同じ decode step を3回実行して比較する
strata-hy4-sycl --model model.strata --tokens ids.txt --detcheck 3
```

`--model`（alias `--native`）と `--tokens` は通常経路で必要です。任意の `--wincheck-skip N` を併用すると、比較対象の step の前に greedy decode で N token 進めます。`--detnotap` を加えると層ごとの tap 保存・比較を省き、logits 比較は継続します（`sy_main.cpp:130-155,170-174,416-455`）。

## 値と既定値

- `--detcheck` の初期値は `0` です。引数を `atoi` で整数化し、値が `> 0` の場合だけ detcheck 分岐を選びます。0、負数、整数に変換できない文字列はこの分岐を無効にします。`atoi` のため、数値の後ろに変換できない文字がある値は数値部分として解釈されます。正の値に対する上限・追加 validation はありません（`sy_main.cpp:97,172,409`）。
- 値を省略すると `nxt()` が `ERR --detcheck needs a value` を stdout に出して終了コード 2 で終了します（`sy_main.cpp:108-115,172`）。
- 同じオプションを複数回指定したときは parser が変数へ順に代入するため、最後の値が残ります（`sy_main.cpp:105-116,172`）。

## 実行時の動作

正数指定時、通常のモデル読み込み・token 読み込み・prefill を終えた後、prefill 最終位置の logits の argmax を次 token とします。`--wincheck-skip` の回数だけ同じ要領で greedy decode を進めた後、次 token を token 列へ追加して比較対象位置を固定します。その同一位置で `forward_chunk(..., 1, ...)` を `--detcheck` 回呼び、各回の logits と、既定では各層の tap を CPU 側へ読み出します。各後続回を最初の回と比較し、float のメモリ表現を `memcmp` して差分を数えます。指定値が `1` の場合は後続反復がなく、比較ループを通らず `DETCHECK REPEATABLE` と表示されます（`sy_main.cpp:409-455`）。

比較診断（`--spec-check`、`--wincheck`、`--detcheck` のいずれかが有効）の前に、プロセス環境変数 `HY4S_VRAM_STATIC=1` を上書き設定します（`sy_main.cpp:300`）。また、分岐の優先順位は `--serve` の早期 return、speculative decode、`--detcheck`、`--wincheck`、通常の `--gen` の順です。そのため `--serve` と併用すると serve 側へ入り detcheck は実行されず、`--draft dfly2` と正の `--gen` によって speculative decode が有効な場合も detcheck 分岐には入りません。正の `--detcheck` は `--wincheck` と `--gen` より先に選ばれます（`sy_main.cpp:215-249,279,379-410,459,527`）。

## 適用条件と副作用

- SYCL runner の通常推論経路が対象です。`--model` が空なら usage を stderr に出して終了コード 2、モデルのロード失敗や prefill / 反復 forward の失敗ならエラーを stderr に出して終了コード 1 で終了します。`--tokens` の読み込み結果が空の場合も `no tokens` を stderr に出し終了コード 2 です（`sy_main.cpp:251-264,266-275,348-350,433`）。
- `--detcheck N` は N 個分の tap 結果と logits を保持する vector を作ります。`--detnotap` は tap の保持と比較を抑えますが、N 回の forward と logits の保持・比較は残ります（`sy_main.cpp:429-455`）。
- tap 比較は両反復に存在する tap と、両方の vector に存在する float の範囲で行われ、tap の個数や各 vector の長さ自体が異なることは差分として数えません。一方、logits は語彙サイズ分を比較します（`sy_main.cpp:445-456`）。
- 通常の推論初期化や prefill は省略されません。通常経路の後段では `top5.txt` を `--out` のディレクトリ（既定 `.`）へ書き込みます。detcheck 自体は `gen_ids.txt` を生成する通常生成分岐には入りません（`sy_main.cpp:93,338-373,409-410,527,603-606`）。
- 正の値の上限がコード上で検証されず、その値に応じたメモリ確保と反復回数になります。極端に大きい値の安全な実行可能性はソース調査だけでは確認できません。

## 出力とエラー

標準出力に `detcheck pos=... repeats=...` を出し、tap / logits に差がある場合は後続反復ごとの差分を出力します。最後に `DETCHECK REPEATABLE` または `DETCHECK NONDETERMINISTIC` を出します。`--detnotap` 有効時は logits に差がない反復の詳細行を省略します（`sy_main.cpp:440-458`）。

比較結果によって終了コードを変える処理はなく、差異があっても detcheck 分岐の後は通常の終了処理へ進みます。SYCL 例外は stderr に `SYCL exception: ...` と出し終了コード 4 です（`sy_main.cpp:603-616`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:97,105-116,170-174` — 初期値、共通の値取得処理、parser 登録。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-254,266-275,279-300` — serve の早期分岐、通常経路の前提、detcheck 有効時の環境設定。
- `engine/src/hy4flash/sycl/sy_main.cpp:409-458` — step の固定、反復、tap / logits の比較と判定表示。
- `engine/src/hy4flash/sycl/sy_main.cpp:603-616` — 通常経路の出力ファイル、SYCL 例外と最終終了コード。
