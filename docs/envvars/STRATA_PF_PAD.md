# `STRATA_PF_PAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_PF_PAD` は、prefill 中の GDN 出力 `y_h` と QSA 出力 `attn_h` の FP16 行 stride に 64 要素の余白を加えるスイッチです。`STRATA_PF_GEMM` も有効な場合、対象チャンクで stride 6144 から 6208（6144 + 64）にし、各出力を `ssm_out.weight` または `attn_output.weight` の GEMM に渡します。HIP の対応 GPU では重み側も同じ幅にパディングした専用 GEMM を試します。Strata の実装コメントは同じ積・ビット列を保つ意図を記していますが、ここでは性能や数値同一性を新たに検証していません。`engine/src/prefill/prefill.cpp:1034-1053,5195-5213,5541-5574`、`engine/sycl/src/prefill/prefill.cpp:404-414,3551-3557,3899-3901`。

この変数単独では無効です。値が合っても `STRATA_PF_GEMM` が有効でない場合は通常 stride のままです。HIP ではさらに、その時点の GPU が padded GEMM 経路を利用できる必要があります。`engine/src/prefill/prefill.cpp:1037-1051`。

## 値と判定

prefill 側は `std::getenv` の結果が存在し、先頭文字が文字 `'1'` かを一度だけ評価して static に保存します。数値変換や文字列全体の比較はしません。`"1"`、`"10"`、`"1anything"` は有効、未設定・空文字・`"0"`・`"true"`・先頭が空白の `" 1"` は無効です。大文字小文字や数値妥当性の検査もありません。実行中に環境を変えても、このプロセスのキャッシュ済み判定は変わりません。`engine/src/prefill/prefill.cpp:1037-1051`、`engine/sycl/src/prefill/prefill.cpp:407-413`。

| 経路 | `STRATA_PF_PAD` / `STRATA_PF_GEMM` | 判定と結果 |
|---|---|---|
| HIP prefill | 両方の先頭文字が `1` | HIP の `pf_pad()` が true になり得る。現在の GPU で padded product が使えなければ警告して false にする。`T` の閾値も満たす場合だけ活性行 stride を 6144 + 64 にする。`engine/src/prefill/prefill.cpp:1037-1051,5195,5541` |
| SYCL prefill | 両方の先頭文字が `1` | 同じ先頭文字判定で true。HIP の GPU 可用性警告はなく、`T` の閾値を満たす GDN/QSA 出力に拡張 stride を渡す。`engine/sycl/src/prefill/prefill.cpp:407-413,3551,3899` |
| その他・片方のみ有効 | どちらかが未設定、空、または先頭文字が `1` 以外 | padding しない。 |

HIP の `Gemm::native` は別の static 判定で両変数を再読し、さらに `STRATA_PF_SWITCH_MIN_T`、`T >= 64`、`N >= 512`、`K % 32 == 0`、scratch 容量、GPU 可用性を確認して専用積を試します。`STRATA_PF_SWITCH_MIN_T` は未設定なら 0、設定時は `std::atoll` で変換され、無効文字列や空文字は 0 になります。活性の stride を広げる側の閾値は `T >= max(STRATA_PF_SWITCH_MIN_T, 64)` なので、最小チャンクは 64 token です。`engine/src/prefill/gemm.cu:1495-1505`、`engine/src/prefill/prefill.cpp:975-979,5195,5541`。

## 有効になる条件

- prefill 実行で GDN の `ssm_out` 出力または QSA の `attn_output` 出力まで進み、チャンク長が `max(STRATA_PF_SWITCH_MIN_T, 64)` 以上であること。短いチャンクでは `pf_pad()` が true でもその呼び出しは通常 stride を使います。`engine/src/prefill/prefill.cpp:5195-5213,5541-5574`。
- `STRATA_PF_GEMM` も先頭文字 `1` であること。片方の変数だけでは padding しません。`engine/src/prefill/prefill.cpp:1037-1041`、`engine/sycl/src/prefill/prefill.cpp:407-411`。
- HIP では padded GEMM の device 判定が true であること。gfx11 WMMA 対応 GPU、またはビルド・GPU に応じて Unsloth WMMA が利用可能な場合に true になります。利用不可なら padding を止めます。`engine/src/prefill/wmma_gemm.cu:44-68,758-764`。
- 起動時の既定値注入は GPU によって異なります。gfx1151 の `arch_default_env` は `STRATA_GFX1151_DEFAULTS` が `0` で始まらない場合 `STRATA_PF_PAD=1` を候補にし、既存値（空文字や `0` を含む）がなければ設定します。gfx1100/1101/1102 の離散 RDNA3 は `gfx11_discrete_exact_env` が `STRATA_PF_PAD=1` を候補にし、`STRATA_GFX11_DEFAULTS=0` で無効になります。これらの経路で `STRATA_PF_GEMM` が別途有効にならなければ PAD は不活性です。gfx12 の既定テーブルには PAD がありません。`engine/src/core/arch_defaults.cpp:28-66,302-323`、`engine/include/strata/core/gfx11_extra.hpp:27-54`。
- `generate` は GPU を問い合わせて `apply_arch_defaults` を prefill switch の読み取り前に呼びます。ユーザーが環境変数を設定済みならその値を保持します。`engine/src/program/generate.cpp:4288-4320`、`engine/src/core/arch_defaults.cpp:218-223,302-323`。
- Strata の setup は gfx1103 用スイッチ集合を gfx1150 にも使い、両方のインストール設定に `STRATA_PF_PAD=1` を含めます。ただしこれは実行設定の `env` に書く既定値であり、動作には実行環境で `STRATA_PF_GEMM` も必要です。`terminal/setup.py:4465-4485,7544-7547`。

## 実行時の詳細

HIP と SYCL の `pf_pad()` は初回呼び出し時に環境値をキャッシュします。HIP の `Gemm::native` も `STRATA_PF_PAD`、`STRATA_PF_GEMM`、`STRATA_PF_SWITCH_MIN_T` を関数内 static に別途キャッシュします。GPU 可用性は HIP の WMMA 実装でデバイス番号ごとにキャッシュされます。`engine/src/prefill/prefill.cpp:1037-1051`、`engine/sycl/src/prefill/prefill.cpp:407-413`、`engine/src/prefill/gemm.cu:1495-1501`、`engine/src/prefill/wmma_gemm.cu:48-59`。

有効時は Strata が FP16 出力バッファを `T * (ZV + 64)` 要素で確保し、GDN recurrence または QSA gate に `ld_y` / `ld_a = ZV + 64` を渡します。その stride を使って `ssm_out` / `attn_output` の native projection を呼びます。`T` の閾値未満は stride 引数を 0 とし、通常の stride を使います。`engine/src/prefill/prefill.cpp:1895-1900,2801-2809,5195-5213,5541-5574`、`engine/sycl/src/prefill/prefill.cpp:1216-1234,1721-1733,3551-3557,3899-3901`。

HIP の専用 padded GEMM は追加条件を満たすと、重みを K + 64 の stride で scratch に dequantize し、`strata_pf_gemm_f16_ld` を呼びます。この経路が使えない一方で padded X が渡された場合、Strata は通常幅へコピーして通常の GEMM を続行します。コピー領域を確保できない場合は stderr にエラーを出し `exit(1)` します。`engine/src/prefill/gemm.cu:1489-1507,1509-1534`。

## ログと測定値

HIP で両スイッチが先頭文字 `1` なのに現在のカードで padded product を実行できない場合、初回判定時に stderr へ次を出し、padding を行いません（static 初期化のため同プロセスでは一度）。

```text
prefill gemm: STRATA_PF_PAD needs the padded gfx11 product, which this card does not run; not padding
```

GPU 既定値の適用時は、設定された switch 名を `strata: ... exact speed switches on by default ...` 等の起動行に列挙します。ユーザーが値を既に設定しているとその変数は上書きされず、この既定値一覧にも加わりません。`engine/src/prefill/prefill.cpp:1044-1048`、`engine/src/core/arch_defaults.cpp:325-332,397-404`。

CUDA の診断用 `gdn_harness` は設定値がある場合に標準出力へ `env STRATA_PF_PAD=<値>` を表示します。これは値の表示だけで、通常 engine のスイッチ判定ではありません。`engine/src/prefill/gdn_harness.cu:450-452`。

`docs/AMD_HIP.md:813` は RX 9070 (gfx1201)、ROCm 7.2.4、Coder IQ1_M で `STRATA_PF_PAD` / `STRATA_PF_GEMM` を試した値を 4K 1,247 対 1,243 tok/s、8K 1,330 対 1,321 tok/s（いずれもノイズ範囲）と記しています。同資料 `:309` は gfx12 では両スイッチを使わず、stride を読む kernel がないところで engine は padding しないと説明しています。これは資料に記載された測定・説明であり、本調査で再測定した値ではありません。

## 根拠

- `engine/src/prefill/prefill.cpp:1034-1053,1895-1900,2801-2809,5195-5213,5541-5574`
- `engine/sycl/src/prefill/prefill.cpp:404-414,1216-1234,1721-1733,3551-3557,3899-3901`
- `engine/src/prefill/gemm.cu:1489-1534`
- `engine/src/prefill/wmma_gemm.cu:44-68,758-764`
- `engine/src/core/arch_defaults.cpp:28-66,218-223,302-323,325-332,397-421`
- `engine/include/strata/core/gfx11_extra.hpp:27-54`
- `engine/src/program/generate.cpp:4288-4320`
- `engine/src/prefill/gdn_harness.cu:450-452`
- `terminal/setup.py:4465-4485,7544-7547`
- `docs/AMD_HIP.md:309,813`

