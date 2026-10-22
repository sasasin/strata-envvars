# `STRATA_DOORBELL_STORE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。調査開始時の作業ツリーは `main...origin/main` で変更なし。

## 役割

HIP の verifier が GPU からホストへ doorbell を通知するとき、doorbell の sequence 値をホストメモリから読み戻して 1 増やす代わりに、その window 内の layer/group に対応する既知の値を GPU から書き込みます。通常の payload 公開と同様に入力 activation、expert ID、routing weight をホスト側の領域へ公開します。

これは実行結果や expert の選択を変える設定ではなく、doorbell の通知方法を切り替える A/B 用フックです。ソースコメントは、HIP の gfx1030 verify timeout 調査（#649）の opt-in としています。

## 値と判定

`env_on()` は `std::getenv()` の結果について、未設定でなく、かつ先頭文字が NUL または `'0'` でないことだけを判定します。値全体の比較や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が NUL） |
| `0`、`0anything` | 無効 |
| `1`、`10`、`true`、`false`、空白で始まる文字列 | 有効（先頭文字が `'0'` 以外） |

大文字小文字、後続文字、数値としての妥当性は検査されません。たとえば `false` も有効です。

## 有効になる条件

- `STRATA_USE_HIP` が定義されたビルドでのみ、この環境変数の値を読み、doorbell 実装を切り替えます。CUDA ビルドでは同じソースに環境変数読み取り・切り替えのコードはコンパイルされません。
- verifier の通常の per-layer doorbell 公開経路が使われる必要があります。`ar_on()` の分岐ではこの選択箇所を通りません。
- SYCL ソースにも同じ HIP 条件付きの読み取りと分岐があります。`STRATA_USE_HIP` が定義されない SYCL ビルドでは有効になりません。
- `STRATA_VERIFY_TRACE` が有効なときだけ、trace 初期化時に `doorbell stored` または `doorbell incremented` と stderr に出力します。この変数単独では有効化ログを出しません。

## 実行時の詳細

値は `src/core/verify.cpp` および `sycl/src/core/verify.cpp` の名前空間スコープ `const bool` 初期化時に一度評価されます。したがってプロセス起動後に環境を書き換えても、この分岐は再評価されません。

HIP で有効なら、verifier の doorbell 公開時に `doorbell_publish_value()` を呼び、値 `(l - lb_) * G + grp + 1` を渡します。無効なら既存の `doorbell_publish()` または residency を見る `doorbell_publish_res()` に進みます。CUDA ではこの環境変数による切り替えはなく、通常分岐に従います。

HIP の CUDA カーネル実装では、value 版も payload をコピーして system fence を行い、その後 `seq` に渡された値を volatile store します。従来版は `seq` を volatile load して 1 加算した値を書き戻します。どちらも payload 公開後に通知します。SYCL 側の同名 value 版も渡された値で ring を commit し、payload とその checksum を公開します。

## 根拠

- 値判定と HIP 限定の読み取り: `src/core/verify.cpp:217-228`、`sycl/src/core/verify.cpp:90-101`。
- verifier の適用分岐と ring 値の算出: `src/core/verify.cpp:1916-1940`、`sycl/src/core/verify.cpp:1343-1367`。
- HIP カーネルの通常版と value 版、および sequence の加算/直接 store: `src/kernels/cuda/elementwise.cu:311-375`。
- SYCL value 版の payload 公開と ring commit: `sycl/src/kernels/cuda/elementwise.dp.cpp:711-733`。
- trace が表示する状態文字列: `src/core/verify.cpp:862-877`、`sycl/src/core/verify.cpp:621-635`。
- `docs/AMD_HIP.md:341-347` は HIP の doorbell store fence に触れていますが、`STRATA_DOORBELL_STORE` の設定値やこの切り替え自体は説明していません。`docs/` 内にこの環境変数の追加説明は見つかりませんでした。
