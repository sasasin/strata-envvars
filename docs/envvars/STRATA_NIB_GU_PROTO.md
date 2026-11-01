# `STRATA_NIB_GU_PROTO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

4-bit 化した expert slot の CUDA gate/up 計算で、通常の S/P skeleton の代わりに gu-proto variant 31（`nibx_gu_kernel<TG, 2>`）を選ぶ opt-in です。group の activation を shared memory に staging してから 2 row-block ずつ計算します。down projection や一般の GGUF slot のカーネルを切り替える変数ではありません。適用時も既存の row dot を使い、変わるのは activation の staging と row-block の処理配置です。`STRATA_EXPERT_NIBBLE` が有効になり、実際に変換された layer の gate/up が実行されることが前提です。

## 値と判定

`std::getenv` の値を `std::atoi` で整数化し、結果がちょうど `1` または `31` の場合に variant `31` とします。`1` は `31` に変換され、`31` はそのままです。それ以外の整数値はすべて `0`（無効）になります。範囲 clamp や無効値の警告はありません。

| 環境値 | `atoi` の結果 | 選択 |
|---|---:|---|
| 未設定 | 0 相当 | 無効 |
| 空文字、数値として読めない文字列 | 0 | 無効 |
| `0`, `2`, `30`, `32`, `-1` | 表記の整数 | 無効 |
| `1`, `31` | 1 または 31 | variant 31 |
| `+1`, `01`, `31tail`, `1.5` | 数値部分の変換結果が 1 または 31 | variant 31 |

`atoi` は文字列全体の厳密な検証をしません。先頭の空白と符号を許し、数値の後ろに続く文字は判定に使われません。たとえば `31tail` は有効ですが、`true` は無効です。値を設定したこと自体ではなく、変換後の整数で判定します。

根拠: `src/kernels/cuda/iq_kernels.cu:4916-4927`。

## 有効になる条件

- **ビルドと backend:** 4-bit nibble slots のカーネルは `STRATA_EXPERIMENTAL_SM60` が定義された CUDA build に限られます。`STRATA_EXPERT_NIBBLE_BUILT` は HIP / Metal 等では 0 です。`STRATA_NIB_GU_PROTO` 自体はこの環境判定関数にありますが、非 nibble build では `nib_layout(L)` が常に false になり、環境値を読んで kernel を選ぶ経路に入りません。nibble slot の起動条件として generate 側は CUDA device が compute capability 6.0 であることも確認します。
- **別の機能設定:** `STRATA_EXPERT_NIBBLE=1` によって対象 layer が nibble slot に変換されている必要があります。unset または空値ではこの conversion は要求されません。通常の実行では `STRATA_EXPERT_NIBBLE` の設定・起動条件を満たさない限り、この変数だけでは何も切り替わりません。
- **対象データ:** 変換対象の gate/up 型は IQ2_S (22), IQ3_XXS (18), IQ3_S (21)、形状は `n_embd=2560`, `n_ff=640` です。`nibx_launch` は variant 31 をこの3型にだけ dispatch します。
- **入力 alignment:** 16-byte staging のため `X` が 16-byte aligned のときだけ variant kernel を呼びます。値が有効でも alignment 不足なら、メッセージなしで通常の nibble S/P kernel に進みます。
- **上書き経路:** bench / parity 用に `native_expert_nib_set_variant()` が `g_nib_variant` を明示設定した場合、`g_nib_variant < 0` のときだけ参照されるこの環境変数の選択は使われません。通常の production 初期値は `-1` です。

根拠: `include/strata/core/expert_nibble.hpp:33-38,59-65,96-101`; `src/program/generate.cpp:2682-2717,4159-4183`; `src/kernels/cuda/iq_kernels.cu:5288-5297,4931-4958`; `src/kernels/cuda/nib_gu_proto.cuh:125-136`; `src/kernels/iq_nibble_parity.cpp:664-682`。

## 実行時の詳細

環境値の読み取りは、nibble layout の gate/up dispatch が `launch_gu_nib()` に入り、`g_nib_variant < 0` のときに初めて行われます。関数内の `static const int` に保存されるため、同一プロセスでは初回判定後に環境を変更しても再評価されません。nibble layer が実行されないプロセスでは読み取り自体が起きません。

読み取り結果が variant 31 で、`X` の alignment が合い、型が対応する場合、`nibx_gu_kernel` を起動して当該 gate/up の出力を書きます。group の entry 数が `GRP_NC` 以下なら activation を一度 staging し、各 block 内の 2 row-block で使います。entry 数がそれを超える場合は各 row-block ごとに chunks を staging します。alignment 不足や対応型でない場合はこの環境選択からの起動要求が失敗扱いにならず、既定の `nib_gu_kernel` に fallback します。

有効な値を初めて読み込むと stderr に `native_expert_grouped: STRATA_NIB_GU_PROTO: 4-bit gate/up kernel gu-proto 31` を一度出します。このログは parse 結果の通知であり、alignment / 型条件による fallback の有無は示しません。未設定・無効値はこのログを出しません。環境選択による dispatch 失敗でプロセスを終了する経路はありません。内部 API で variant を強制した bench / parity 経路は別で、16-byte alignment または variant/type 対応がないと `gu-proto variant ... is not built (or x is not 16-aligned)` を stderr に出して `exit(1)` します。

既存の `docs/OLDER_GPUS.md` は以前の測定値を載せていますが、同じ節に「このコードでは未測定」と明記しています。したがって、この commit の速度向上は確認済み事実としては記載しません。資料の記述では one GP100 die で gate/up 単体の測定値は T=1 で 54–57 µs 対 67–72 µs、T=2–4 で 1.22–1.39 倍ですが、engine 0.1.45.3 等の旧測定条件に限られます（`docs/OLDER_GPUS.md:237-247`）。

## 根拠

- 環境値 parse、許可する整数、stderr log、static cache: `src/kernels/cuda/iq_kernels.cu:4916-4927`。
- nibble gate/up dispatch、alignment fallback、通常 kernel への fallback: `src/kernels/cuda/iq_kernels.cu:4931-4964`。
- variant 31 と型 22 / 18 / 21 の kernel mapping: `src/kernels/cuda/nib_gu_proto.cuh:125-136`。
- staged kernel と entry 数に応じた staging 範囲: `src/kernels/cuda/nib_gu_proto.cuh:69-109`。
- nibble build 条件と変換対象形状・形式: `include/strata/core/expert_nibble.hpp:33-38,59-65,96-101`。
- nibble feature の startup 条件と warning / fallback: `src/program/generate.cpp:2682-2717,4159-4200`。
