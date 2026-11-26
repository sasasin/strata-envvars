# `STRATA_COMMIT_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP エンジンの verifier が window の commit graph を作るとき、GDN 層の状態・畳み込み履歴を層ごとではなく複数層まとめて commit する経路を選びます。まとめ処理が使えない場合は層ごとの処理へ戻ります。値が有効なときは、QSA 層の indexer append も条件を満たせば複数層まとめます。生成する token や層の計算対象を選ぶ設定ではありません。読み取りと分岐は `Verifier::capture_commit` にあります（`engine/src/core/verify.cpp:3425-3454`, `3462-3473`）。

## 値と判定

Metal 以外の当該実装では `std::getenv` の結果について先頭 1 文字だけを検査し、先頭が `'0'` なら無効、それ以外なら有効です。文字列全体の parse、真偽値変換、空白除去はしません（`engine/src/core/verify.cpp:3448-3452`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の `STRATA_GPU_METAL` なしの build | 有効 | 空文字、`1`、`true`、`false`、` 0` など先頭が `0` でない値 | `0`、`0anything`、`00`、`0 ` など先頭が `0` の値 |
| `STRATA_GPU_METAL` build | 無効（環境値を読まない） | なし | 常に無効 |

空文字は設定済みでも先頭文字が終端文字 `\0` なので有効です。`false` も先頭が `f` のため有効で、`0anything` は文字列全体が数値として不正でも無効です。大文字小文字や後続文字は判定に影響しません（`engine/src/core/verify.cpp:3448-3452`）。

## 有効になる条件

- CUDA/HIP で `STRATA_GPU_METAL` が定義されていない build であること。Metal build は常に層ごとの GDN 処理を使います（`engine/src/core/verify.cpp:3448-3452`）。
- verifier が `capture_commit` を実行する経路であること。通常の verifier 実行では `run` が window graph と commit graph を capture します（`engine/src/core/verify.cpp:3776-3839`）。
- batched GDN commit には GDN 層があり、必要な各層の `ssm_norm.weight` が見つかることが必要です。重みが欠けると `ok` が false になり、commit capture は失敗します（`engine/src/core/verify.cpp:3454-3469`, `3498-3512`）。
- batched GDN kernel が受け付けない場合は層ごとの経路へ fallback します。CUDA/HIP kernel は `STRATA_GDN_SPLIT` の先頭文字が `1`、`STRATA_GDN_COMMIT_SPLIT` の先頭文字が `0`、または `STRATA_DBG_GDN` の先頭文字が `1` のとき batched kernel を起動せず `false` を返します。また、GDN 層数が 65535 を超える、window 行数が 1 未満または `kVerifyLongT` 超、`n_keep` が null、head 数が正でないか割り切れない場合も batch を拒否します（`engine/src/kernels/cuda/verify_kernels.cu:1231-1244`）。この判定は helper の初回呼び出し時に static cache されます。
- QSA 層のまとめ処理は `g_no_batch_kv` が false であること、indexer の重みが揃うこと、層数上限および `max_cells` の一致条件を満たすことが必要です。条件を満たさない場合は QSA 層ごとの append 処理になります（`engine/src/core/verify.cpp:3471-3497`, `3523-3536`）。

## 実行時の詳細

`commit_exec_` が未作成の場合に commit graph を capture し、CUDA/HIP build では `static const bool` の初期化 lambda が `STRATA_COMMIT_BATCH` を評価します。そのため読み取りはプロセス内の最初の該当 capture 時だけで、以後の verifier や実行中の環境変更では値が再評価されません（`engine/src/core/verify.cpp:3425-3427`, `3448-3452`）。Metal build は同じ static 値を `false` に固定します。

有効なら GDN 層数と重みを調べて `gdn_commit_layers` を呼び、kernel が対応可能な場合は履歴と状態の commit を層まとめで行います。コメントは層ごとの 2 launch ずつから 2 launch にし、約 70 graph node を減らすこと、および層ごとの算術は bitwise に同じであることを設計上の説明として述べています。実測条件はこのソース箇所に記載されていません（`engine/src/core/verify.cpp:3445-3447`, `3462-3469`）。GDN batch が成立しなければ通常の層ループで `gdn_conv_commit` と `gdn_step_norm_multi` を呼びます（`engine/src/core/verify.cpp:3498-3521`）。

`max_t_`（`--lookup-max-t` による window 上限）が `kVerifyMaxT` より大きく、GDN batch が成立しない場合、per-layer `gdn_step_norm_multi` に上限があるため capture は失敗し、`verify commit: windows past <上限> tokens (--lookup-max-t) need the batched GDN commit (unset STRATA_COMMIT_BATCH=0, STRATA_GDN_SPLIT, STRATA_GDN_COMMIT_SPLIT=0)` を `err` に設定します（`engine/src/core/verify.cpp:3504-3510`）。CUDA の capture / instantiate に失敗した場合も `verify: commit capture: ...` または instantiate 側のエラーを返します（`engine/src/core/verify.cpp:3545-3559`）。SYCL の `Verifier::capture_commit` は `STRATA_COMMIT_BATCH` を参照せず、別の `STRATA_SYCL_GDN_STATE_COMMIT` を読みます（`engine/sycl/src/core/verify.cpp:2204-2243`）。

## ログと測定値

この環境変数の有効・無効を通知する専用ログは確認できません。値が先頭 `0` で GDN 層があり `--lookup-max-t` の window が `kVerifyMaxT` を超える場合、上記の `err` が verifier の失敗として呼び出し元に返ります。commit launch の実行時エラーは `verify: commit launch: ...`、同期エラーは `verify: commit: ...` として返されます（`engine/src/core/verify.cpp:3504-3510`, `4550-4574`）。

約 70 graph node 減という数値は実装コメントにある設計説明で、計測条件や再測定結果ではありません（`engine/src/core/verify.cpp:3445-3447`）。

## 根拠

- `engine/src/core/verify.cpp:3425-3452` — verifier commit capture、Metal 分岐、環境変数の読み取りと値判定。
- `engine/src/core/verify.cpp:3453-3521` — GDN / QSA の batching 条件、層ごとの fallback、window 上限エラー。
- `engine/src/kernels/cuda/verify_kernels.cu:1231-1252` — GDN batch kernel の追加条件と失敗時の戻り値。
- `engine/src/core/verify.cpp:3545-3559`, `4550-4574` — commit graph 作成・launch の失敗処理。
- `engine/sycl/src/core/verify.cpp:2204-2243` — SYCL 実装は別の変数を参照。
