# `STRATA_FUSE_HITS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の verify 処理で、GPU 側の MoE hit 出力を `moe_hit_add` で parts に加える代わりに、その加算を native MoE combine カーネルにまとめるかを選びます。融合できる経路では `moe_hit_add` の個別呼び出しを省き、combine が hit 行を加えてから重み付き combine を行います。環境変数はこの選択だけを変え、後述の実行条件を満たさない場合は通常の加算経路に戻ります（`engine/src/core/verify.cpp:535-550,2827-2861,2932-2958`、`engine/include/strata/kernels/native_moe.hpp:19-25`）。

## 値と判定

HIP build では関数内 `static` の初回評価時に `std::getenv` で読み、設定されていれば `std::atoi(v) != 0` を真偽値にします。文字列全体の妥当性検査や clamp はありません。先頭の整数として `atoi` が読む値が 0 なら強制 OFF、0 以外なら強制 ON です。空白や符号を含む整数接頭辞も `atoi` の規則に従い、後続文字は判定されません。整数接頭辞がない文字列（空文字、`true`、`false`）や `0anything` は 0 となり、`1`、`-1`、`2`、`1anything` は非 0 となります。`atoi` が `int` に表せない入力の結果は、このコードでは検査・規定されていません（`engine/src/core/verify.cpp:536-540`）。

| build / 値 | 判定 |
|---|---|
| HIP、未設定 | GPU ごとに既定を判定。`gfx1200` / `gfx1201` なら ON、それ以外、device 取得失敗、または device 番号が 0–63 の範囲外なら OFF。 |
| HIP、設定値の `atoi` 結果が 0 | GPU 世代によらず OFF。空文字、`0`、`0anything`、`true` など。 |
| HIP、設定値の `atoi` 結果が非 0 | GPU 世代によらず ON。`1`、`-1`、`2`、`1anything` など。 |
| HIP 以外（CUDA を含む） | 常に OFF。この build 分岐では環境変数を読みません。 |

gfx12 判定は `strata::kernels::gfx_arch_is_gfx12` による `gfx1200` / `gfx1201` との一致です（`engine/src/core/verify.cpp:540-550`、`engine/include/strata/kernels/gfx_arch.hpp:41-42`）。

## 有効になる条件

環境変数が ON でも、hit 融合にはすべての条件が必要です（`engine/src/core/verify.cpp:2858-2861,2933-2937`）。

- HIP build であること。CUDA 等では `fuse_hits_on()` が false を返します。
- native combine が有効であること。`generate.cpp` では既定で無効で、`--native-moe-combine` が有効化し、`--native` もこの設定を有効化します（`engine/src/program/generate.cpp:783,1249,3917,5163,6118`）。この CLI 設定が OFF なら環境変数を ON にしても融合されません。
- verify の通常の partial-residency 経路であること。all-resident (`ar_on()`) 経路ではこの hit-fusion 判定に入らず、device-hits 経路では別途同じ判定をします（`engine/src/core/verify.cpp:2827-2837,2858-2861`）。
- profiling が OFF (`!prof_on_`)、remote expert optimization が未使用 (`!remote_opt_`)、shared-gate が combine 側へ移されていない (`!sg_gated_[grp]`) こと。
- `STRATA_DEC_BATCH` が有効で、group の token 数 `n` が 2 以上 8 以下であること。`STRATA_DEC_BATCH` は未設定なら ON、設定時は `atoi` が非 0 の場合だけ ON です（`engine/src/core/verify.cpp:1489`）。
- `native_moe_combine_hits_supported(...)` が真であること。実装上これは `k == 10`、shared pointer が非 null、`n_tok` が 1–8、embedding 幅が正かつ 4 の倍数、parts/shared/output の各ポインターが 16-byte aligned であることを要求します（`engine/src/kernels/cuda/native_moe.cu:187-189`）。

どれかを満たさなければ `hits_in_combine` は false になり、通常の `moe_hit_add(...)` が呼ばれます。環境変数の ON だけで CLI 設定、profile、remote-opt、窓サイズ、テンソル形状などの条件は上書きされません（`engine/src/core/verify.cpp:2858-2861,2933-2937`）。

## 実行時の詳細

`fuse_hits_on()` の環境変数判定は関数内 `static const int` に保存されるため、HIP プロセス中に環境を変更しても反映されません。未設定時の GPU 判定結果も `per_dev[64]` にデバイスごとにキャッシュします。設定ありの場合はこの GPU 判定を使わず、その値で強制 ON/OFF します。CUDA build では判定関数が即 false を返します（`engine/src/core/verify.cpp:536-550`）。

融合が成立しない場合は `moe_hit_add` を呼び、その後の combine は通常の multi combine（native が有効かつ `dec_batch && n > 1` の場合）または token ごとの `moe_combine_parts` に進みます。融合が成立した場合は `native_moe_combine_multi_hits_added(...)` を呼び、例外が出ると `err` に `verify combine: ` と例外文を付けて verify 処理を失敗させます（`engine/src/core/verify.cpp:2932-2965`）。カーネル側も k、alignment、token 数などを確認し、条件を満たさない呼び出しには `native MoE combine (hits added) requires k = 10, aligned spans, 1..8 tokens (16 in a wide build)` の `invalid_argument` を投げます（`engine/src/kernels/cuda/native_moe.cu:191-201`）。

## ログと測定値

環境変数の読み取り自体に対応するログはありません。partial-residency の host-pool 経路では `strata::dispatch::notef` が `experts layer: cpu rows via %ld (1 = fused wait+copy, 0 = wait then copy), hits in combine=%ld` を出し、続く combine で `combine layer: kind %ld (0 per-token, 1 multi, 2 multi+hits, 3 multi+hits gated)` を出します。融合成功時は値 `2`、通常の multi combine は `1` です。このコード上の `notef` 呼び出し位置は `engine/src/core/verify.cpp:2936,2944` です。性能測定値を記した該当 Strata 資料は確認できなかったため、速度・正確性の測定値は記載しません。

## 根拠

- 全参照の直接読み取りと値判定、HIP / 非 HIP 分岐: `engine/src/core/verify.cpp:535-550`。
- gfx12 の対象アーキテクチャ: `engine/include/strata/kernels/gfx_arch.hpp:41-42`。
- hit 融合の適用条件、通常経路への fallback、combine の分岐と観測ログ: `engine/src/core/verify.cpp:2827-2861,2932-2965`。
- native combine の既定値・CLI 有効化: `engine/src/program/generate.cpp:783,1249,3917,5163,6118`。
- hit-fusion kernel の追加形状・alignment 条件と失敗文言: `engine/src/kernels/cuda/native_moe.cu:187-201`。
- 索引 `docs/envvars/000_envvers.md` には候補名があります。リポジトリ内の `docs/DETAILS.md` と Markdown 資料では、この変数に関する別の挙動説明や測定値を確認できませんでした。
