# `STRATA_SYCL_EXPERT_STAGE_COPY`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は SYCL verifier の grouped expert staging が使う重み blob のコピー方式を選びます。staging 経路では `0` が `fetch_blobs`、非 `0` が SYCL カーネル `copy_expert_stage_tiled` を選びます。expert の計算自体はその後も `native_expert_grouped` で行います。読み取りは `Verifier::record_window` 内の grouped lambda にあり、環境変数が未設定なら `0` です（`sycl/src/core/verify.cpp:1648-1668`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7944-7957`）。

## 値と判定

値は `std::getenv` で取得し、設定されていれば `std::atoi` で整数変換します。文字列全体の妥当性確認はありません。未設定だけが明示的な既定値 `0` に置き換わり、空文字や数値に変換できない文字列も `atoi` の結果 `0` となります。数値の後ろの文字は `atoi` が読み進めないため、たとえば `1junk` は `1`、`0junk` は `0` です。先頭の空白や符号は `atoi` の整数変換規則に従います。変換結果の `0` か非 `0` かだけが後段で判定され、大文字小文字は関係ありません（`sycl/src/core/verify.cpp:1663-1668`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7947-7952`）。

| 条件 | 未設定 | tiled copy を選ぶ値の例 | `fetch_blobs` を選ぶ値の例 |
|---|---:|---|---|
| staging 関数まで到達 | `0` | `1`, `-1`, `1junk` | `0`, `0junk`, 空文字, `true`, `false`, `junk` |

整数型で表現できないほど大きな数値を `atoi` に渡した場合の結果は C/C++ の変換仕様上保証されないため、ここでは有効値として扱いません。

## 有効になる条件

この値がコピー方式を変えるには、次の条件をすべて満たす必要があります。

- SYCL の verifier が native expert 経路を実行していること。対象の読み取り箇所は `sycl/src/core/verify.cpp` にあります（同 `:1648-1652`）。
- `lay.native` であること。そうでなければ別の `moe_grouped_s2` 経路を使い、この変数を読みません（同 `:1649`, `:1673-1675`）。
- `b60_layout_requested()` が false、`gy == 0`、`device_plan_` が true であること（同 `:1654-1659`）。`STRATA_PRIVATE_B60_DECODE_LAYOUT` の判定は `sycl/include/b60_layout_state.hpp:7` にあります。
- `STRATA_VERIFY_NO_HOST` と `STRATA_SYCL_EXPERT_STAGE` が `env_on` 判定で有効であること。`env_on` は未設定・空文字・`0` 始まりを false、それ以外を true とします（`sycl/src/core/verify.cpp:149-152,1658-1659`）。
- staging 関数の layout・容量・workspace・alignment・in-order queue・batch 条件を満たすこと。特に layout は `n_embd == 2560`、`n_ff == 640`、`d_type == 42`、`d_row == 180` に加え、`gu_type` が 16/22/29 のいずれかで対応する row size・offset・総 byte 数が一致する必要があります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7915-7920,7931-7937`）。
- `STRATA_GROUPED_V1` が有効でないこと。これはファイル内の `env_on` でプロセス内初期化時に読み取られ、true の場合 staging 関数は通常の `native_expert_grouped` へ戻ります（同 `:3689-3692,7302-7306,7931-7940`）。

条件を満たさない場合、関数は `copy_mode` を使わず通常の `native_expert_grouped` にフォールバックします。なお batch 数は別変数 `STRATA_SYCL_EXPERT_STAGE_GROUPS` から取得し、未設定時は `8` です。staging 関数が受け付ける値は 1〜16 で、範囲外なら同じく通常経路へ戻ります（`sycl/src/core/verify.cpp:1663-1668`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7849,7931-7940`）。

## 実行時の詳細

対象値は `record_window` が grouped lambda を実行するときに直接 `getenv` され、関数内 static には cache されません（`sycl/src/core/verify.cpp:940,1648-1668`）。通常の graph 経路では `record_window` は graph の capture 時に呼ばれ、capture 済み graph は再利用されるため、再生のたびにこの環境変数を読み直すわけではありません（同 `:1994-2008`）。`STRATA_VERIFY_EAGER` が設定される経路では `run` 中に `record_window` が呼ばれるため、その実行ごとに読み直します（同 `:2474-2477`）。したがって graph capture 後の環境変更は既存 graph の記録済みコピー方式を変えず、eager 経路では次の `record_window` 呼び出しに反映されます。

staging 関数が有効な場合、各 batch について metadata を準備し、`copy_mode == 0` なら `fetch_blobs`、それ以外なら tiled SYCL copy kernel で expert blob を workspace にコピーします。その後 workspace 内の blob に pointer を付け替え、同じ grouped expert 計算を実行します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7942-7957`; tiled kernel の source/target コピーは同 `:7895-7913`）。この変数が選ぶのは blob のコピー方法です。

## ログと測定値

この変数の値や選択したコピー方式を直接表示するログは、確認した Strata ソースにありません。条件不足時の fallback にも、この変数を理由とする警告はありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7931-7940`）。資料 `docs/DETAILS.md` にこの変数の記載は見つかりませんでした。比較測定値も確認できないため、性能差は記載しません。

## 根拠

- `sycl/src/core/verify.cpp:149-152,1648-1675` — helper の値判定、親条件、環境変数の読み取り、呼び出し。
- `sycl/src/core/verify.cpp:940,1970-1978,1994-2008,2474-2477` — `record_window` と graph capture / eager 実行。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692,7302-7306,7849,7915-7957` — `STRATA_GROUPED_V1`、layout と staging の検証、コピー分岐、fallback。
- `sycl/include/b60_layout_state.hpp:7` — Battlemage layout 判定。
