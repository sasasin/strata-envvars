# `STRATA_DOORBELL_STORE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

HIP verifier の doorbell publish で、GPU が共有 sequence/ring word を read-modify-write で 1 増やす代わりに、その layer/group の step 番号を直接 store する A/B 用スイッチです。Strata のコメントでは、gfx1030 の verify timeout 調査用として説明されています。モデルやルーティング値の選択を変える設定としては実装されていません。

## 値と判定

`env_on("STRATA_DOORBELL_STORE")` は `getenv()` の結果が null でなく、空文字でもなく、先頭文字が `'0'` でもない場合に true を返します。文字列全体の parse、数値検査、大文字小文字変換はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| `0`, `0anything` | OFF |
| `1`, `2`, `true`, `false`, ` 0`, その他先頭が `0` 以外の非空文字列 | ON |

無効値に対する警告や fallback はありません。値は `src/core/verify.cpp` と `sycl/src/core/verify.cpp` のファイルスコープ `const bool` 初期化時に読み取られるため、プロセス起動時の環境で固定され、実行中の変更では再評価されません。CLI 引数や別の Strata 環境変数による上書きはありません。

## 有効になる条件

- `STRATA_USE_HIP` が定義された HIP ビルドでのみ、環境変数を読み、その値を publish 経路で参照します。CUDA ビルドでは読み取りも分岐もコンパイルされません。
- verifier が layer/group ごとの routed expert 処理を行い、`ar_on()` が false の分岐を通る必要があります。`ar_on()` は all-resident かつ `ar_off_` でない状態を指し、その場合は resident plan の分岐となり doorbell の publish は行われません。
- `STRATA_USE_HIP` の下では `remote_opt_` / `always_publish_` の有無に先立ってこの分岐が通常 publish を置き換えます。非 HIP ビルドでは従来どおり `remote_opt_ || always_publish_` に応じて通常 publish、または residency 情報付き publish を選びます。
- `STRATA_HIP_GFX906` だけの互換ビルドは、このスイッチの `#if defined(STRATA_USE_HIP)` 条件を満たしません。

OS 別の判定や CLI フラグはありません。環境値が ON でも、上記の HIP verifier 経路を通らなければ効果はありません。

## 実行時の詳細

通常の値では、GPU publish kernel が payload を書いた後、sequence word を読み出して 1 増やします。スイッチが ON の場合は `doorbell_publish_value()` に切り替え、`(l - lb_) * G + grp + 1` として計算した step 番号を sequence word に store します。native と SYCL-port の verifier に同じ分岐があり、対応する kernel は payload の後に ring value を書きます。これは既知の step 番号を使って ring 更新時の読み出しを避ける経路です。

通常実行ではこの環境変数だけを理由にしたログや警告は出ません。`STRATA_VERIFY_TRACE` も有効な場合、HIP の trace 初期化時に stderr へ `strata verify trace (#649): on; coherent words ... doorbell stored ...`（OFF なら `doorbell incremented`）を出します。trace の追加情報には `HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の設定値も表示されますが、それらの外部側の意味はこの文書では扱いません。

publish 関数は `k > 1024` の場合に stderr へ `doorbell_publish: k too large` を出して `exit(1)` します。これは値切替先にもある publish 関数のガードです。verifier 側では、layer の ring が期待値に届かず GPU graph が完了した場合 `verify: layer ... never rang (...)`、20 秒を超えて待った場合 `verify: timed out at layer ...` をエラーにします。この環境変数専用のエラーや自動 fallback は実装されていません。

## 根拠

- 名前の読み取りと値判定 helper: `src/core/verify.cpp:296-306`, `sycl/src/core/verify.cpp:91-101`。
- 読み取り箇所の全件確認: 上記 2 件がコード内の値読み取りで、`rg -n --hidden --glob '!.git/**' 'STRATA_DOORBELL_STORE'` で得られる他の参照はコメントです（`include/strata/kernels/elementwise.hpp:121`, `src/kernels/cuda/elementwise.cu:353-354`, `sycl/src/kernels/cuda/elementwise.dp.cpp:712-713`）。
- `ar_on()` の定義: `include/strata/core/verify.hpp:529`。
- HIP 条件と publish 選択、step 値: `src/core/verify.cpp:2106-2130`, `sycl/src/core/verify.cpp:1403-1427`。
- ring を直接 store する kernel と `k > 1024` の終了経路: `src/kernels/cuda/elementwise.cu:353-375`; SYCL-port 実装: `sycl/src/kernels/cuda/elementwise.dp.cpp:712-740`。
- trace 表示: `src/core/verify.cpp:1005-1019`, `sycl/src/core/verify.cpp:622-636`。
- host 側の doorbell 待ちと失敗経路: `src/core/verify.cpp:4947-4965`。
