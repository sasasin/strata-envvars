# `GPU_MAX_HW_QUEUES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Strata 自身がこの変数で GPU のキュー上限を設定する実装は見つからない。HIP 版 `strata generate` では、起動時の自動 queue priming を行う前に値を `atoi` で読み、結果が 1 または 2 なら priming を見送って stderr に理由を出す。runtime に渡す設定を Strata が変更するわけではない。この分岐は `STRATA_USE_HIP` かつ `STRATA_HIP_GFX906` ではないビルドに限られる（`engine/src/program/generate.cpp:3474-3487, 3504-3515, 3821-3837`）。

もう一つの用途は、`STRATA_VERIFY_TRACE` が有効なとき、HIP verifier の診断行に現在の値をそのまま表示すること。これは値による verifier の動作変更ではない（`engine/src/core/verify.cpp:336-344, 1245-1260`）。SYCL 側にも同型の HIP 条件付き診断コードがある（`engine/sycl/src/core/verify.cpp:187-194, 800-814`）。

## 値と判定

queue priming の分岐は `std::getenv` の結果が null かどうかを先に確認し、設定されていれば `std::atoi` の戻り値を 1 以上 2 以下と比較する。文字列全体の数値検査やエラー処理はない。従って未設定・空文字・`0`・`3`・`true`・`false`・数値で始まらない文字列はこの条件を満たさない。`1` と `2` のほか、`atoi` が 1 または 2 と読む `01`、`+1`、先頭空白付きの `1`、`1junk`、`2.0` も条件を満たす。大文字小文字比較や範囲 clamp はない。数値変換範囲外の文字列の結果は `atoi` に委ねられ、Strata は検証しない（`engine/src/program/generate.cpp:3508-3513`）。

| 状況 | unset | priming を抑止する値 | 条件を満たさない例 |
|---|---|---|---|
| HIP、`STRATA_HIP_GFX906` 以外、Linux、`STRATA_HIP_QUEUE_PRIME` に非空の指定なし | 自動 priming の候補 | `atoi(value)` が 1 または 2（例: `1`, `2`, `1junk`） | 空文字、`0`, `3`, `true`, `false`, `x` |
| 上記以外の build / OS / backend | この変数による priming 判定なし | 該当なし | 該当なし |
| `STRATA_HIP_QUEUE_PRIME` が非空かつ文字列が厳密に `0` でない | この変数による抑止なし | 該当なし | その指定文字列が queue spec になる |

検証 trace の表示では数値変換をせず、未設定なら `-`、設定済みなら値の文字列をそのまま出す。空文字は空欄として表示される（`engine/src/core/verify.cpp:1252-1257`）。

## 有効になる条件

- priming 判定があるのは `STRATA_USE_HIP` かつ `STRATA_HIP_GFX906` ではない生成経路だけ。CUDA、Metal、通常の SYCL 経路では、この変数による priming 分岐はない（`engine/src/program/generate.cpp:3474, 3821-3837`）。
- `STRATA_HIP_QUEUE_PRIME` が厳密に `0` なら関数は先に戻り、この変数は読まれず、priming 関連の行も出ない。非空で `0` 以外ならその文字列が queue spec となり、`GPU_MAX_HW_QUEUES` の抑止判定を通らない。空の `STRATA_HIP_QUEUE_PRIME` は自動判定経路に進む（`engine/src/program/generate.cpp:3487-3495, 3504-3515`）。
- 自動判定経路でも、Windows では gfx 判定後に priming せず戻る。Linux では対象 GPU の取得に成功し、デバイスが gfx1200 / gfx1201 の場合に自動 spec `nn` を選ぶ。それ以外の GPU では戻る。対象変数が 1 または 2 でも、この gfx12 判定より後の位置で初めて評価される（`engine/src/program/generate.cpp:3490-3515`）。
- `STRATA_VERIFY_TRACE` が空でなく、先頭文字が `0` でない場合に限り verifier の診断行が出る。`GPU_MAX_HW_QUEUES` はその行に記録されるだけで、trace の有効化条件ではない（`engine/src/core/verify.cpp:336-344, 1245-1260`）。
- サーバーは親プロセス環境を基に engine 子プロセス用環境を作り、トップレベル設定の `env` が同名の値を上書きする。`vision.env` は encoder 用環境にさらに重ねられるため、同名を指定すれば encoder 側の継承値を上書きできる。どちらも値は文字列化され、Python サーバーは数値として解釈しない（`terminal/serve/server.py:4007-4028, 4134-4156, 8795, 9422-9423`; encoder 起動時にその環境を渡す箇所: `terminal/serve/server.py:3214-3221`）。
- CLI 引数によるこの変数の優先指定や上書きは見つからない。`--gpu` が設定するのは可視 GPU の環境変数であり、`GPU_MAX_HW_QUEUES` ではない（`engine/src/program/generate.cpp:3781-3802`）。

## 実行時の詳細

`strata generate` の HIP 起動経路は、最初の HIP API 呼び出しより前に queue priming 関数を呼ぶ。変数は関数呼び出しごとに `getenv` され、その場で `atoi` される。static cache はないため、この処理が行われる前の環境変更は読み取られるが、実行中の変更を継続監視はしない（`engine/src/program/generate.cpp:3487-3515, 3821-3837`）。

未設定または `atoi` の値が 1/2 以外なら、自動 spec `nn` の stream を順番に作成し、各 stream で小さな async memset と同期を行ってから stream を破棄し、確保した buffer を解放する。`atoi` が 1/2 ならこの priming 部分をスキップする。`STRATA_HIP_QUEUE_PRIME` の非空指定はこの自動判定を迂回し、文字列の各文字を queue spec として処理する（`engine/src/program/generate.cpp:3494-3515, 3517-3535`）。この環境変数による分岐自体に、token 選択・検証結果・終了状態を変える処理はない。

verifier の診断用途では、値はトレース用メモリの確保処理が走る際に都度 `getenv` される。trace 有効フラグ `g_trace` はプロセス内のグローバル定数として初期化されるが、`GPU_MAX_HW_QUEUES` の表示値はキャッシュされない（`engine/src/core/verify.cpp:336-344, 1245-1257`）。

## ログと測定値

Linux の HIP gfx1200 / gfx1201 自動 priming 経路で `atoi` が 1 または 2 になると、stderr に次の行を出して priming 関数から戻る。明示的な `STRATA_HIP_QUEUE_PRIME` 指定がある場合はこの行を出さない。

```text
strata generate: GPU queues not primed: GPU_MAX_HW_QUEUES=<設定文字列> leaves none for the draft stream (STRATA_HIP_QUEUE_PRIME=nn primes them anyway)
```

同じ自動経路で抑止されなければ、priming 後に `strata generate: opened %zu GPU queues in a fixed order (STRATA_HIP_QUEUE_PRIME=0 turns it off)` を stderr に出す（`engine/src/program/generate.cpp:3508-3512, 3535`）。

HIP verifier では `STRATA_VERIFY_TRACE` が有効で trace メモリ確保処理に入ると、`strata verify trace (#649): on; coherent words ... HIP_HOST_COHERENT=... HSA_ENABLE_SDMA=... GPU_MAX_HW_QUEUES=...` の行に値が含まれる。CUDA 等では HIP 条件の suffix を出さず、`STRATA_VERIFY_TRACE` が無効ならこの行自体を出さない（`engine/src/core/verify.cpp:1245-1260`）。この変数自体による終了・エラー処理はない。

## 根拠

- `engine/src/program/generate.cpp:3474-3535, 3821-3837` — HIP build guard、自動 priming、値判定、stream 処理、ログ、呼び出し位置。
- `engine/src/core/verify.cpp:336-344, 1245-1260` — trace 有効条件と値の診断表示。
- `engine/sycl/src/core/verify.cpp:187-194, 800-814` — SYCL tree にある HIP 条件付き診断表示。
- `terminal/serve/server.py:3214-3221, 4007-4028, 4134-4156, 8795, 9422-9423` — engine 環境と vision encoder 環境への値の引き渡し。
- `engine/src/program/generate.cpp:3781-3802` — `--gpu` の上書き対象が別の環境変数であること。
