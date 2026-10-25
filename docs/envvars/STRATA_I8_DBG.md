# `STRATA_I8_DBG`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の fused int8 ESIMD expert kernel にある bring-up 用ビットフラグです。gate/up と down の計算 kernel で、重み decode、activation load、出力 store、K 方向の計算ループを個別に飛ばせます。通常の推論結果を得るための設定ではなく、設定すると中間値や出力が不完全になります。

## 値と判定

`dbg_flags()` は `std::getenv("STRATA_I8_DBG")` の結果を `std::atoi` に渡します。数値文字列全体の検証はしません。`atoi` が読み取る整数のビットマスクとして扱われ、フラグは OR で組み合わせられます。

| 設定 | `atoi` の結果 | 動作 |
|---|---:|---|
| 未設定 | 0 | すべてのデバッグ分岐を無効化 |
| 空文字、数値に変換できない文字列 | 0 | 同上 |
| `1` の bit が立つ値（例: `1`, `5`） | bit 0 | 重み decode を飛ばす |
| `2` の bit が立つ値（例: `2`, `6`） | bit 1 | activation load を飛ばす |
| `4` の bit が立つ値（例: `4`, `5`） | bit 2 | 出力 store を飛ばす |
| `8` の bit が立つ値（例: `8`, `12`） | bit 3 | K 方向のループを 0 回にする |

`atoi` は先頭の空白と符号を受け付け、整数の後ろに続く文字列を検査しません（例: `2junk` は 2 として読み取られます）。したがって `true` は有効化値として特別扱いされず、0 に変換されます。数値の範囲外に対する扱いは実装が検査していません。

## 有効になる条件

- SYCL prompt の fused int8 ESIMD expert kernel がビルドに含まれ、実行経路で使われる必要があります。通常の prompt では `STRATA_PREFILL_MMQ`（alias `STRATA_PF_I8`）などで int8 経路が選ばれ、対応する device・形式・shape で gate/up と down の kernel が受理された場合に使われます。
- `STRATA_SYCL_I8_ESIMD=OFF`、または `AUTO` の AOT build で対象が bmg/lnl 以外の場合、CMake は `STRATA_I8_NO_ESIMD` stub を選びます。この stub には `dbg_flags()` の読み取りがなく、この変数は作用しません。
- 実カーネルを含む場合も、fused int8 kernel が呼ばれなければ読み取り結果は計算に影響しません。別 backend（CUDA/HIP）の環境変数ではありません。

## 実行時の詳細

`dbg_flags()` の結果は関数内の `static const int` に保持され、最初の呼び出し時に一度だけ読み取られます。gate/up と down の両方が同じ関数を使います。呼び出し後にプロセス環境を書き換えても再評価されません。

bit 0 は decode 部分の条件分岐を飛ばします。bit 1 は kernel 内で activation を読む箇所を飛ばし、初期化された仮の activation 値を使います。work-group variant では事前の chunk load が残る場合があります。bit 2 は結果を書き戻す条件を偽にし、出力バッファを更新しません。bit 3 は K loop の反復数を 0 にし、通常は初期値 0 の accumulator が bit 2 によって禁止されていなければ出力されます。これらを指定した実行の数値結果は通常の推論結果として解釈できません。

環境変数自体に専用ログや警告を出す処理は確認できません。値は各 kernel 引数の `dbg` に渡され、kernel 内で分岐に使われます。

## 根拠

- `sycl/src/prefill/esimd_moe.dp.cpp:754-756`: `getenv`、`atoi`、static cache による値の取得。
- `sycl/src/prefill/esimd_moe.dp.cpp:221-223,237-243,303-337`: gate/up の非 work-group kernel におけるループ、decode、activation load、store の分岐。
- `sycl/src/prefill/esimd_moe.dp.cpp:350-421,516-540,629-639,644-739`: down と work-group kernel の対応分岐。
- `sycl/src/prefill/esimd_moe.dp.cpp:978-1012,1015-1048`: gate/up と down の引数に同じ `dbg_flags()` を格納し、kernel variant を dispatch。
- `sycl/src/prefill/prefill.cpp:4235,4291-4305`: SYCL prompt 経路での kernel 呼び出しと失敗時の経路。
- `sycl/src/prefill/esimd_moe.dp.cpp:40-60` と `sycl/CMakeLists.txt:45-63`: `STRATA_I8_NO_ESIMD` stub、および ESIMD kernel を無効化する build 条件。
- `docs/INTEL_INT8_EXPERTS.md:25-27`: 既存資料は bring-up switch と説明していますが、フラグ 8 の説明は省略しています。値の判定と個別の動作は上記実装を根拠にしています。
