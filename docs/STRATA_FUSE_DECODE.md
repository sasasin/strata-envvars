# `STRATA_FUSE_DECODE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA の実験ビルドで、decode 中の複数の処理をまとめたカーネルへ切り替えます。該当するのは activation の複数形式への変換、BF16 projection の組、MoE の gate/up・SwiGLU・中間量子化などです。呼び出し箇所は `STRATA_EXPERIMENTAL_SM60` のコンパイル条件内にあり、通常の CUDA リリースビルドや HIP ビルドではこの変数を設定してもこれらの分岐は入りません。

## 値と判定

`include/strata/kernels/fuse_decode.hpp` は `getenv()` の戻り値が存在し、先頭文字が `'1'` なら有効とします。文字列全体の parse はしません。

| `STRATA_FUSE_DECODE` | 判定（直接読み取り時） |
|---|---|
| 未設定 | 無効。ただし後述の sm_60 既定値が起動時に設定する場合がある |
| 空文字 | 無効（設定済みだが先頭文字は `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `01`, `true`, `2`, ` 1` | 無効 |

大文字小文字・後続文字・数値としての妥当性は判定しません。読み取り結果は関数内の `static const bool` に初回呼び出し時に保存され、その後の環境変更は反映されません。

## 有効になる条件

機能の呼び出し箇所は `STRATA_EXPERIMENTAL_SM60` 定義時にだけコンパイルされます。CMake では `STRATA_EXPERIMENTAL_SM60=ON` は CUDA の Pascal sm_60 / Volta sm_70 向け実験ビルドを選びます。したがって環境変数が `1` であっても、通常の既成エンジンでは効果がありません。

sm_60 では起動時の `apply_nv_defaults()` が条件を満たすと未設定変数へ `1` を設定します。条件は、CUDA デバイスが少なくとも1台あり、可視デバイスすべてが同じ compute capability 6.0 であること、かつ `STRATA_SM60_PERF` の先頭文字が `0` でないことです。`STRATA_SM60_PERF` が `0` で始まると既定値群は作られません。ユーザーが `STRATA_FUSE_DECODE` に空文字を含む何らかの値を明示している場合、既定値設定処理は上書きしません。その値が `1` で始まらなければ機能は無効のままです。明示した `STRATA_FUSE_DECODE=1` は、`STRATA_SM60_PERF=0` でも直接判定では有効です。

sm_70（V100 など）にはこの自動設定はありません。実験ビルドで `STRATA_FUSE_DECODE=1` を設定した場合に有効になります。複数 GPU の compute capability が混在する場合も `apply_nv_defaults()` は呼ばれず、自動設定されません。

## 実行時の詳細

有効時は、該当経路で次の処理を置き換えます。

- GDN、shared expert、QSA layer では、必要な activation 形式を別々の量子化・変換カーネルで作る代わりに `quantize_act_images()` でまとめて生成します。対象 weight が native data を持つ場合など、もともと変換が不要な経路では呼び出されません。
- GDN の alpha/beta BF16 projection と QSA indexer の key/query projection は、それぞれ対の projection カーネルへ切り替わります。
- shared expert と grouped S2 MoE の複数経路では、SwiGLU と中間値の Q8_0 量子化を一つのカーネルで行います。grouped S2 の fast 経路で `swiglu_q8` が有効な場合は別の fused カーネル経路が先に選ばれ、この変数の分岐には入りません。

sm_60 の既定値が新たに環境へ設定された場合、stderr に `strata: sm_60 (Pascal): ... exact speed switches on by default (STRATA_SM60_PERF=0 turns them off; a switch you set is kept): ...` の形式で設定したスイッチ一覧を出します。変数を直接読む `fuse_decode()` 自体に有効化ログはありません。

## 文書・測定値との照合

`docs/DETAILS.md` は sm_60（Tesla P100）の既定スイッチ群に本変数を含め、`STRATA_SM60_PERF=0` で群を止められると記載しています。ソースの sm_60 既定表および適用条件と一致します。P100 の +14.2% はスイッチ群全体の測定であり、本変数単独の効果としては扱えません。`docs/NVIDIA_V100.md` は CUDA 12 実験ビルドの V100 向け opt-in として本変数を記載し、寄稿者測定の「token あたり 4–16 us saved」を載せていますが、表に測定条件の詳細がないため一般的な性能値とは判断できません。

## 根拠

- 値判定と static cache: `include/strata/kernels/fuse_decode.hpp:8-15`
- CUDA 実験ビルドの定義と Pascal / Volta の条件: `CMakeLists.txt:181-219`
- sm_60 の既定値、`STRATA_SM60_PERF` 判定、ユーザー値の保持、stderr 出力: `src/core/nv_defaults.cpp:11-15,18-49,52-69`
- 同一 compute capability の可視 CUDA デバイスだけで既定値を適用: `src/program/generate.cpp:2800-2817`
- GDN/shared expert/QSA layer の activation と projection: `src/core/layer.cpp:263-272,325-335,482-492,1150-1164,1181-1190`
- shared expert および grouped S2 SwiGLU + quantization: `src/kernels/cuda/shared_expert.cu:334-415`, `src/kernels/cuda/s2_expert_grouped.cu:644-658,751-764,798-811,1204-1219`
- 文書記載: `docs/DETAILS.md:2425-2453`, `docs/NVIDIA_V100.md:93-100`
