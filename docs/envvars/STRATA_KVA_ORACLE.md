# `STRATA_KVA_ORACLE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

非空のディレクトリパスを指定すると、KVA の Oracle モードで、そのディレクトリにある層ごとの capture ファイルから late-layer の入力 residual を読み、通常の層入力に差し替えます。これは KVA の近似経路に使う入力を capture の値で再生するためのものです。変数だけでは KVA を有効にしません。また、環境変数の受け取り自体は CUDA/HIP 向け KVA 実装にありますが、Metal build では KVA backend が無効です（`include/strata/prefill/kva.hpp:43-49,168-171`）。

## 値と判定

| 値 | Strata の処理 |
|---|---|
| 未設定または空文字 | `oracle_dir` を設定せず、この変数からは Oracle mode にしません。 |
| 非空文字列 | 文字列全体を directory path として `oracle_dir` に保存し、初期 mode を Oracle にします。数値変換やパス検証、正規化はこの設定箇所では行いません。 |

実際に Oracle 再生する mode は、後続設定で上書きされます。非空の `STRATA_KVA_PROJECTOR` は mode を Linear に変更し、その後の非空 `STRATA_KVA_MODE` は最後に評価されます。`STRATA_KVA_MODE=oracle` は Oracle、`linear` は Linear、それ以外の文字列（`identity` を含む）は Identity にします。比較は大文字小文字を区別する完全一致です。従って、`STRATA_KVA_ORACLE` が非空でも projector や mode の値によって Oracle 読み込みに使われない場合があります。逆に `STRATA_KVA_MODE=oracle` だけでも mode は Oracle になりますが、この変数由来の directory は空のままで、読み込み時の path は `/L<layer>.bin` になります（`include/strata/prefill/kva.hpp:168-180`; `src/prefill/prefill.cpp:2850,2893-2895`）。

## 有効になる条件

- KVA 自体を `STRATA_KVA` で有効にする必要があります。未設定・空文字は off、非空値の先頭文字が `0` なら off、それ以外は on です。ただし Metal build では backend guard により off になります（`include/strata/prefill/kva.hpp:152-156`）。
- CLI の `--batch`, `--peer-device`、または複数 GPU への layer split がある場合、engine は KVA をブロックします。KVA が明示的に on なら `strata generate: KVA ... is off here: ...` を stderr に出します（`src/program/generate.cpp:6263-6278`）。
- 1 回の cold prompt read（`pos0 == 0`）、全 layer stage、画像なし、DFlash2 taps なしで、prompt 長が `STRATA_KVA_MIN_PROMPT` 以上かつ suffix より十分長く、モデル形状が測定対象（48 layers / 512 experts）である必要があります。別形状は `STRATA_KVA_ANY_MODEL` が on の場合に限り許可され、stderr に警告します（`include/strata/prefill/kva.hpp:104-133`; `src/prefill/prefill.cpp:2947-2965`）。
- 条件を満たしても、chunk の全位置が完全計算 suffix の手前にあるときだけ近似対象になり、指定 split 以降の層で Oracle 入力を再生します（`src/prefill/prefill.cpp:3115-3123,3619-3629`）。

## 実行時の詳細

設定値は `kva_config_from_env()` が環境から読み、`kva_config()` の function-local `static const` に初回評価結果を cache します。従って、プロセス内で設定が初めて評価された後に環境を書き換えても再読込されません。`STRATA_KVA_ORACLE` の非空判定後に `STRATA_KVA_ORACLE_FP32` を flag helper で評価し、未設定・空文字なら false、設定値の先頭文字が `0` 以外なら true としてファイル幅を選びます（`include/strata/prefill/kva.hpp:143-146,149-195`）。

Oracle mode で KVA 対象になると、static `KvaTap` が directory と fp32/bf16 形式を保持します。層 `l` ごとに `<dir>/L<l>.bin` を binary read-only で開き、prompt position `p0` に対応する offset から `T * D` 個の要素を読みます。既定の bf16 は fp32 residual buffer に展開し、fp32 指定では fp32 値を読みます。読み込んだデータを device residual に非同期 upload し、その層の block input として使います（`src/prefill/prefill.cpp:2889-2932,2967-2974,3689-3695`）。

ファイル open/seek/read/upload の失敗は `err` に `kva oracle: cannot read ...`, `cannot seek ...`, `short read ...`, `the upload failed` などの理由を設定し、`run_impl()` が false を返す経路になります。Oracle 専用の成功ログはありません。KVA が適用された場合は stderr に `strata prefill: KVA on: ... mode oracle` が出ます。設定が有効でも条件不成立なら、明示的に KVA を on にした場合などに `KVA configured but NOT applied: ...` が出ます（`src/prefill/prefill.cpp:2891-2929,3691-3694,5820-5856`）。

## 根拠

- `include/strata/prefill/kva.hpp:43-49,69-93,137-195` — backend 条件、設定値、flag 判定、環境変数 parse と cache。
- `src/program/generate.cpp:6257-6278` — 起動時の engine 条件、batch / peer device / 複数 GPU による無効化とログ。
- `src/prefill/prefill.cpp:2947-2974,3115-3123,3619-3629` — prompt 適用条件と Oracle tap の初期化・対象 chunk/layer 判定。
- `src/prefill/prefill.cpp:2889-2932,3689-3695,5820-5856` — per-layer file 読み込み、residual 差し替え、エラーおよび観測ログ。
