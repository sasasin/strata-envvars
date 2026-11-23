# `INK_SYCL_NO_XMX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2 の SYCL backend で、oneMKL を使う XMX GEMM / MoE の dispatch を無効化する開発・診断用の切替です。値の先頭文字が `1` の場合、`xmx_enabled()` が false を返し、oneMKL 用 dispatch 関数は `false` を返して呼び出し側の SG16 実装へ進みます。対象は `engine/src/inkling2/sycl/ink_sy_xmx.h` の `xmx_enabled()` と各 `ink_xmx_*` 関数です（同ファイル:23-33, 423-524）。

この切替は生成設定やモデル形式を変えるものではなく、XMX dispatch を試すかどうかを変えます。無効時に SG16 経路へ fallback する箇所は `ink_sy_runner.h:385-411, 680-714` と `ink_sy_hybrid.h:774-798, 801-843` です。両経路の数値結果が常に一致することを示す根拠は、このソース範囲では確認できません。

## 値と判定

`xmx_enabled()` は `std::getenv` の結果について、未設定でないことと先頭 byte が `'1'` であることだけを判定します。文字列全体の parse、空白除去、大文字小文字変換、数値検証はありません。したがって空文字は無効化しませんが、`1anything` や `10` は無効化します。`true`、`0`、`01`、先頭が空白の ` 1` は無効化しません（`ink_sy_xmx.h:23-33`）。

| 条件（build など） | unset | 無効化する値 | 無効化しない値 |
|---|---|---|---|
| `INK_SYCL_USE_ONEMKL` が定義された SYCL build | XMX dispatch を許可 | 先頭 byte が `1`（例: `1`, `1x`, `10`） | 空文字、`0`, `true`, `01`, ` 1`, その他先頭が `1` でない文字列 |
| `INK_SYCL_USE_ONEMKL` が未定義の SYCL build | `xmx_enabled()` は常に false | 値の判定結果は dispatch に影響しない | 値の判定結果は dispatch に影響しない |

CMake は oneMKL のヘッダーが見つかった場合に `INK_SYCL_USE_ONEMKL=1` を定義し、そうでなければ定義しません（`engine/src/inkling2/sycl/CMakeLists.txt:28-41`）。macro 未定義時は `xmx_enabled()` が false を返し、XMX dispatch 関数も false を返す stub です（`ink_sy_xmx.h:23-33, 520-524`）。

## 有効になる条件

- Inkling-2 の SYCL backend を使う必要があります。この名前の読み取り箇所は SYCL 実装内にあり、CUDA / HIP / Metal の経路にはありません（`engine/src/inkling2/sycl/ink_sy_xmx.h:23-33`, `engine/src/inkling2/sycl/ink_sy_common.h:196-224`）。
- XMX dispatch を許可するには `INK_SYCL_USE_ONEMKL` が定義された build が必要です。未定義なら環境値にかかわらず XMX は無効です（`ink_sy_xmx.h:23-33, 520-524`; `CMakeLists.txt:28-41`）。
- 環境値が unset または先頭が `1` 以外でも、dense BF16 / Q8_ROW は `M >= 16`、量子化 SK 線形演算は `M >= 16` かつ `K` が 256 の倍数の場合にだけ各 XMX 関数が処理し、それ以外は runner の SG16 経路へ戻ります（`ink_sy_xmx.h:423-488`; `ink_sy_runner.h:385-411`）。
- MoE XMX は expert ごとの token 数が `xmx_moe_min_n()` 以上の場合だけ実行されます。既定値は 12 で、これは別の変数 `INK_SYCL_XMX_MOE_MIN_N` が変更できます（`ink_sy_xmx.h:35-42, 490-519`; `ink_sy_runner.h:680-712`; `ink_sy_hybrid.h:774-798`）。非-hybrid MoE dispatch にはさらに `M >= 32` が必要です（`ink_sy_runner.h:680-681`）。
- `dev_caps()` も同名変数を読み、SG16 対応 subgroup と特定の device 名の両方がある場合に `has_xmx_sg16` を設定します。ただしこの commit では同フィールドを設定する以外の参照がなく、この判定は dispatch の有効条件になっていません（`ink_sy_common.h:184-224`; `rg` による全参照確認）。

## 実行時の詳細

`xmx_enabled()` は初回呼び出し時に関数内 `static const bool` を初期化し、その後の呼び出しでは値を再利用します。したがってプロセス起動後に環境を書き換えても、この判定には反映されません（`ink_sy_xmx.h:23-33`）。`dev_caps()` も初回呼び出し時に `static SyDevCaps` を作り、別個に環境値を一度読みます（`ink_sy_common.h:196-224`）。この二つは初回評価時点が独立しています。

oneMKL が有効な build で値が無効化を指示しない場合、BF16 / Q8_ROW / SK の線形処理は入力を FP16 へ変換し oneMKL row-major GEMM を呼びます。各関数の条件を満たさないか、`INK_SYCL_NO_XMX` により `xmx_enabled()` が false なら `false` を返し、runner は SG16 kernel を選びます（`ink_sy_xmx.h:423-488`; `ink_sy_runner.h:385-411`）。MoE でも XMX 関数が false を返す場合、runner / hybrid runner は通常の SG16 MoE kernel に振り分けます（`ink_sy_xmx.h:490-519`; `ink_sy_runner.h:680-714`; `ink_sy_hybrid.h:774-798, 801-843`）。

同じ名前の二つの読み取り箇所はいずれもプロセス環境から直接読みます。Strata 内でこの値を CLI 引数、設定ファイル、子プロセスへ転送する処理は確認できません。CLI や別の環境変数による `xmx_enabled()` の上書きもありません。関連する別設定は MoE の閾値 `INK_SYCL_XMX_MOE_MIN_N` です。

## ログと測定値

この変数の値、無効化、または fallback を知らせる実行時ログは確認できません。build 時は oneMKL を検出した場合に CMake が `Inkling SYCL: enabling Intel oneMKL XMX GEMM (...)` を出しますが、これは環境変数の値を示すログではありません（`engine/src/inkling2/sycl/CMakeLists.txt:33-40`）。この調査範囲で本変数による性能測定値は確認できませんでした。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_xmx.h:23-42` — XMX 有効判定、遅延 cache、MoE 閾値。
- `engine/src/inkling2/sycl/ink_sy_xmx.h:423-524` — oneMKL dispatch 条件と macro 未定義時の stub。
- `engine/src/inkling2/sycl/ink_sy_common.h:184-224` — device capability の遅延初期化と同名変数の別読み取り。
- `engine/src/inkling2/sycl/ink_sy_runner.h:385-415, 680-714` — 線形演算と通常 MoE の dispatch / fallback。
- `engine/src/inkling2/sycl/ink_sy_hybrid.h:774-843` — hybrid MoE の dispatch / fallback。
- `engine/src/inkling2/sycl/CMakeLists.txt:28-41` — oneMKL build macro の条件。
