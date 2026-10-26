# `GDN_PROBE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`GDN_PROBE` は通常の Strata 実行時設定ではなく、Metal の `gdn_prompt_parity` テストの `--bench` 経路から GDN prompt scan kernel に渡す診断用 function constant の値です。テスト経路は値を `gdn_prompt.metal` の `gdn_probe` に渡し、値 `1` で simdgroup 間の部分和の集約を、値 `2` で状態更新を省略します。カーネルのコメントは `1` を誤った結果になる probe としています。

リポジトリ全体での完全一致検索では、環境変数を読む箇所は `metal/tests/gdn_prompt_parity.cpp` の1箇所だけです。Metal kernel には同名の function constant 宣言がありますが、環境変数は読まず、テスト側が値を設定します。製品実行コードがこの環境変数を読む根拠は確認できません。

## 値と判定

テスト側は `std::getenv("GDN_PROBE")` が null なら `0`、設定されていれば `std::atoi` の結果を function constant index 6 に設定します。文字列全体の厳密な数値 parse やエラー判定はありません。

| 環境変数の状態 | テストが渡す値 |
|---|---|
| 未設定 | `0` |
| 空文字 | `0`（`atoi` が数字を読めないため） |
| 数字列を含む値 | `atoi` が先頭の空白と符号の後から読む数字列を整数に変換し、数字列の後ろは無視する（例: `2abc` は `2`、`-1` は `-1`） |
| 数字を読めない値 | `0` |

カーネルでは `gdn_probe != 1` のとき部分和を threadgroup memory に書き、他 simdgroup の値を加算します。`gdn_probe == 1` のときこの集約を飛ばします。`gdn_probe != 2` のとき state の更新ループを実行し、`gdn_probe == 2` のとき更新を飛ばします。それ以外の整数値（負値を含む）はこれらの分岐を無効化し、通常の処理を残します。

## 有効になる条件

- `metal/tests/gdn_prompt_parity` を `--bench` 付きで実行する必要があります。`--bench` がない経路の parity 検査ではこの環境変数を読みません。そちらは row-block scan 用の pipeline に function constant `0` を明示設定します。
- ベンチマーク側で `cb < 0` かつ `nm[9] != 'v'` の場合に環境変数を読み、constant index 6 を設定します。ループ内で pipeline を作るたびに読み直すため、値を static cache するコードではありません。
- 値が `1` または `2` の場合、上記の kernel 処理を意図的に省略します。通常の正しさ検証用設定として扱うべき値ではありません。
- `metal/kernels/gdn_prompt.metal` の function constant が設定されない場合、`is_function_constant_defined(GDN_PROBE) ? GDN_PROBE : 0` により kernel 内の `gdn_probe` は `0` です。

## 実行時の詳細

テストは `--bench` の有無を argv から決め、ベンチマーク時は通常の parity loop を飛ばしてから decode step と scan variant の時間を計測します。ベンチマーク loop で `GDN_PROBE` を整数変換し、`mtl::Constants::i(6, ...)` で値を設定して `gdn_scanr_4` などの pipeline を作成します。`gdn_prompt.metal` は index 6 の function constant を `GDN_PROBE` として宣言し、scan kernel の集約・状態更新分岐に使います。

この環境変数自体について、実行中の製品プロセス、子プロセスへの転送、リクエスト単位の再評価を行うコードは見つかりませんでした。環境変数を読むテストコードは `metal/tests/` にあります。

## 根拠

- `metal/tests/gdn_prompt_parity.cpp:23-26` — `--bench` の判定と Metal library のコンパイル。
- `metal/tests/gdn_prompt_parity.cpp:93-101` — parity 経路では row-block pipeline に function constant `0` を設定。
- `metal/tests/gdn_prompt_parity.cpp:142-174` — ベンチマーク経路、`getenv` / `atoi` による値の読み取り、index 6 への設定、pipeline 作成と計時。
- `metal/kernels/gdn_prompt.metal:154-156` — function constant 宣言と未設定時の既定値 `0`。
- `metal/kernels/gdn_prompt.metal:209-225` — 値 `1` による部分和集約の省略、値 `2` による state 更新の省略。
