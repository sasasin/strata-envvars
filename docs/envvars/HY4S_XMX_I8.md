# `HY4S_XMX_I8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

SYCL の量子化重み GEMM が SG=8 XMX 経路を使う場合に、入力 activation の処理と GEMM を FP16 または INT8 DPAS のどちらで実行するか選ぶ。未設定または parse 後の値が `0` なら FP16 XMX、値が `1` なら 1 項 INT8 DPAS、`2` なら残差を加えた 2 項 INT8 DPAS を選択する。INT8 の値は `linear_auto` から呼ばれる重み GEMM に適用され、SYCL の graph runner では通常の線形層・Engram 射影・LM head などから到達する。直接 `gemm_xmx` を呼ぶ同梱テスト経路もある。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:847-854,910-964,969-986`、`engine/src/hy4flash/sycl/sy_graph.h:476-480,817-826,1448-1469`、`engine/src/hy4flash/sycl/sy_gemm_test.cpp:68`。

## 値と判定

`xmx_i8_mode()` は初回呼び出し時に `std::getenv` し、未設定なら `0`、設定済みなら `atoi` の戻り値を保存する。文字列全体の検証はなく、空文字や数値で始まらない文字列は `atoi` により `0` となり、数値の後ろは無視される。したがって `1abc` は `1`、`2xyz` は `2`、`0anything` は `0`、`true` は `0`。符号付き整数として `-1` や `3` も parse されるが、INT8 DPAS として分岐するのは値がちょうど `1` または `2` の場合だけ。空白・大文字小文字の独自判定や clamp、無効値のエラー処理はない。`atoi` で `int` の範囲外となる文字列の結果はコードで保証されない。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:847-854,915-930`。

| 条件 | unset | `1` と parse される例 | `2` と parse される例 | その他の例 |
|---|---|---|---|---|
| すべての build | mode `0` | `1`, `01`, `1abc` | `2`, `2xyz` | 空文字、`true`、`0anything` は mode `0`; `-1`, `3` はそれぞれその整数（INT8 分岐には入らない） |

## 有効になる条件

- Strata の SYCL GEMM 経路を通り、行数が `M >= 16`、`N` が 64 の倍数、`K` が 256 の倍数であること。`linear_auto` は `M` の 8 の倍数部分だけ GEMM に渡し、残りは GEMV / `linear_h` に回す。`M < 16` や寸法条件を満たさない場合はこの設定を使った XMX GEMM に到達しない。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:943-964,969-985`。
- `HY4S_XMX_I8=1|2` が INT8 DPAS を選ぶには、build で `HY4S_DISABLE_SG8` が定義されておらず、選択デバイスについて `dev_caps().has_xmx_sg8` が真であること。機能検出はサブグループ幅とデバイス識別に基づく。条件を満たさない場合は SG=16 XMX または SG=32 SIMT へ進み、そこで `HY4S_XMX_I8` の値は INT8/FP16 の切替に使われない。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:910-940`、`engine/src/hy4flash/sycl/sy_common.h:198-259`。
- `build_hy4_sycl.sh bmg` は `HY4S_DISABLE_SG8` と `HY4S_ENABLE_SG16_XMX` を定義するため、この変数による SG=8 INT8 切替は使われない。通常の `fat` / `acm` build は SG=8 を無効化しない。`engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-40`。
- `HY4S_NO_XMX=1` なら `dev_caps()` が XMX 能力の登録を抑止するため、設定値にかかわらず SG=8 INT8 経路には入らない。`engine/src/hy4flash/sycl/sy_common.h:218-255`。
- `HY4S_USE_ONEMKL` build では、`HY4S_ONEMKL` が有効で `M >= 32` など oneMKL 経路の条件を満たすとき、mode `0` なら Strata は oneMKL GEMM を呼び出し得る。mode が `0` 以外なら `gemm_onemkl` は `false` を返し、後続経路へ進む。mode `3` や `-1` は INT8 にはならないが oneMKL 選択を妨げる点に注意。ここでは oneMKL 内部の実行動作は扱わない。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-865,889-908,943-948,969-976`。`HY4S_ONEMKL` は先頭文字が `'0'` の場合だけ無効であり、build に `HY4S_USE_ONEMKL` がなければ参照されない。
- 重みが RP layout の場合、`linear_auto` は GEMM の対応形式を S4/S5/S8 に限定する。それ以外は通常 GEMM 分岐に入らない。非 RP では S2/S3/S4/S5/S6/S8 が対応する。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:949-962`。

## 実行時の詳細

値は `xmx_i8_mode()` の関数内 `static const int` に初回評価時だけ保存されるため、プロセス実行中に環境を変更しても再評価されない。プロセス起動前に設定する必要がある。`HY4S_XMX_I8` 自体を子プロセスへ渡すコードはこの読取経路にはない。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:847-854`。

SG=8 XMX に入り mode が `1` または `2` の場合、activation を GPU 上で Q8_1_G64 に量子化してから INT8 の重み GEMM を実行する。mode `1` は 1 項量子化、mode `2` は量子化残差をもう 1 項で表し、対応する追加 scratch と計算を使う。mode `0` および `1`/`2` 以外は FP16 XMX GEMM を選ぶ。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:263-310,910-940`。

oneMKL なしの `linear_auto` は、`M >= 16` かつ寸法条件を満たすと `M` を 8 の倍数に切り下げて GEMM を呼び、残りの行を別の線形経路で処理する。`HY4S_USE_ONEMKL` build では先に oneMKL 経路を試す。CLI 引数がこの環境変数を上書きする処理は確認できない。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:889-908,943-985`。

## ログと測定値

この環境変数の値や選択した mode を表示する Strata のログ、警告、専用エラー処理は確認できない。`1`/`2` 経路で scratch のデバイスメモリ確保に失敗した場合は、共通の `dalloc` が `dalloc: out of device memory (%zu bytes)\n` を stderr に出し、終了コード 3 で終了する。`engine/src/hy4flash/sycl/sy_gemm_xmx.h:917-924`、`engine/src/hy4flash/sycl/sy_common.h:263-270`。

`docs/DETAILS.md` にこの変数や対応 DPAS GEMM の測定値は見当たらない。コードコメントにある性能・誤差値は条件付きの資料として検証できないため、本書では測定結果として記載しない。

## 根拠

- `engine/src/hy4flash/sycl/sy_gemm_xmx.h:847-854` — 環境変数の読み取り、既定値、static cache。
- `engine/src/hy4flash/sycl/sy_gemm_xmx.h:263-310,420-561` — 1 項 / 2 項 activation 量子化と INT8 DPAS GEMM。
- `engine/src/hy4flash/sycl/sy_gemm_xmx.h:889-940,943-986` — oneMKL 優先判定、XMX 分岐、寸法条件、fallback。
- `engine/src/hy4flash/sycl/sy_common.h:198-259` — デバイス能力・XMX 判定と `HY4S_NO_XMX`。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-49` — build macro と oneMKL build 条件。
- `engine/src/hy4flash/sycl/sy_graph.h:476-480,817-826,1448-1469` — runner からの呼び出し例。
