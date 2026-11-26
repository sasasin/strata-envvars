# `FNX_HC_BAR_WRAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、Flash-Next split engine の hyper-connection read が使う grid barrier counter を、指定回数後に周回する位置へ初期化する診断用フックです。各カードの `hc_prepare` が counter を 0 にした後、`hc_preset_barrier` が scratch の末尾にある counter を `mod - n * grid` に設定します。barrier は read ごとに2回使われます。通常の未設定時は counter を 0 のまま使い、モデル計算や barrier counter の初期周回位置を変えません（`engine/src/split/src/engine.cu:181-188`、`engine/src/split/src/kernels.cu:1186-1190,1203-1207,1230-1236`、`engine/src/split/src/hc.cuh:26-28,69-91`）。

このフックがあるのは `strata-split` の Engine 実装です。これは CMake で opt-in の別エンジンで、split engine は CUDA または HIP のビルド時に構成されます。通常の `strata` エンジン向け設定ではありません（`engine/CMakeLists.txt:922-925`、`engine/src/split/CMakeLists.txt:1-5,20-27,76-101`）。

## 値と判定

Engine の各カードの scratch を確保・準備した直後に、まず `std::getenv` の非 null 判定を行い、設定されていれば `env_int` で符号付き十進整数として全体を parse します。`env_int` は未設定だけ既定値を返します。設定値は空でない任意文字列として扱われず、空文字も parse エラーです（`engine/src/split/src/engine.cu:181-187`、`engine/src/split/src/env.hpp:15-21,33-40`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| Split engine の各カード | `getenv` が null なら counter を `hc_prepare` が書いた 0 のままにする | `n` が正の整数で、かつそのカードの `floor(0xffffffff / g)` 以下。`g` はそのカードの barrier grid 数（`hc_grid()`） | 空文字、`1x`、前後の空白、整数範囲外は `env_int` の parse error。`0` と負値、`0xffffffff` より大きい値は `FNX_HC_BAR_WRAP` の範囲エラー。さらに正値でも `floor(0xffffffff / g)` を超える値は `hc_preset_barrier` が拒否 |

parse は `strtoll(..., 10)` で、符号 `+` / `-` と数字列を受け付けますが、先頭文字を事前確認し、parse 後に文字列末尾まで消費されたことと `ERANGE` でないことを検査します。したがって `+1`、`01` は parse 可能、` 1`、`1 `、`0x10`、`1anything`、空文字は parse できません。parse できても `n <= 0` は拒否されます。`hc_preset_barrier` 側の上限は `hc_bar_mod(g) / g`、`hc_bar_mod(g) = floor(0xffffffff / g) * g` なので、整数上限だけでなくカードごとの grid 数によっても異なります（`engine/src/split/src/env.hpp:15-21,33-40`、`engine/src/split/src/engine.cu:184-187`、`engine/src/split/src/hc.cuh:26-28`、`engine/src/split/src/kernels.cu:1230-1236`）。

## 有効になる条件

- `strata-split` がビルドされ、その `fnx::Engine` が作られる必要があります。split build は `STRATA_BUILD_SPLIT` の opt-in で、CUDA/HIP の split engine に含まれます（`engine/CMakeLists.txt:922-925`、`engine/src/split/CMakeLists.txt:20-27,76-101`）。
- `sfnx` サーバーは起動時に Engine を構築するため対象です（`engine/src/split/tools/sfnx.cpp:1117-1135`）。`fnx_run` は `lab_mode` の `exact`、`read`、`batch`、`compare`、`decode`、`bdecode`、`cache2` では Engine を作らず早期 return するため、この変数を読みません。それ以外で Engine 構築に進むモードは対象です（`engine/src/split/tools/fnx_run.cpp:960-962,978-988`）。
- モデル状態や Engine 作成モードによる値の上書きはありません。値は GPU scratch の準備後にカードごとに適用され、別の CLI 引数や環境変数との優先順位分岐はありません（`engine/src/split/src/engine.cu:156-188`）。

## 実行時の詳細

Engine constructor は各カードで `hcs` scratch を device allocation し、`hc_prepare` で grid を設定して barrier counter を 0 にします。その後、変数が設定されている場合は整数を読み、範囲を確認して `hc_preset_barrier` を呼びます。関数は現在のカードの grid `g` と `mod = hc_bar_mod(g)` を取り、`1 <= barriers_left <= mod / g` を確認したうえで `mod - barriers_left * g` を scratch の counter へ同期コピーします。barrier counter は modulo `mod` で増え、各 barrier の到着数が grid の block 数 `g` なので、指定した barrier 数の後に周回する状態を作ります（`engine/src/split/src/engine.cu:181-188`、`engine/src/split/src/kernels.cu:1173-1190,1230-1236`、`engine/src/split/src/hc.cuh:26-28,69-91`）。

設定有無と値の取得は Engine constructor 中に行われ、関数内 static cache はありません。各カードを処理するときに読み直します。unset 時は `hc_prepare` の 0 初期化のみで、preset 呼び出しはありません。CLI 引数による上書きはありません（`engine/src/split/src/engine.cu:156-188`）。

## ログと測定値

成功時にこの変数専用の有効化ログはありません。変数が設定されて空・非整数なら helper が `FNX_HC_BAR_WRAP: '<値>' is not a whole number` の例外を投げます。整数だが 0 以下、32 bit unsigned 上限超過なら `FNX_HC_BAR_WRAP: want a barrier count > 0, got <n>`、barrier grid に対する上限超過なら `hc_preset_barrier: barriers_left must be 1..<上限>` が例外になります。device copy が失敗した場合は `hc_preset_barrier: <CUDA/HIP runtime error text>` です（`engine/src/split/src/env.hpp:33-40`、`engine/src/split/src/engine.cu:184-187`、`engine/src/split/src/kernels.cu:1230-1236`）。

`sfnx` の Engine 構築中に失敗すると stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1097-1103,1122-1136`）。`fnx_run` の CLI では stderr に `fnx_run: <理由>` を出し、終了コード 1 です（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。barrier が実行時に timeout すると device 側で `err` の bit 4 が立つ実装ですが、この環境変数自体が timeout を発生させるとの記述や測定値は確認できません（`engine/src/split/src/hc.cuh:11-14,73-89`）。

## 根拠

- 全参照検索: 実コードは `engine/src/split/src/engine.cu:184-187` のみ。`engine/src/split/src/kernels.hpp:72-73` はコメント内の参照。
- 値の変換: `engine/src/split/src/env.hpp:15-21,33-40`。
- counter の上限・初期値・更新: `engine/src/split/src/hc.cuh:26-28,69-91`、`engine/src/split/src/kernels.cu:1173-1190,1230-1236`。
- Engine および実行経路: `engine/CMakeLists.txt:922-925`、`engine/src/split/CMakeLists.txt:20-27,76-101`、`engine/src/split/tools/sfnx.cpp:1117-1135`、`engine/src/split/tools/fnx_run.cpp:960-988,1364-1373`。
- 設計資料 `docs/DETAILS.md` にこの変数の記載は見つかりませんでした。ここでは現行ソースのコメントと実装だけを根拠にしています。
