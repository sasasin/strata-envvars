# `FNX_PF_HCSPLIT_F16`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA split prefill の hyper-connection split がカード間で交換する `mixed` 行を f16 形式にし、受信したカードが f16 に丸めた値を f32 に戻して使う設定です。f32 で交換する既定経路と比べ、交換する行データは半分のバイト数になります。両カードで所有行も含めて同じ f16 値を使うようにしています。これは転送形式と後続計算に使う値を変える設定で、生成結果の一致は保証されません。`Pf` の初期化と `Engine::prefill_pass` の split read 経路に実装されています（`engine/src/split/src/prefill.cu:440`, `1095-1109`, `1541-1563`, `1587-1592`）。

## 値と判定

`fnx::env_int("FNX_PF_HCSPLIT_F16", 0)` が `std::getenv` で取得し、`parse_whole` が文字列全体を base 10 の `long long` として解析します。未設定は既定値 `0`。解析後は `!= 0` で判定するため、`0` は無効、正負を問わずゼロ以外は有効です。空文字、空白、数字以外の接尾辞、範囲外は `env_int` の例外です（`engine/src/split/src/env.hpp:15-22`, `33-40`; 呼び出し `engine/src/split/src/prefill.cu:1099`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HCSPLIT 初期化まで到達した場合 | `0` として無効 | `1`, `-1`, `2`（整数として解析でき、ゼロ以外） | `0` |
| 整数として解析できない値 | 該当なし | 該当なし | 空文字、`true`, `1x`, ` 1`, `1 `、`long long` 範囲外。無効扱いへの fallback ではなく例外 |

先頭の `+` / `-` は許可されます。小数・指数表記・前後空白は許可されず、文字列全体が消費される必要があります。値域の clamp はありません。環境変数を読むのは prefill 構造体の初期化時で、この値を保存後に読み直したり static cache したりするコードはありません。初期化後に環境を変えても既存の `Pf::hf16` には反映されません（`engine/src/split/src/env.hpp:15-22`, `33-40`; `engine/src/split/src/prefill.cu:1095-1106`）。

## 有効になる条件

値がゼロ以外でも、次の条件を満たさない経路では f16 交換は実行されません。

- `FNX_HIP` ではない CUDA/NVIDIA build が必要です。HCSPLIT の有効化・設定は `#if !FNX_HIP` 内にあり、HIP build はこの環境変数を読みません（`engine/src/split/src/prefill.cu:1065-1069`, `1090-1101`; HIP build 定義 `engine/src/split/CMakeLists.txt:90-92`, `121-128`）。
- 2 枚のカードを使い、`FNX_PF_RING_SM` がゼロ（既定値）で、`FNX_PF_OVERLAP` がゼロ以外（既定値 1）、かつ `FNX_PF_HCSPLIT` がゼロ以外（既定値 2）である必要があります。`FNX_PF_HCSPLIT=0`、overlap 無効、または GPU thread ring 使用時は HCSPLIT の初期化に入らず、この変数も読まれません（`engine/src/split/src/prefill.cu:1064-1069`, `1080-1094`）。
- HCSPLIT の初期化には down GEMM の cublasLt calibration が既定で実行されます。両カードで条件を満たす algorithm が見つからない場合、HCSPLIT 全体を無効化します。`FNX_PF_HCSPLIT_LT=0` で calibration を止めても `down_lt` が立たないため、後段の全カード判定で split は無効になります（`engine/src/split/src/prefill.cu:1095-1102`, `1149-1159`）。
- 各 prefill pass で実際に split read するには、その pass の chunk 数が `FNX_PF_HCSPLIT_MIN`（既定値 3）以上で、すべての chunk が 512 token 以上であることも必要です。`FNX_PF_HCSPLIT=1` のときはさらに calibration 成功と各 chunk がちょうど 4096 token であることが必要です。条件に満たない pass は通常の read に戻ります（`engine/src/split/src/prefill.cu:1436-1444`）。

## 実行時の詳細

`FNX_PF_HCSPLIT_F16` は各カードの `Pf` 初期化中、HCSPLIT が有効と判断された後に読み取られます。したがって、構成条件を外れると不正な値を設定していても、この読み取り箇所の整数 parse 例外は発生しません。一方、読み取りまで到達して不正値だった場合、`env_int` は `FNX_PF_HCSPLIT_F16: '<値>' is not a whole number` という `std::runtime_error` を投げます（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/src/prefill.cu:1090-1101`）。CLI や他の設定値がこの値を上書きする処理はありません。

有効時は pass ごとに `mixhk` の f16 バッファを確保します。カードごとに hyper-connection read を担当行について行い、結果を `mixhk` に f16 で書き込みます。カード間 swap も `N * sizeof(__half)` の行幅で行い、受信完了後は全行を `mixhk` から f32 の `mixed` に戻し、同じ f16 値を `xh` にもコピーします。無効時は f32 の `mixed` を行幅 `N * sizeof(float)` で swap し、受信後に `mixed` から `xh` を f16 化します（`engine/src/split/src/prefill.cu:1103-1109`, `1541-1563`, `1587-1592`）。

HCSPLIT 全体が後から無効化された場合や、個別 pass の条件を満たさず split read をしない場合、この値だけで split read が強制されることはありません。HCSPLIT が有効でも split read のない pass では専用の `mixed` 行交換は行われません（`engine/src/split/src/prefill.cu:1149-1159`, `1436-1449`）。

## ログと測定値

この変数の値や f16 交換の有効化を直接示す専用ログはありません。HCSPLIT が全カードで有効な場合には `fnx: prompt path: the hyper-connection read is split between the cards (...)`、calibration が成立せず無効な場合には `fnx: prompt path: the hyper-connection read stays on both cards (...)` が stderr に出ます。文言と判定箇所は `engine/src/split/src/prefill.cu:1149-1159` です。Strata の資料にこの変数固有の測定値は確認できません。

## 根拠

- `engine/src/split/src/env.hpp:15-22`, `33-40` — 整数文字列の規則、未設定時の既定値、不正値の例外。
- `engine/src/split/src/prefill.cu:440`, `1064-1109` — HCSPLIT の条件、対象変数の読み取り、f16 バッファ確保。
- `engine/src/split/src/prefill.cu:1149-1159` — 全カードの calibration 成功判定とログ。
- `engine/src/split/src/prefill.cu:1436-1449` — pass ごとの split read 条件。
- `engine/src/split/src/prefill.cu:1541-1563`, `1587-1592` — 担当行の読み取り、交換、両カードでの f16 値の利用。
- `engine/src/split/CMakeLists.txt:90-92`, `121-128` — HIP build の compile guard。
