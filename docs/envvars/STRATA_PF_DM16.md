# `STRATA_PF_DM16`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

HIP の gfx11 向け fused native prompt expert 経路で、F16 down kernel が expert ごとの down 出力行を `Dm` に FP32 でなく FP16 として書き、combine 側も FP16 入力として読むよう要求します。FP16 化するのは down rows であり、対応する combine は `moe_combine16` です。対象経路を通らない実行ではこの変数による動作はありません。

## 値と判定

| 環境値 | `pf_dm16()` の判定 | 結果 |
|---|---|---|
| 未設定 | false | FP16 down rows を要求しない |
| 空文字 | false | FP16 down rows を要求しない |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | true | 条件がそろえば FP16 down rows を使う |
| その他（例: `0`, `true`, ` 1`） | false | FP16 down rows を要求しない |

文字列全体の parse、数値変換、大文字小文字変換はありません。`prefill.cpp` の `pf_dm16()` は最初の呼び出し時に `static const bool` として結果をキャッシュするため、その後の環境変更は反映されません（`src/prefill/prefill.cpp:557-560`）。

## 有効になる条件

- この設定が読み取られ、効果を持つのは HIP ビルドの gfx11（gfx1100/1101/1102/1103/1150/1151）向け F16 fused kernel 経路です。F16 device のコンパイル対象は `src/prefill/moe_f16_common.cuh:38-43` にあります。CUDA 経路や gfx12 経路ではこの DM16 切り替えは実装されていません。
- prompt の layer が fused native expert 経路 (`fused_nat`) を通る必要があります。fused 経路でない layer や通常の MMQ/FP16 経路では `pf_dm16()` を使いません（`src/prefill/prefill.cpp:4735-4740,4827-4843`）。
- 下方向の kernel が F16 である必要があります。実装上は `STRATA_PF_F16` による F16 down (`f16 && (f16kq::covers_down(...) || f16_d(...))`) または gfx1151 の Q8_0 down default (`f16_q8d`) が該当します。それ以外の down kernel は従来形式です（`src/prefill/moe_fused_iq.cu:2137-2144,2179-2190`）。従って `STRATA_PF_DM16=1` 単独では F16 kernel 自体を有効にしません。
- さらに prompt 呼び出し側が `rows_cpu == 0`、`!peer_now`、`m.shared` と `m.bo` のアドレスがともに 16-byte aligned の場合だけ `want_dm_f16(true)` を渡します。CPU expert rows がある場合、peer 経路の場合、または alignment 条件を満たさない場合は DM16 を要求しません（`src/prefill/prefill.cpp:4827-4829`）。

## 実行時の詳細

HIP の起動処理は engine が環境スイッチを読む前に GPU 情報を得て `apply_arch_defaults()` を呼びます（`src/program/generate.cpp:3790-3807`）。Windows の integrated gfx1151 では `igpu_default_env()` が `STRATA_PF_DM16=1` を既定値として返します（`src/core/arch_defaults.cpp:169-190`）。既定値適用側は変数が既に設定済みなら値を問わず維持し、未設定の場合だけ `_putenv_s` / `setenv(..., 0)` で設定します（`src/core/arch_defaults.cpp:195-200,284-289`）。この表への適用条件は Windows かつ gfx1151 で、表自体も integrated GPU の場合に限り返されます（同 `:151-153,172-190`）。したがってこの条件では、明示した空文字や `0` などは既定 `1` に置き換えられず、上記の reader 判定が使われます。他 OS、他 gfx、discrete GPU にはこの既定値注入はありません。

各 fused native layer の直前に `want_dm_f16(...)` が呼ばれ、`experts_native()` は down が対象 F16 kernel かを確認して `d16` を決め、最後に `dm_f16_used()` で実際に書いた形式を呼び出し元へ返します（`src/prefill/prefill.cpp:4827-4840`; `src/prefill/moe_fused_iq.cu:2095-2103,2137-2144`）。DM16 が使われる場合は combine で `moe_combine16()` を呼びます。CPU rows がある場合はこの分岐に入らず、FP32 combine 側へ進みます（`src/prefill/prefill.cpp:6130-6138`）。F16 down epilogue は値を FP16 に飽和させて格納するとコメントされています（`src/prefill/moe_f16_common.cuh:227-230`）。

この変数自体について、Strata のコードに無効値の警告やエラー出力はありません。Windows integrated gfx1151 で既定値群が新たに設定された場合は、起動時の integrated GPU prompt set ログに適用されたスイッチ名が列挙されます（`src/core/arch_defaults.cpp:284-298`）。それ以外に DM16 専用の有効化ログは確認できません。

## 根拠

- `src/prefill/prefill.cpp:556-560` — 環境値の読み取り、先頭文字判定、static cache。
- `src/program/generate.cpp:3790-3807` — HIP 起動時の arch defaults 適用順と integrated GPU 判定。
- `src/core/arch_defaults.cpp:151-153,169-200,284-298` — Windows gfx1151 integrated GPU 向け `1` の既定値、およびユーザー設定を維持する処理。
- `src/prefill/prefill.cpp:4735-4740,4827-4843,6130-6138` — 対象 layer、要求条件、実際に使った形式に応じた combine 分岐。
- `src/prefill/moe_fused_iq.cu:2095-2103,2137-2144,2178-2190` — down kernel が DM16 を選択して適用する条件。
- `src/prefill/moe_f16_common.cuh:38-43,227-245` — gfx11 F16 device guard と FP16 down row 格納。
