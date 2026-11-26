# `STRATA_SM70_TABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の Volta（compute capability 7.0、sm_70）で、グループ化された native expert の mode 8、interleaved MMVQ、hyper-connection の fast norm/up を選べるようにする数値スイッチです。3つの機能は別々の条件で判定されます。Strata は同じ変数を CUDA カーネル実装内で読みます。起動時に CUDA デバイスの条件が合えば未設定の変数を `1` に補いますが、この既定注入がなくても、各機能は変数を直接読みます（`engine/src/core/nv_defaults.cpp:136-163,222-257`、`engine/src/program/generate.cpp:4421-4449`、`engine/src/kernels/cuda/iq_kernels.cu:6763-6802`、`engine/src/kernels/cuda/native_mmvq.cu:4189-4228`、`engine/src/kernels/cuda/fused_gr.cu:4073-4084`）。

## 値と判定

各カーネルの直接判定は `std::getenv` した文字列を `std::atoi` に渡し、変換結果が 0 でないかを見ます。数値全体の検証や範囲制限はありません。`atoi` は先頭の空白と符号を許し、先頭の数値部分を変換して後続文字を無視します。したがって `1`、`-1`、`+2`、` 1tail` は有効、`0`、`0tail`、空文字、`true`、`tail1` は無効です。数値として読める先頭部分がない文字列は 0 になります。`atoi` の範囲外入力の結果はコードで扱っていません（`engine/src/kernels/cuda/iq_kernels.cu:6782,6800`、`engine/src/kernels/cuda/native_mmvq.cu:4193`、`engine/src/kernels/cuda/fused_gr.cu:4082`）。

| 判定箇所 | unset（直接判定時） | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| mode 8（CUDA sm_70） | 無効。通常起動で既定注入の条件を満たすと `1` が設定される | `atoi(value) != 0`。例: `1`, `-1`, `2tail` | 空文字、`0`, `0tail`, `true`, 数字で始まらない文字列 |
| interleaved MMVQ（CUDA sm_70） | 無効 | `atoi(value) != 0` | 空文字、`0`, `0tail`, `true`, 数字で始まらない文字列 |
| fast norm/up（CUDA、Voltaのみ） | `STRATA_GR_FAST` も未設定なら無効 | `atoi(value) != 0` かつ現在デバイスが sm_70 | `atoi(value) == 0` または現在デバイスが sm_70 でない |

起動時の既定注入は CUDA ビルドで、可視デバイスが1台以上あり全台の compute capability が同じときに行われます。全台が sm_70 で、`STRATA_SM70_PERF` の先頭文字が `0` でなく、`STRATA_DEFAULTS` が `026`・`0.2.6`・`v0.2.6` のいずれでもなく、かつ `STRATA_SM70_TABLE` が未設定なら、Strata はプロセス環境へ `STRATA_SM70_TABLE=1` を設定します。既に設定されていれば空文字を含め値を保持します。混在 compute capability ではこの表を適用せず、`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` でも既定注入しません（`engine/src/program/generate.cpp:4421-4450`、`engine/src/core/nv_defaults.cpp:15-18,136-163,222-237`、`engine/include/strata/core/defaults_026.hpp:21-29`）。

対象変数を直接指定する CLI 引数は確認できません。`--gpu` は可視デバイスを変えるため、同一 compute capability かどうかを含む既定注入条件には間接的に影響します（`engine/src/program/generate.cpp:3781-3801,4421-4449`）。

既定注入を抑えるマスタースイッチがあっても、`STRATA_SM70_TABLE` を明示設定すればその値は保持され、カーネル側の直接判定が使われます。`STRATA_SM70_PERF` の抑止は先頭文字が `0` かどうかで見ますが、対象変数自身は `atoi` 判定です（`engine/src/core/nv_defaults.cpp:15-18,139-143,222-233`）。

## 有効になる条件

- **mode 8:** CUDA の sm_70 で、`STRATA_EXP_MODE` が mode 8 を上書きしていないことが必要です。`g_exp_mode` または `STRATA_EXP_MODE` の `atoi` 結果が 0 以上なら、そちらが優先されます。両方とも自動選択のままでも、部分グループの呼び出し（`grid_groups > 0 && grid_groups < cap_groups`）では CUDA layout の mode 0 を使います。mode 8 の fused gate/up はさらに対象量子化型、埋め込み幅、`n_ff % 32 == 0` などの条件を満たす場合に限られます（`engine/src/kernels/cuda/iq_kernels.cu:6763-6802,7196-7215`）。
- **interleaved MMVQ:** CUDA で compute capability 7.0、device ordinal が0〜15、`g_multi_exact` が有効、列数が1〜8、量子化型がコードの対象5種（23, 12, 13, 14, 11）であり、その型・列数・出力幅に対する Volta table の行数が0でない必要があります。条件を満たさない場合は通常の `native_mmvq` にフォールバックします。主な grouped-expert 呼び出しでは `q8_1_il` scratch があり、2 token 以上の場合に gate/up の interleaved 経路を検討し、down 側も同様に条件判定します（`engine/src/kernels/cuda/native_mmvq.cu:4202-4228,4230-4252`、`engine/src/kernels/cuda/shared_expert.cu:229-257`）。
- `STRATA_MMVQ_IL_PF=1` は別の任意設定で、sm_70 の interleaved MMVQ を有効化する `STRATA_SM70_TABLE` の代わりにはなりません。これも使うと該当する Volta 型・形状で追加の prefetch table を選びます（`engine/src/kernels/cuda/native_mmvq.cu:2350-2365,3964-3970`）。
- **hyper-connection fast norm/up:** `STRATA_GR_FAST` が設定済みなら、その `atoi` 結果が優先され、`STRATA_SM70_TABLE` による既定判定は使われません。未設定時は CUDA の現在デバイスが sm_70 で、対象変数の `atoi` 結果が非0なら fast 経路を選びます。実際の分岐は `STRATA_GR_FAST_BUILD` が有効なビルドの `launch_multi` にあり、通常の multi-read 分岐が対象です。Q8 hyper-connection read、RDNA 経路、または先行する v3 経路では別の処理が先に選ばれます（`engine/src/kernels/cuda/fused_gr.cu:48-53,1782-1795,4073-4084,4286-4320`）。
- 対象名を直接読む実装は CUDA カーネル側にあります。HIP の `native_mmvq_il_supported` 実装は常に false を返し、HIP の `cur_dev_volta()` も false です。CPU・Metal・サーバー側がこの値を独自に解釈するコードは確認できません（`engine/src/kernels/cuda/native_mmvq.cu:4255-4265`、`engine/src/kernels/cuda/fused_gr.cu:1404-1419`）。

## 実行時の詳細

通常の CUDA 起動では、引数解析後に visible GPU を調べ、全台が同じ compute capability の場合に `apply_nv_defaults` が各既定値を環境へ追加します。`setenv(..., 0)` を使うため既存値は上書きせず、変数を設定した場合は stderr に sm_70 の既定スイッチ一覧を出します（`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:222-257`）。

カーネル側の読み取り時期は経路ごとに異なります。

- mode 8 は `exp_mode()` の初回自動選択時にデバイスごとの `per_dev` 配列へ保存されます。`STRATA_EXP_MODE` 自体も関数内 `static` に一度だけ読みます。選択後にプロセス環境を書き換えても、そのデバイスの自動選択は更新されません（`engine/src/kernels/cuda/iq_kernels.cu:6763-6802`）。
- interleaved MMVQ は `il_arch_ok()` の初回判定をデバイスごとの `static ok[16]` に保存します。そこで対象変数を一度読み、以後の変更は再評価しません（`engine/src/kernels/cuda/native_mmvq.cu:4193,4202-4215`）。
- fast norm/up は対象変数を `gr_fast()` の呼び出しごとに読みます。ただし `STRATA_GR_FAST` の有無と値は関数内 `static` に保存され、sm_70 判定の `cur_dev_volta()` はデバイスごとにキャッシュされます（`engine/src/kernels/cuda/fused_gr.cu:1404-1419,4073-4084`）。

## ログと測定値

対象変数をカーネルが有効化・無効化したことだけを示す専用ログや、値の不正を理由とする終了経路はありません。起動時に Volta の既定スイッチを1つ以上追加した場合は、`strata: sm_70 (Volta): %zu exact speed switches on by default (STRATA_SM70_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ` に設定したスイッチ名の一覧を続けて stderr に出します。明示値だけで使う場合や既定スイッチを追加しない場合、この行は出ません（`engine/src/core/nv_defaults.cpp:240-255`）。

ソースコメントは V100-SXM2 の hyper-connection read を T=1 で `50.9 -> 46.7 us`、bitwise と記録していますが、同コメントには測定回数や他の測定条件がありません。再現可能な一般性能値としては扱えません（`engine/src/kernels/cuda/fused_gr.cu:4082`）。`docs/DETAILS.md` の sm_70 行はこの変数を含む21個の既定スイッチ群と `STRATA_SM70_PERF=0` / `STRATA_DEFAULTS=026` の解除条件を記載しており、起動時の既定注入コードと整合します（`docs/DETAILS.md:1487`）。一方、`docs/SETTINGS.md` は対応 backend を「NVIDIA and AMD」としていますが、実装箇所は CUDA 側で、HIP 側の interleaved MMVQ は `false` を返し、Volta 判定も `false` です。コード上、AMD/HIP でこの変数が有効になる経路は確認できません（`docs/SETTINGS.md:314`、`engine/src/kernels/cuda/native_mmvq.cu:4255-4265`、`engine/src/kernels/cuda/fused_gr.cu:1404-1419`）。

## 根拠

- 既定値・抑止・起動時適用・ログ: `engine/src/core/nv_defaults.cpp:15-18,136-163,222-257`、`engine/src/program/generate.cpp:4421-4449`、`engine/include/strata/core/defaults_026.hpp:21-29`
- mode 8 の判定・キャッシュ・呼び出し条件: `engine/src/kernels/cuda/iq_kernels.cu:6763-6802,7196-7215`
- interleaved MMVQ の判定・キャッシュ・fallback: `engine/src/kernels/cuda/native_mmvq.cu:4193-4228,4230-4252`、`engine/src/kernels/cuda/shared_expert.cu:229-257`
- hyper-connection の判定・キャッシュ・dispatch: `engine/src/kernels/cuda/fused_gr.cu:48-53,1404-1419,1782-1795,4073-4084,4286-4320`
- 設定一覧との照合: `docs/DETAILS.md:1487`
