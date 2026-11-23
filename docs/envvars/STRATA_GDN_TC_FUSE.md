# `STRATA_GDN_TC_FUSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の GDN split Tensor Core scan に出力正規化を融合し、scan 内で正規化後の FP16 出力 `y16` まで書くかを制御する。未設定時は融合を許可し、`0` 相当では別の `gdn_out_norm_kernel` に正規化を任せる。通常の非 split Tensor Core scan、再帰カーネル自体の選択、状態更新を有効化する変数ではない。値を読むのは `gdn_recurrence_impl` の CUDA 専用分岐である（`engine/src/prefill/kernels.cu:3075-3080,3182-3202`）。

出力正規化の融合は split scan のみ実装され、FP32 の `o` ではなく `y16 = o * rsqrt(mean(o^2) + eps) * gamma` を scan が出力する。実装コメントは後続 kernel の1 pass を省く一方、別の和の順序になるため bitwise ではないと説明している（`engine/src/prefill/gdn_tc.cuh:449-456`）。この環境変数単独の速度・精度測定値は資料に見つからなかった。

## 値と判定

関数ローカル `static const bool` の初期化時に `std::getenv` で値を読み、未設定なら `true`、設定済みなら `std::atoi(v) != 0` とする。文字列全体の検証や `true` / `false` の特別扱いはない（`engine/src/prefill/kernels.cu:3198-3199`）。

| 条件 | unset | 融合を許可 | 融合を止める |
|---|---|---|---|
| CUDA の該当 GDN 分岐に到達 | `true` | `1`, `2`, `-1`, `1x` など、`atoi` の結果が非0 | 空文字、`0`, `false`, `0anything`, 数字で始まらない文字列など、`atoi` の結果が0 |
| HIP build | この変数は読み取られない | 該当なし | 該当なし |

空白や符号を含む数値文字列は `atoi` の変換規則に従い、先頭の数値部分の後ろに文字があっても変換結果が0でなければ有効になる。範囲外の数値文字列の結果は C `atoi` の仕様上、定義されない。CLI 引数や別環境変数からこの値を上書きする処理は確認できなかった。

## 有効になる条件

- `gdn_recurrence_impl` の通常経路で、CUDA build（`!__HIPCC__`）の Tensor Core dispatch に到達すること。HIP 側には当該読み取りがない（`engine/src/prefill/kernels.cu:3080-3092,3182-3202`）。
- split Tensor Core scan が実行されること。自動 dispatch では `STRATA_GDN_TC` が非0で、`T >= 128` の Tensor Core scan が通常プランで失敗した後に split fallback を試す経路などが該当する。`STRATA_GDN_TC` が未設定または0なら、この設定だけでは Tensor Core scan は選択されない（`engine/src/prefill/kernels.cu:3186-3189,3226-3237`; `docs/DETAILS.md:1803`）。
- 出力付き呼び出しであり、`gdn_tc_tiles()` が1を返すこと。コードはこの条件を満たさない場合 `tcnp` を null にし、融合しない。2 tiles/head では head 全体の正規化を一つの block で行えないため、別の正規化 kernel に進む（`engine/src/prefill/kernels.cu:1340-1355,3199-3202`）。
- probe が split path を強制する場合も同じ `tcnp` 条件が適用される。これは `gdn_probe_get()` の診断経路で、一般の CLI 引数による環境変数の優先順位とは別である（`engine/src/prefill/kernels.cu:3192-3209`）。

## 実行時の詳細

通常の prompt prefill から `gdn_recurrence` が呼ばれ、`gdn_recurrence_impl(..., with_out=true)` に入る。state-only 呼び出しでは `with_out=false` のため `tcnp` は null となり、この変数による融合は起きない（`engine/src/prefill/prefill.cpp:5205-5210,9340-9344`; `engine/src/prefill/kernels.cu:3273-3285,3301-3306,3199-3202`）。

融合が許可され、出力付きかつ1 tile/head の場合、split scan に正規化の入力 `z`, `gamma`, `eps` と出力先 `y16` を渡す。split scan が選択されても融合条件を満たさない場合は `normed` が false のままになり、scan 後に `with_out && !normed_any` の条件で `gdn_out_norm_kernel` を起動する（`engine/src/prefill/kernels.cu:3200-3202,3233-3237,3259-3269`; `engine/src/prefill/gdn_tc.cuh:449-456`）。

この値は `static` 初期化で一度だけ読み取られる。実行中に環境を変更しても再評価されず、最初の読み取り前に設定されている必要がある（`engine/src/prefill/kernels.cu:3198-3199`）。

## ログと測定値

この変数の有効・無効を知らせる専用ログはない。split Tensor Core scan の選択や理由を `GdnProbe` に記録する診断経路はあるが、通常経路でこの変数自体の値を出力しない（`engine/src/prefill/kernels.cu:3192-3199,3259`）。launch error が発生した場合は `check("gdn_recurrence")` から `cudaGetLastError()` を確認し、失敗時は `exit_device_error` に `prefill gdn_recurrence` と CUDA error string を渡す（`engine/src/prefill/kernels.cu:110-116,3271`）。

`docs/DETAILS.md` は `STRATA_GDN_TC=1` の Tensor Core scan について別途測定値を掲載するが、`STRATA_GDN_TC_FUSE` の比較測定ではない（`docs/DETAILS.md:1803`）。

## 根拠

- `engine/src/prefill/kernels.cu:3073-3080,3182-3202,3226-3269,3271-3285,3301-3306`
- `engine/src/prefill/gdn_tc.cuh:449-456`
- `engine/src/prefill/prefill.cpp:5205-5210,9340-9344`
- `docs/DETAILS.md:1803`
