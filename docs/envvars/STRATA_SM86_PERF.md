# `STRATA_SM86_PERF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

sm_86（CUDA compute capability 8.6）の NVIDIA 既定値テーブルを無効にするスイッチです。未設定、または値の先頭文字が `0` でなければテーブルが候補になります。テーブルは主にエンジン内の別々のスイッチを環境へ既定値として追加し、各機能の分岐はそれらのスイッチを読みます。この変数自体は個々の kernel を選択せず、生成内容を直接変更しません。テーブルの値は `engine/src/core/nv_defaults.cpp:41-74`、適用は同 `:222-256`、エンジン起動時の呼び出しは `engine/src/program/generate.cpp:4421-4449` です。

現在の sm_86 テーブルは `STRATA_ADAPT_LAG=2`、`STRATA_CPU_IQ_ALL_EXACT1=1`、`STRATA_SIDE_MIXER=2`、`STRATA_ATTN_DAILY=1`、`STRATA_GR_UP75=1`、`STRATA_GU_SWIGLU=1`、`STRATA_QSA_ROWS=1`、`STRATA_B6_MMVQ_ROWS=1`、`STRATA_DEQUANT_SIDE=1`、`STRATA_LFUSE=1`、`STRATA_PLE_COMPACT=1`、`STRATA_PLE_COPY_STREAM=1`、`STRATA_PF_FUSED_KQ=1`、`STRATA_HC_UPMIX=1`、`STRATA_Q80_ROWS1=1`、`STRATA_EXP_MODE=8`、`STRATA_PREFILL_CPU_SHARE_NT=32` です。さらに主 GPU の VRAM が 13 GiB 以下なら `STRATA_ADAPT_FETCH=2`、16 GiB より大きければ `STRATA_VERIFY_DEVICE_HITS=1` が候補に加わります（`nv_defaults.cpp:43-74`）。これらの変数をユーザーが既に設定していれば、その値は空文字を含め維持されます（同 `:227-234`）。

## 値と判定

共通 helper `off(name)` は `getenv` の結果が存在し、かつ先頭文字が文字 `'0'` なら off と判定します。文字列全体の parse・数値変換・大文字小文字判定はしません（`engine/src/core/nv_defaults.cpp:14-18`）。

| 条件 | unset | 有効になる値（テーブルを止めない） | 無効になる値（テーブルを止める） |
|---|---|---|---|
| sm_86 の既定値テーブル | 既定値を適用 | 空文字、`1`、`true`、`false`、` 0` など先頭が `0` 以外の値 | `0`、`00`、`0anything`（先頭が `0` の文字列すべて） |

表の「無効」はこのテーブルだけを指します。明示した `STRATA_SM86_PERF=1` が個々の設定を有効化するわけではなく、未設定時と同じくテーブル適用を許します。`STRATA_DEFAULTS=026` は sm_86 テーブル全体を止めません。ソースではこの設定は sm_86 分岐の `STRATA_ADAPT_FETCH` 条件にだけ使われ、同値が真なら `ADAPT_FETCH=2` を追加しません（`engine/src/core/nv_defaults.cpp:41-74`）。

同じ変数は speculative-adapt の sm_86 既定値注入にも使われます。ここでも unset は許可、先頭 `0` は抑止です（`engine/src/core/nv_defaults.cpp:328-347`）。

## 有効になる条件

- この処理は `generate.cpp` の NVIDIA 経路にあり、コンパイル条件は HIP と Metal を除外しています（`engine/src/program/generate.cpp:4421-4425`）。
- CUDA デバイスが 1 台以上見つかり、全ての可視デバイスの compute capability が同じで、その capability が 8.6 のときにテーブルを適用します。異なる capability が混在する場合、この箇所は `apply_nv_defaults` と `apply_spec_adapt_default` を呼ばず、sm_86 のテーブルは追加されません（`engine/src/program/generate.cpp:4427-4450`）。
- `STRATA_SM86_PERF` が先頭 `0` ならテーブルは空になります（`engine/src/core/nv_defaults.cpp:37-43`）。個別スイッチがすでにプロセス環境に設定されている場合、テーブルが有効でもそのスイッチは上書きしません（同 `:227-234`）。
- `STRATA_SPEC_ADAPT_SM86` が先頭 `1` の場合に限り、`STRATA_SM86_PERF` が off でなければ、未設定の `STRATA_SPEC_ADAPT_EVERY=2` と `STRATA_SPEC_ADAPT_WARM=200` を追加します。両変数が既に設定済みなら値を保ちます（`engine/src/core/nv_defaults.cpp:335-347`）。これらの値が生成時に使われるには、`--spec >= 2`、`--adapt-every` の明示指定なし、かつ `STRATA_SPEC_ADAPT_EVERY` の `atoi` 結果が正で通常の `adapt_every` より小さく、`STRATA_SPEC_ADAPT_WARM` の `atoll` 結果が正である必要があります（`engine/src/program/generate.cpp:5100-5109`）。`STRATA_SM86_PERF=0` は既定値注入を止めますが、ユーザーがこれら二つを直接設定した場合の生成側判定を無効化するコードではありません。

## 実行時の詳細

`generate` の起動処理で GPU 数・各 GPU の capability を照会し、全 GPU が同一 capability の場合に、個々の engine switch が読む前に `apply_nv_defaults` を呼びます（`engine/src/program/generate.cpp:4427-4449`）。`off()` は static cache を使わず、その呼び出しごとに環境を読みます。テーブル適用と speculative-adapt 既定値の判定はいずれもこの起動経路で行われます。テーブル適用は `setenv(..., 0)` または Windows の `_putenv_s` で、未設定の個別変数だけをプロセス環境へ追加します（`engine/src/core/nv_defaults.cpp:222-234`）。

既定値の追加は CLI 引数でなく環境変数を通じて行われます。この箇所に `STRATA_SM86_PERF` を変更する CLI 引数はありません。後続の各機能がモデル状態や各スイッチに応じて実際の処理を選ぶため、この変数だけから全モデル・全要求で同一の kernel 経路になるとは言えません。

## ログと測定値

テーブルで一つ以上の個別値を追加した場合、stderr に `strata: sm_86 (Ampere): N [exact ]speed switches on by default (STRATA_SM86_PERF=0 turns them off; a switch you set is kept): ...` の形式で、追加された名前を出力します（`engine/src/core/nv_defaults.cpp:240-255`）。通常は `exact speed switches` と表示されますが、VRAM 条件で `STRATA_ADAPT_FETCH` も追加された場合は `speed switches` となります（同 `:248-253`）。スイッチが off でテーブルが空の場合、またはテーブル候補の個別変数が全て既に設定済みの場合、このログは出ません。sm_86 で `STRATA_SPEC_ADAPT_SM86=1` による既定値だけを追加し、テーブル追加がなかったケースも、このログの対象外です（同 `:240-255,328-347`）。この変数自体による警告、終了、失敗経路はありません。

`docs/DETAILS.md:1478-1488` は sm_86 の既定値を9個として列挙し、`STRATA_ADAPT_NOWAIT` も含めています。一方、調査対象 HEAD の実装には `STRATA_ADAPT_NOWAIT` はなく、sm_86 の固定テーブルに17個、VRAM 条件付き候補が最大1個あります（`engine/src/core/nv_defaults.cpp:43-74`）。資料にある性能値はソース実装から確認した測定ではないため、ここでは現行性能の主張として扱いません。

## 根拠

- `engine/src/core/nv_defaults.cpp:14-18` — `off()` の設定有無・先頭文字判定。
- `engine/src/core/nv_defaults.cpp:37-74` — compute capability 8.6 のテーブルと VRAM 条件。
- `engine/src/core/nv_defaults.cpp:222-256` — 個別環境変数の優先順位と stderr 出力。
- `engine/src/core/nv_defaults.cpp:328-347` — speculative-adapt 用の追加判定と値。
- `engine/src/program/generate.cpp:4421-4450` — ビルド条件、可視 GPU の同一 capability 判定、起動時適用。
- `engine/src/program/generate.cpp:5100-5109` — speculative-adapt 既定値を使う CLI・値条件。
- `engine/include/strata/core/nv_defaults.hpp:9-17,109-113` — スイッチの説明と適用タイミングに関する実装コメント。
- `docs/DETAILS.md:1478-1488` — 現行ソースとの差がある既存資料。
