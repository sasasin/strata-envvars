# `STRATA_PRIVATE_GR_UP_ROWS16`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の fused GR decode における up projection を、通常の `GfUp` の出力列単位の処理から、出力行を16行ずつまとめる `GrUpRows16` 系カーネルへ切り替える private opt-in です。これは GR 経路全体を有効化するスイッチではありません。`gr_up_rows16_enabled()` はこの変数に加えて `STRATA_PRIVATE_B60_DECODE_LAYOUT` と main actor 状態を要求し、さらに呼び出し箇所で `m.T == 4` を要求します。条件が揃わなければ従来の `GfUp` か別の通常 up 経路が使われます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2517-2526, 3103-3108`）。

この実験カーネルは BF16 up weights と low-rank activation を読み、`m.xn` に up projection の値を書きます。後続の `GfPostop` はその値をスコアとして読み、ゲート・正規化などを行い、`mixed` 出力を書きます（同 `:2703-2737, 2745-2759, 3103-3108`）。

## 値と判定

`gr_up_rows16_enabled()` 内で `std::getenv` の結果を関数内 `static const bool` に一度保存し、環境変数が設定されていて、かつ最初の1文字が ASCII `'1'` の場合だけ変数部分を true とします。文字列全体や整数としては parse しません（同 `:2517`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| すべての呼び出し | false | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `01` |

大文字小文字や後続文字は判定されません。空白の trim、数値妥当性検査、境界値検査もありません。`01` は先頭が `0` のため無効です。未設定・空文字・無効値に対する警告や fallback 設定はなく、bool が false になります（同 `:2517`）。

## 有効になる条件

値の判定が true でも、以下を満たす呼び出しでのみ16行カーネルが選ばれます。

- SYCL 実装の `fused_gr.dp.cpp` が実行経路にあること。このファイルは SYCL ターゲットのソースとして CMake に登録されています（`sycl/CMakeLists.txt:42`）。この変数を読む実装はこの SYCL ファイル以外にありません。
- `STRATA_PRIVATE_B60_DECODE_LAYOUT` の値の先頭文字が `'1'` であること。同変数も `getenv` の関数内 static 判定です（`sycl/include/b60_layout_state.hpp:7`）。B60 layout を要求しているのに weights が未 pack の状態で main graph を記録すると、`B60MainActorScope` が `std::logic_error("B60 main graph recorded while weights are raw")` を投げます（同 `:14-20`）。この例外は本変数の値判定そのものではなく、親となる B60 layout 経路の失敗です。
- 呼び出し時に `b60_main_actor()` が true であること。`B60MainActorScope` は layout 要求または `STRATA_PRIVATE_BMG_SINGLE_ACTOR` 要求があると actor 状態を立てます。確認できた生成箇所は verifier の `Verifier::record_window` です（`sycl/include/b60_layout_state.hpp:14-20`; `sycl/src/core/verify.cpp:940-942`）。ただし本変数自身が layout 要求も必要とするため、single actor だけでは足りません。
- `gf_enabled(st,m)` が true であること。これは別の `STRATA_PRIVATE_GR_F32_REG`（`atoi != 0`）に加え、`1 <= m.T <= 4`、`STRATA_GR_DOWN_SLICED` が有効、`STRATA_GR_MORE_GROUPS` と `STRATA_GR_LARGE_GRF` が無効、`STRATA_GR_NORM_SPLIT` が有効、`STRATA_GR_UP_COLS == 16`、`STRATA_GR_UP_ILP` が無効、GPU 世代が Battlemage であることを要求します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`; 各設定の判定は同 `:812-836, 1200-1210`）。
- up dispatch に到達したうえで `m.T == 4` であること（同 `:2521-2526, 3103-3108`）。1〜3 token の dispatch ではこの変数が true でも `GfUp` に戻ります。
- 通常経路では `STRATA_PRIVATE_GR_F32_PHASE` が unset / `both` / `up` のいずれかなら `gf_dispatch_up` に進みます。`gf_phase("up")` が false の場合でも、`STRATA_PRIVATE_GR_SILU_FROM_LO`（`atoi != 0`）が有効なら `launch_gr_up_from_lo` を経由します（同 `:2530-2532, 2690-2693, 3465-3470`）。後者でも本変数と `m.T == 4` の条件が必要です。
- `STRATA_PRIVATE_GR_SOA_CACHE` が有効な場合は down 側の cache 経路がさらに `gf_enabled`、phase が down で up ではないこと、`STRATA_PRIVATE_GR_SILU_FROM_LO` と本変数が有効であることを検査します。条件を満たさない場合は `std::logic_error("B60 GR cache requires the measured GR control combination")`、cache pointer がない場合は `std::logic_error("B60 missing GR decode cache")` になります（同 `:3160-3166`）。

## 実行時の詳細

`gr_up_rows16_enabled()` の環境値は最初の関数呼び出し時に static 保存されます。後からプロセス環境を書き換えても、この値の判定には反映されません。親の `STRATA_PRIVATE_B60_DECODE_LAYOUT` も helper 内 static 保存です。`b60_main_actor()` は static cache ではなく thread-local actor state を返します（`sycl/include/b60_layout_state.hpp:7, 14-20`; `sycl/src/kernels/cuda/weight_permute.dp.cpp:103-107`）。

通常の `gf_dispatch_up` は `m.T` に応じた `gf_launch_up<E>` を選びます。そこでは、本変数が有効かつ `m.T == 4` の場合に限り、`STRATA_PRIVATE_GR_SOA_CACHE`、次に `STRATA_PRIVATE_GR_2D_PAIR` の順で別の up 計算カーネルを選択し、どちらも無効なら `gp_launch_compute`（`GrUpRows16`）を起動します。いずれも16行の結果を `m.xn` に格納してから `GfPostop` を実行します。本変数が無効、または `T != 4` の場合は標準 `GfUp<E>` を起動し、その後同じ post-op に進みます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2745-2759, 3076-3093, 3103-3108, 3117-3119`）。

SiLU-from-low-rank の経路では `launch_gr_up_from_lo` が同じ `gr_up_rows16_enabled() && m.T == 4` を判定し、true なら `gf_dispatch_up` に渡します。false なら `STRATA_PRIVATE_GR_LO_VEC4` が有効かつ `2 <= m.T <= 4` の場合の別経路、または標準 `gr_up_from_lo_kernel` を選びます（同 `:2521-2526, 3470`）。

## ログと測定値

この変数の判定や rows16 選択を知らせるログはありません。通常 up dispatch の rows16 分岐自体は失敗を投げず、条件不成立時は上記の標準 up 実装へ進みます。別途 SOA cache 経路では前節の `logic_error` があり得ますが、その原因判定は cache 経路の制約です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2517-2526, 3103-3108, 3160-3166`）。

調査対象 commit の `docs/DETAILS.md` を含む `docs` と SYCL ソースに本変数名の追加説明・測定結果は見つかりませんでした。`data/settings-register.json` は本変数を private opt-in、SYCL、research と記録し、「integration lane measured nothing on it」としています。同レジストリは候補一覧・メタデータであり、上記の実装動作の根拠にはしていません（`data/settings-register.json:31089-31117`）。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2517-2526` — 環境値判定と up-from-low 呼び出し側の token-count 分岐。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2693` — Battlemage 向け F32 経路と phase 条件。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2703-2759, 3103-3119` — rows16 up 計算、post-op、dispatch。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:3160-3166, 3465-3470` — cache 制約と fused GR の up 経路選択。
- `sycl/include/b60_layout_state.hpp:7, 14-20`; `sycl/src/core/verify.cpp:940-942`; `sycl/src/kernels/cuda/weight_permute.dp.cpp:103-107` — B60 layout と main actor 状態。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:812-836, 1200-1210`; `sycl/CMakeLists.txt:42` — 関連する GR 条件と SYCL ソース登録。
