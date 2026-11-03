# `FNX_HC1`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next split engine の hyper-connection read で、何行まで one-barrier 形式の CUDA/HIP kernel を使うかを指定します。`FNX_HC1=0` はこの形式を使わず、1〜8 は `T` 行の read について `T <= FNX_HC1` のときに使います。Engine 構築時に値を検査し、実際の各 `hc_read` で `T` と閾値を比べて kernel variant を選びます。

## 値と判定

| 環境値 | 判定・結果 |
|---|---|
| 未設定 | 既定値 `3`。1〜3 行の read が one-barrier 形式の候補。 |
| 整数 `0` | 有効。`T <= 0` となる read はないため、one-barrier 形式を選ばない。 |
| 整数 `1`〜`8` | 有効。`T` が値以下で、かつ `T <= 8` の read に one-barrier 形式を使う。 |
| 負数または `9` 以上 | `FNX_HC1: 0 (off) .. 8 rows, got <値>` の `std::runtime_error`。 |
| 空文字、数字以外、前後の空白や数字の後ろに文字がある値 | `env_int` の全体整数 parse に失敗し、`FNX_HC1: '<値>' is not a whole number` の `std::runtime_error`。 |
| `long long` の範囲外 | `strtoll` の範囲エラーとなり、同じ `is not a whole number` エラー。 |

整数は基数10で、先頭の `+` または `-` を許します。値全体を消費する必要があるため、`3x`、` 3`、`3 ` は無効です。空文字は未設定扱いにならず parse error です。CLI 引数や別の設定値による上書きはありません。`FNX_HC1` の直接参照は `hc1_rows()` の一箇所です。

## 有効になる条件

- `src/split` の Flash-Next split engine を使う実行経路が対象です。CMake は `kernels.cu` を CUDA または HIP の `strata-split-*` 実行ファイル向けにコンパイルします。
- `hc_read()` の `T` が 1〜8 で、かつ設定値以下のときだけ one-barrier variant が選ばれます。値が 8 でも、9 行以上は通常 variant です。
- 値が 0 の場合も環境値として有効ですが、通常の read 行数では one-barrier variant は選ばれません。
- 他の環境変数、OS、CLI オプションによる別の閾値選択は見つかりませんでした。

## 実行時の詳細

`Engine` のコンストラクターが `hc1_rows()` を呼び、graph capture 内の最初の hyper-connection read まで検査を遅らせない実装です。`hc1_rows()` は正常に parse された結果を function-local `static const` に保持します。したがって値は最初の正常な評価後にプロセス内で cache され、以後の Engine や read で環境を変更しても再読込されません（初回評価が例外になった場合は C++ の static 初期化が完了しないため、次の呼び出しで再評価されます）。

`hc_read()` は毎回 `T <= hc1_rows()` を判定し、`T <= 8` の場合に条件を満たすと `k_hc<T, true, ...>` を起動します。one-barrier variant は down 部分の grid barrier 後、各 block が partials から low projection を作り、そのまま up 部分へ進みます。通常 variant は reduce の後にもう一度 grid barrier を使ってから up 部分に進みます。どちらも同じ `hc_read` の出力を計算する経路として実装されています。

値が無効なら Engine の構築中に例外になります。`fnx_run` は `fnx_run: <例外文>` を stderr に出して終了コード 1、`sfnx` は `ERR <例外文>` を stdout に出し、`sfnx: failed: <例外文>` を stderr に出して終了コード 1 で終了します。値の選択自体について通常時のログはありません。

## 根拠

- `src/split/src/env.hpp:15-21,33-40` — 符号付き base-10 整数の全体 parse、未設定時の fallback、parse error。
- `src/split/src/kernels.cu:1145-1153` — 既定値 3、0〜8 の範囲検査、static cache。
- `src/split/src/engine.cu:31-32,62-68` — Engine 構築時の検査呼び出し。
- `src/split/src/kernels.cu:1196-1230` — read ごとの閾値判定と `T` ごとの launch dispatch。
- `src/split/src/hc.cuh:110-115,239-309,382-393` — one-barrier と通常形式の kernel variant および barrier の違い。
- `src/split/CMakeLists.txt:81-109` — kernel source の分割コンパイルと HIP build の設定。
- `src/split/tools/fnx_run.cpp:1365-1372`、`src/split/tools/sfnx.cpp:1030-1035,1054-1062` — Engine 構築時例外の出力と終了経路。
