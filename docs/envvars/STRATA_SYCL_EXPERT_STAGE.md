# `STRATA_SYCL_EXPERT_STAGE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

SYCL の verifier が native expert の grouped 計算を行うとき、通常の `native_expert_grouped` の代わりに staged 版 `native_expert_grouped_staged` を呼ぶための opt-in です。staged 版は expert のメタデータを準備し、expert weight blob を workspace にコピーしてポインタを workspace 内へ付け替えてから、既存の grouped 計算を実行します。対応しない layout や実行条件では staged 版の中で通常版へ戻ります。環境変数自体はログを出さず、生成 token の選択や verifier の別アルゴリズムを直接変更する処理もありません（`sycl/src/core/verify.cpp:1648-1676`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7895-7913,7915-7958`）。

## 値と判定

`verify.cpp` 内の `env_on(name)` が `getenv` の結果を調べます。未設定、空文字、または先頭文字が `0` の値は false、それ以外は true です。文字列全体の比較や数値変換はしません（`sycl/src/core/verify.cpp:149-152`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `env_on("STRATA_SYCL_EXPERT_STAGE")` の判定 | 無効 | `1`, `true`, `yes`, ` 1` など先頭が `0` でない文字列 | 空文字、`0`, `0anything`, `00x` |

先頭文字だけを見るため、大文字小文字や数値としての妥当性は検査しません。たとえば `false` や `garbage` も値判定上は true です。`00x` は先頭が `0` のため false です。既定は無効です（`sycl/src/core/verify.cpp:149-152,1658-1668`）。

## 有効になる条件

- SYCL verifier の `grouped` 経路で native expert layout が使われ、`gy == 0` であること。非 native layout は別の `moe_grouped_s2` を呼び、この変数の分岐を通りません（`sycl/src/core/verify.cpp:1648-1676`）。
- Battlemage layout が要求されていないこと（`!b60_layout_requested()`）、`device_plan_` が有効であること、`STRATA_VERIFY_NO_HOST` が `env_on` 判定で true であること。`device_plan_` は `STRATA_VERIFY_DEVICE_PLAN` が存在して `atoi` が非 0、かつ `all_resident_` と `always_publish_` がどちらも false の場合にだけ true です（`sycl/src/core/verify.cpp:852-855,1658-1659`）。`STRATA_VERIFY_NO_HOST` はこの分岐では先頭文字が `0` でない設定値を要求します。
- staged 関数が対応する layout / 実行条件であること。`n_embd == 2560`, `n_ff == 640`, `d_type == 42`, `d_row == 180` に加え、`gu_type` が 16 / 22 / 29 のいずれかで、その型ごとの `gu_row` と offset・byte 数の整合条件を満たす必要があります。`g_grouped_v1` が true、capacity が 1..80 の範囲外、workspace 不在・不足、scratch/workspace の 16-byte alignment 不足、queue が in-order でない場合も通常版に fallback します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7915-7940`）。
- `STRATA_SYCL_EXPERT_STAGE_GROUPS` が未設定なら最大 batch group 数は 8、設定時は `atoi` の結果です。1..16 以外なら staged 関数が通常版へ fallback します。workspace に収まる blob 数にさらに制限されます（`sycl/src/core/verify.cpp:1663-1668`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7849,7931-7944`）。
- `STRATA_SYCL_EXPERT_STAGE_COPY` が未設定なら copy mode は 0。設定値は `atoi` で読み、0 のとき `fetch_blobs`、0 以外のとき tiled copy kernel を選びます。これは staged 分岐が成立した場合の転送経路を選びます（`sycl/src/core/verify.cpp:1663-1668`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7947-7952`）。

## 実行時の詳細

対象変数は `grouped` を呼び出す際に都度 `getenv` され、関数内 static cache ではありません。ただし通常の graph 経路では `record_window` 中の graph capture 時に分岐が記録され、その後の graph replay では環境変数を読み直しません。`STRATA_VERIFY_EAGER` が設定される経路では window ごとに `record_window` が実行されるため、その実行ごとに分岐を評価します（`sycl/src/core/verify.cpp:1658-1668,1994-2008,2474-2477`）。

staged 処理は最大 batch 数と workspace 容量から実際の batch 数を決め、各 batch について metadata を準備し、workspace へ blob をコピーしてポインタを付け替えた後、`native_expert_grouped` を呼びます。copy mode 0 は `fetch_blobs`、その他は tiled copy kernel を使います。条件不適合時は追加の警告なしに通常の `native_expert_grouped` へ戻ります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7942-7958`）。

## ログと測定値

この分岐や staged 関数には、選択・fallback を示す専用ログはありません。分岐条件の不成立や staged 関数の検査条件不適合は通常版への fallback となります（`sycl/src/core/verify.cpp:1658-1676`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7931-7940`）。調査対象ソースと `docs/DETAILS.md` には、この変数による性能・正確性の測定値を確認できませんでした。

## 根拠

- `sycl/src/core/verify.cpp:149-152` — `env_on` の判定規則。
- `sycl/src/core/verify.cpp:852-855,1658-1676` — device plan 条件、staged 分岐、補助 tuning 値、通常経路。
- `sycl/src/core/verify.cpp:1994-2008,2474-2477` — graph capture と eager 実行時の `record_window` 呼び出し。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7849,7895-7913,7915-7958` — staged copy の構成、対応 layout、fallback、batch 処理。
