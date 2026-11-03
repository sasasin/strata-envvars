# `FNX_ARENA_CHURN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の arena が有効なとき、window ごとに K/V pool の上端を一時的に最大 64 pages 先へ進めて expert slot を RAM に貸し出し、その後、使用中の最上位 page まで戻して slot を再び埋めます。arena 上限が近い場合は前進幅が 64 pages 未満になり、すでに上限なら前進しません。ソースコメントはこれを「a test」と位置づけています。通常の `strata` 実行系で読む環境変数ではありません。

## 値と判定

`fnx::env_flag("FNX_ARENA_CHURN")` が `env_int(name, 0) != 0` を返すかで判定します。`env_int` は設定値全体を符号付き 10 進整数として解析し、末尾まで数字であることと `long long` の範囲内であることを要求します。

| 値 | 判定 |
|---|---|
| 未設定 | 既定値 0 のため無効 |
| `0`, `+0`, `-0`, `00` | 整数 0 のため無効 |
| `1`, `-1`, `2` など、範囲内の 0 以外の整数 | 有効 |
| 空文字、空白、数字以外、整数の後ろに文字がある値、`long long` 範囲外 | 無効扱いへの fallback はせず、`FNX_ARENA_CHURN: '<値>' is not a whole number` の例外 |

先頭・末尾の空白、`1.0`、`1x` は受理されません。先頭の `+` / `-` と先行ゼロは許されます。値が `1` である必要はなく、負数を含む 0 以外の整数は true です。根拠: `src/split/src/env.hpp:15-22,33-40,51-52`。

## 有効になる条件

- `src/split/CMakeLists.txt` が追加する `strata-split-<カード数>` が実行される必要があります。split build は `STRATA_BUILD_SPLIT` が既定 OFF で、Linux CUDA または HIP、GGML CUDA headers などの条件がそろわなければ生成されません（`CMakeLists.txt:2947-2949`, `src/split/CMakeLists.txt:1-30,64-79,92-97`）。通常の `strata` 実行ファイルにはこの読み取り箇所は含まれません。
- `Engine::arena_churn()` は `arena_cap_ == 0` の場合も何もしません。arena は `FNX_ARENA` が未設定または正確に `1` のとき有効で、`0` なら無効です。`FNX_ARENA=0` では churn は発生しません（`src/split/src/model.cpp:1474-1480`, `src/split/src/engine.cu:283-284,338-346,604-609`）。
- `FNX_EXPERT_RAM_GIB=off` と arena の併用はモデル初期化時に拒否されます。その場合は churn 判定に到達しません（`src/split/src/model.cpp:1480-1488`）。
- この変数を読む関数には CLI 引数や設定ファイルによる上書き経路がありません。環境変数の判定結果は `arena_churn()` 内の関数ローカル `static const bool` に保存されます。

## 実行時の詳細

`Engine::verify()`, `Engine::step()`, `Engine::verify_rows()` は、それぞれ window 処理の冒頭で `arena_churn()` を呼びます（`src/split/src/engine_common.cu:777-783,873-883,1049-1065`）。初回の呼び出しで環境値を読み、その後の呼び出しでは保存した判定を使うため、読み取り後の環境変更は反映されません。

判定が true で arena があると、`top` を全 lane の使用中 page の最大上端として求め、現在の pool 上端または `top` の大きい方から `ARENA_STEP`（64 pages）進めた値を `arena_cap_` で制限して `arena_set()` に渡し、その後 `top` に戻します（`src/split/src/engine.cu:438-439,604-614`）。`arena_set()` は各カードを同期してから slot/page の割り当てを切り替え、返却時には expert slot を再充填します。各変更では stderr に `fnx: arena: K/V pool ...` の行を出します（`src/split/src/engine.cu:548-592`）。上限や状態によって `arena_set()` が同じ上端への変更を受けた場合は早期 return し、ログも出しません（同 `:551-553`）。

設定値が不正なら、最初の window で `env_int` が例外を送出します。`sfnx` の失敗経路は stdout に `ERR <例外文>`、stderr に `sfnx: failed: <例外文>` を出して exit code 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1086-1090`）。有効値・無効値の判定だけを知らせる専用ログはありません。

## 根拠

- 候補名の読み取りは `src/split/src/engine.cu:606-607` の一箇所です。`src/split/src/engine.hpp:145` は宣言コメントで、追加の読み取りではありません。
- helper の整数変換と例外: `src/split/src/env.hpp:15-22,33-40,51-52`。
- arena の有効条件と window 前の lend / give-back: `src/split/src/model.cpp:1474-1488`, `src/split/src/engine.cu:283-346,438-439,548-614`。
- 呼び出し箇所と失敗時の観測結果: `src/split/src/engine_common.cu:777-783,873-883,1049-1065`, `src/split/tools/sfnx.cpp:1027-1035,1086-1090`。
