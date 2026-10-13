# `STRATA_VERIFY_COHERENT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

HIP verifier が mapped host buffer を確保するとき、明示的に coherent と指定した host memory を要求する診断用の切り替えです。コメントは gfx1030 の verifier timeout に関する opt-in A/B 用と説明しています。CUDA の通常経路では環境変数を読みません。

## 値と判定

HIP 実装の `env_on()` は `getenv()` の戻り値について、未設定、空文字、または先頭文字が `0` の場合に false、それ以外を true とします。文字列全体の parse や数値変換はしません。

| 環境値 | HIP での結果 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、`2`、`anything` | 有効 |

先頭文字だけを比較するため、大文字小文字、後続文字、数値としての妥当性は判定しません。値は namespace-scope の `const bool g_coherent` 初期化時に一度読み取られます。プロセス起動後に環境を書き換えても再評価されません。

## 有効になる条件

- `src/core/verify.cpp` では `STRATA_USE_HIP` が定義されたビルドだけで変数を読み、mapped buffer の確保に適用します。CUDA ビルドではこの変数による分岐はありません。
- 値が有効でも、verifier が `mapped()` を呼ぶ allocation に限って適用されます。HIP では `hipHostMallocMapped | hipHostMallocCoherent` を指定し、複数 GPU の peer portability が必要な場合は `hipHostMallocPortable` も付けます。未設定または無効なら従来の `cudaHostAllocMapped` 経路を使います。
- 要求した allocation に失敗すると `mapped()` は false を返します。初期化時の staging/plan buffer なら、それぞれ `verify: mapped staging allocation failed` または `verify: mapped plan allocation failed` で verifier の初期化が失敗します。
- SYCL 実装（`sycl/src/core/verify.cpp`）にも同名の読み取りがありますが、そこでは `STRATA_USE_HIP` 条件下の宣言と trace ログ表示にだけ使われています。SYCL の `mapped()` は `window_host_uncached()` に応じて `strata::host_malloc_polled()` または `sycl::malloc_host()` を選び、この変数を参照しません。したがって、SYCL の mapped allocation の方式はこの変数では切り替わりません。

## 実行時の詳細

HIP 実装では `mapped()` が verifier の staging buffers（token/step/position、commit、出力、routing rows、sequence と flags など）、GPU plan、さらに trace 用 buffer の確保に使われます。`STRATA_VERIFY_COHERENT` が有効なら、これらの mapped allocation は明示的 coherent flag 付きで要求されます。この切り替え自体は性能や正確性の測定結果を保証しません。

`STRATA_VERIFY_TRACE` も有効で trace buffer の確保処理まで到達すると、HIP 経路は stderr に `strata verify trace (#649): on; coherent words explicit, ...` と表示します。変数が無効なら `coherent words default` です。trace が無効な場合、この coherent 状態を示すログは出ません。SYCL で `STRATA_USE_HIP` が定義された場合も trace ログに状態が表示されますが、上記の通り SYCL allocation の選択には影響しません。

## 根拠

- `src/core/verify.cpp:169-180`: #649 の HIP opt-in コメント、`env_on()` の判定、HIP 条件付きの読み取り。
- `src/core/verify.cpp:293-305`: coherent flag 付き HIP allocation と通常 mapped allocation の分岐。
- `src/core/verify.cpp:605-623,630-632`: mapped staging/plan の使用箇所と allocation failure の扱い。
- `src/core/verify.cpp:694-709`: trace buffer の mapped allocation と HIP の状態ログ。
- `sycl/src/core/verify.cpp:89-100,229-242,534-558,620-635`: SYCL 側の読み取り、mapped allocation の方式、trace ログ。`g_coherent` はログ表示にだけ参照されます。
- `docs/DETAILS.md` には `STRATA_VERIFY_COHERENT` の個別説明を確認できませんでした。性能値や推奨設定は記載していません。
