# `STRATA_DOORBELL_STORE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 条件付きの verifier で、GPU が CPU 側へ expert 用の入力を通知する doorbell の ring 更新方法を切り替える A/B 用スイッチです。通常経路では GPU が ring 値を読み足して書き戻しますが、有効時はその publish 段の既知の番号を ring に書き込みます。`engine/src/core/verify.cpp` と `engine/sycl/src/core/verify.cpp` の `g_doorbell_store` が設定を保持し、`Verifier` の route/expert 処理から publish 関数を選びます（`engine/src/core/verify.cpp:333-343,2700-2715`; `engine/sycl/src/core/verify.cpp:148-154,187-190,1622-1637`）。

この変数による選択は、生成内容や expert の選択を変えるものとして実装されていません。コードコメントは #649 の HIP verifier timeout 調査（gfx1030）用 A/B と説明しています。通常の HIP build guard 以外に GPU 世代を検査する分岐はありません（`engine/src/core/verify.cpp:333-343,2700-2715`）。

## 値と判定

両 verifier の `env_on` は `getenv` の結果が null でなく、空文字でなく、先頭文字が `0` でない場合に true を返します。文字列全体の parse や数値検証はしません（`engine/src/core/verify.cpp:336-339`; `engine/sycl/src/core/verify.cpp:151-154`）。

| ビルド条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_USE_HIP` が定義された verifier build | 無効 | `1`, `2`, `true`, `false`, ` 0`（いずれも先頭文字が `0` 以外の非空文字列） | 空文字、`0`, `0anything` |
| `STRATA_USE_HIP` が未定義の build | この変数を読み取るコードなし | 該当なし | 効果なし |

大小文字・空白・数値としての妥当性は検査しません。たとえば `false` も先頭が `f` のため有効、` 0` も先頭が空白のため有効です。`0anything` は先頭文字が `0` なので無効です（同上）。

## 有効になる条件

- `STRATA_USE_HIP` を定義してコンパイルされた verifier であること。通常の CUDA 経路にはこの読み取り・切り替えがありません（`engine/src/core/verify.cpp:340-343,2700-2705`; `engine/sycl/src/core/verify.cpp:187-190,1622-1627`）。
- verifier の route/expert 処理が `ar_on()` ではない分岐に入り、doorbell を publish すること。有効時はその分岐の publish 選択を `doorbell_publish_value` にします。`ar_on()` 側ではこのスイッチを参照せず、resident plan の処理を行います（`engine/src/core/verify.cpp:2686-2715`; `engine/sycl/src/core/verify.cpp:1612-1637`）。
- コメント上の主な用途は gfx1030 の HIP verifier timeout 調査ですが、当該分岐に GPU 世代・CLI 引数・サーバーモード・モデル形式の追加判定はありません（`engine/src/core/verify.cpp:333-343,2700-2715`）。

## 実行時の詳細

`g_doorbell_store` は namespace-scope の `const bool` として初期化されます。そのため環境を読むのは verifier 実行中の各 window や各 publish 時ではなく、該当コードを含むプロセスの静的初期化時です。実行開始後に環境値を変更してもこの値には反映されません。値の再読み込みや子プロセスへの転送はこの実装にありません（`engine/src/core/verify.cpp:336-343`; `engine/sycl/src/core/verify.cpp:151-154,187-190`）。

有効な場合、通常の `doorbell_publish` / `doorbell_publish_res` の代わりに `doorbell_publish_value` を呼び、route 入力 `x`、expert ID、routing weight を出力バッファへ publish して、現在の段番号 `(l - lb_) * G + grp + 1` を ring 値として渡します。CUDA/HIP kernel 実装では ring の read-modify-write をせず、その値を volatile store します（`engine/src/core/verify.cpp:2700-2715`; `engine/src/kernels/cuda/elementwise.cu:353-375`）。SYCL 側の対応実装も payload を publish してから ring commit に同じ値を渡します（`engine/sycl/src/core/verify.cpp:1622-1637`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:721-770`）。

## ログと測定値

この値自体を理由にした警告や終了処理はありません。選択先の `doorbell_publish_value` は `k > 1024` のとき stderr に `doorbell_publish: k too large` を出して `std::exit(1)` します（`engine/src/kernels/cuda/elementwise.cu:369-375`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:745-749`）。`STRATA_VERIFY_TRACE` が有効で trace buffer の割り当てに進んだ場合は、stderr に `strata verify trace (#649): on; coherent words ...; doorbell stored|incremented, HIP_HOST_COHERENT=... HSA_ENABLE_SDMA=... GPU_MAX_HW_QUEUES=...` を出します。`doorbell` 部分は `g_doorbell_store` の判定結果です（`engine/src/core/verify.cpp:1245-1260`; `engine/sycl/src/core/verify.cpp:800-814`）。

`docs/DETAILS.md` にこの変数の動作説明や条件付き測定値はありません。ソースにも性能値は記録されていないため、効果の大きさはこの調査からは示せません。

## 根拠

- 値の読み取り・parse と HIP compile guard: `engine/src/core/verify.cpp:333-343`; `engine/sycl/src/core/verify.cpp:148-154,187-190`。
- verifier の適用分岐・段番号: `engine/src/core/verify.cpp:2686-2715`; `engine/sycl/src/core/verify.cpp:1612-1637`。
- ring 値 store と publish payload: `engine/src/kernels/cuda/elementwise.cu:311-375`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:721-770`。
- 条件付き診断ログ: `engine/src/core/verify.cpp:1245-1260`; `engine/sycl/src/core/verify.cpp:800-814`。
