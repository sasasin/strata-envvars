# `HIP_HOST_COHERENT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数としての意味は対象外。

## 役割

Strata の HIP verifier は、この変数を制御設定として解釈しません。`STRATA_VERIFY_TRACE` が有効で HIP 用の verifier trace buffer を初めて割り当てる際、値を診断ログに表示します。Strata 内でこの値を使ってメモリ確保方法や同期方式を切り替える処理は見つかりませんでした。

## 値と判定

Strata は `getenv("HIP_HOST_COHERENT")` の結果を `%s` でそのままログへ渡します。数値変換、真偽値判定、文字列比較、範囲検査はありません。

| 環境の状態 | Strata のログ表示 |
|---|---|
| 未設定 | `-` |
| 空文字で設定 | 空欄 |
| その他の文字列 | その文字列 |

## 有効になる条件

- HIP 用 verifier が使われ、`STRATA_USE_HIP` が定義されたビルドであること。
- `STRATA_VERIFY_TRACE` が有効で、trace buffer の初回割り当て箇所に到達すること。
- `STRATA_VERIFY_TRACE` 自体は `env_on()` で判定されます。未設定・空文字・先頭文字が `0` の値は無効、先頭文字が `0` 以外の非空値は有効です。この判定はグローバル初期化時に行われます。

条件を満たすと stderr に `strata verify trace (#649): on; coherent words ... HIP_HOST_COHERENT=<値> ...` が出ます。条件を満たさなければ、Strata はこの変数を読み取らず、表示もしません。値が設定されても、Strata 側の verifier 動作や分岐は変わりません。

## 実行時の詳細

HIP verifier は `STRATA_VERIFY_COHERENT` を `g_coherent` に読み込み、`mapped()` でその設定に応じて明示的 coherent host allocation を使うかを決めます。一方 `HIP_HOST_COHERENT` は同じログ行の `%s` 引数としてだけ参照され、`g_coherent` や allocation の条件には渡されません。`STRATA_VERIFY_COHERENT` は別の Strata 設定であり、この文書では相互作用の区別のためだけに記載しています。

`src/core/verify.cpp` では、そのログ出力時に環境値を読み取ります。環境値自体を保存する static cache はありません。

SYCL 側にある `sycl/src/core/verify.cpp` にも同じログ式がありますが、これも `STRATA_USE_HIP` 条件内です。SYCL ビルドでその条件が有効になる構成かどうかは、この変数の読み取りコードからは判断できません。

## 根拠

- `src/core/verify.cpp:189-200`: HIP 用設定と trace 設定の読み取り。`env_on()` は空文字と先頭 `0` を無効にする。
- `src/core/verify.cpp:313-326`: 実際の coherent allocation は `g_coherent` で分岐し、`HIP_HOST_COHERENT` は参照しません。
- `src/core/verify.cpp:716-731`: trace buffer 初回割り当て時の HIP 診断ログと、値が未設定の場合の `-` 表示。
- `sycl/src/core/verify.cpp:89-100,612-626`: SYCL 側の同型コード。
- `docs/DETAILS.md` と `docs/AMD_HIP.md` に `HIP_HOST_COHERENT` の説明は見つかりませんでした。
