# `INK_SYCL_NO_XMX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Inkling 2 Mini の SYCL engine で oneMKL XMX GEMM を使わないようにする旧名の環境変数です。読み取り helper は先に `STRATA_SYCL_NO_XMX` を調べ、そちらが未設定または空文字の場合に限って本変数を読みます。選択された値の先頭文字が `1` なら XMX を無効にします。oneMKL を有効にしたビルドでは、該当する dense linear / MoE の XMX dispatch が不成立を返し、呼び出し側が SG16 の通常カーネルへ進みます。oneMKL を含まないビルドでは XMX dispatch 自体が常に不成立です（`engine/src/inkling2/sycl/ink_sy_common.h:48-55`、`engine/src/inkling2/sycl/ink_sy_xmx.h:23-29,418-442,463-490,516-520`、`engine/src/inkling2/sycl/ink_sy_runner.h:394-420`）。

## 値と判定

helper は `STRATA_SYCL_NO_XMX` を `getenv` し、未設定か空文字なら `INK_SYCL_NO_XMX` を読みます。最終的に選ばれた文字列の先頭が ASCII `1` かどうかだけを判定し、残りの文字列は解析しません（`engine/src/inkling2/sycl/ink_sy_common.h:48-55`）。

| 条件 | `STRATA_SYCL_NO_XMX` | `INK_SYCL_NO_XMX` | 結果 |
|---|---|---|---|
| 両方未設定 | 未設定 | 未設定 | XMX 無効化要求なし |
| 新名が空 | 空文字 | 旧名の値を判定 | 旧名にフォールバック |
| 新名が非空 | `1`、`10`、`1anything` など | 旧名の値にかかわらず無視 | 先頭が `1` なら無効化 |
| 新名が非空 | `0`、`true`、`false`、` 1`、空白など | 旧名の値にかかわらず無視 | XMX 無効化要求なし |
| 新名が未設定または空 | 上記以外の旧名値 | `1`、`10`、`1anything` など | 先頭が `1` なら無効化 |
| 新名が未設定または空 | 上記以外の旧名値 | `0`、`true`、`false`、` 1`、空文字など | XMX 無効化要求なし |

大文字小文字、空白、数値としての妥当性は検査しません。たとえば新名が `0`、旧名が `1` の場合は新名が優先され、無効化されません。新名が空で旧名が `1` の場合は無効化されます。CLI 引数や設定ファイルからこの値を読む処理は対象 engine ソースにありません（`engine/src/inkling2/sycl/ink_sy_common.h:48-55`）。

## 有効になる条件

- `INK_SYCL_USE_ONEMKL` が定義された Inkling SYCL engine では、`xmx_enabled()` が helper の結果を反転して返します。CMake は oneMKL の BLAS header が見つかった場合にこの macro を定義し、SYCL build script も `MKLROOT` 配下に header がある場合に定義します（`engine/src/inkling2/sycl/CMakeLists.txt:28-40`、`engine/src/inkling2/sycl/build_inkling_sycl.sh:88-94`、`engine/src/inkling2/sycl/ink_sy_xmx.h:23-29`）。
- oneMKL 有効時も、対象経路・形状に入った場合にだけ XMX と通常 SG16 の選択が生じます。Dense linear は BF16 / Q8ROW で `M >= 16`、S2〜S8 で `M >= 16` かつ `K` が 256 の倍数のとき XMX 関数が候補になります。MoE は expert ごとの token 数 `n` が `INK_SYCL_XMX_MOE_MIN_N`（未設定または空なら 12）以上の場合が候補です。これらの shape/formats に該当しなければ通常経路が使われ、対象変数の値はその処理結果を変えません（`engine/src/inkling2/sycl/ink_sy_xmx.h:31-37,418-490`）。
- oneMKL が無効のビルドでは XMX 関数はすべて `false` を返す stub になり、呼び出し元は通常経路へ進みます。従って本変数を `1` にしても、そのビルドで追加の切り替えは起きません（`engine/src/inkling2/sycl/ink_sy_xmx.h:516-520`）。
- `dev_caps()` も helper の結果を参照して `has_xmx_sg16` を設定しますが、現 checkout ではこのフィールドは設定箇所以外で使われていません（`engine/src/inkling2/sycl/ink_sy_common.h:278-288,290-317`）。
- 本変数を再度有効化する CLI 引数や別の環境変数はありません。`INK_SYCL_XMX_MOE_MIN_N` は MoE の件数しきい値を変えますが、XMX 無効化要求を上書きしません（`engine/src/inkling2/sycl/ink_sy_xmx.h:31-37,487-490`）。

## 実行時の詳細

値の判定結果は `sy_no_xmx_requested()` 内の関数ローカル `static const bool` に保存されます。プロセス内で最初にこの helper が呼ばれた時点で環境を読み、以後の環境変更は反映されません。helper は `dev_caps()` の初期化および `xmx_enabled()` から呼び出されます（`engine/src/inkling2/sycl/ink_sy_common.h:48-55,290-305`、`engine/src/inkling2/sycl/ink_sy_xmx.h:23-29`）。

XMX 無効時、dense linear dispatch は `ink_xmx_linear_*` が `false` を返すため、BF16 / Q8ROW / S2〜S8 の呼び出し元が SG16 GEMM / linear kernel を実行します（`engine/src/inkling2/sycl/ink_sy_xmx.h:418-483`、`engine/src/inkling2/sycl/ink_sy_runner.h:394-420`）。MoE では XMX 関数が `false` になり、runner / hybrid の呼び出し元が通常の SG16 expert kernel に進みます（`engine/src/inkling2/sycl/ink_sy_xmx.h:487-514`、`engine/src/inkling2/sycl/ink_sy_runner.h:772-813`、`engine/src/inkling2/sycl/ink_sy_hybrid.h:774-815,835-843`）。この変数が変更するのはこれらの計算経路の選択です。CLI、モデル設定、サーバー設定による本変数の読み替えや上書きは、対象の engine ソースでは確認できません。

## ログと測定値

この変数の値や XMX 無効化を報告する専用ログ、終了コード、エラー経路は対象コードにありません。`docs/INTEL.md` は A750 での反復性や速度測定、および旧名としての本変数を記載していますが、これらはコードから確認できる挙動ではないため、ここでは測定結果として扱いません（`docs/INTEL.md:323-333,448`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_common.h:46-55` — 新旧変数の優先順位、空文字時のフォールバック、先頭文字判定と cache。
- `engine/src/inkling2/sycl/ink_sy_common.h:290-317` — device capability 初期化からの読み取りと `has_xmx_sg16` 設定。
- `engine/src/inkling2/sycl/ink_sy_xmx.h:23-37,418-520` — build macro、行列・MoE の条件と無効ビルド用 stub。
- `engine/src/inkling2/sycl/ink_sy_runner.h:394-420,772-813`、`engine/src/inkling2/sycl/ink_sy_hybrid.h:774-815,835-843` — XMX が不成立の場合の通常カーネル経路。
- `engine/src/inkling2/sycl/CMakeLists.txt:28-40`、`engine/src/inkling2/sycl/build_inkling_sycl.sh:88-94` — oneMKL build macro を有効にする条件。
