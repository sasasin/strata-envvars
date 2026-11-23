# `strata-hy4 --spec-check`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--spec-check` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

DFly2 speculative decode の各検証窓について、受理された token rows を一度に処理した logits と、同じ位置を 1 token ずつ処理し直した logits が bitwise 一致するかを診断します。診断結果は `stderr` に出ます。このフラグは `SpecCfg::check` を有効にします（`engine/src/hy4flash/run/hy4_main.hip.cpp:427`、`engine/src/hy4flash/run/hy4_spec.hip.h:18-31`）。

## 使い方

```sh
# DFly2 で生成し、speculative verify と逐次 decode の logits を比較する
strata-hy4 --model model.strata --tokens prompt.ids --gen 32 --draft dfly2 --spec-check
```

通常の CLI 生成でこの診断を通すには `--draft dfly2` と正の `--gen` が必要です。`--spec-check` 単独では DFly2 は有効になりません。`draft` の初期値は `auto` ですが、ソースコメント上、これは `--serve` 時に drafter を自動選択し、通常の CLI 実行では `off` として扱う設定です（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,701`）。`--serve` では `SpecCfg` が serve options に渡され、drafter が利用可能で `--draft off` でなければ Spec が作られます（同 `:544-570`、`engine/src/hy4flash/run/hy4_serve.hip.h:319-341`）。

## 値と既定値

値を取りません。parser はこの引数を見つけると `scfg.check = true` にし、既定状態は `SpecCfg::check = false` です。数値や on/off 値を後ろに付ける構文ではなく、同じフラグを複数回指定しても同じ真偽値を設定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,427`、`engine/src/hy4flash/run/hy4_spec.hip.h:18-25`）。

このフラグ自体に追加の値検証はありません。speculative decode が起動しない実行では受理されても診断は行われません。

## 実行時の動作

通常の greedy speculative verify では、各窓の前に hybrid GPU/CPU の expert vcache を flush し、窓の計算中は cache を freeze します。verify の後、受理された経路の logits をホストへコピーし、先頭行から受理行までを 1 token ずつ再計算して、各 logits 行を `std::equal` で要素ごとに厳密比較します（`engine/src/hy4flash/run/hy4_spec.hip.h:360-365,446-470`）。そのため診断を有効にすると、検証窓ごとに追加の forward、GPU/CPU 同期、logits のホスト転送が発生します。

確率的 sampling（greedy でない設定、または penalty 使用時）は `prob_mode` になり、窓の freeze と逐次再計算の両方が `!prob_mode` 条件でスキップされます。したがって sampling 実行ではこのフラグによる bitwise 行比較は行われません（同 `:240-250,362,446`）。

`SpecCfg::exact` が有効な場合、AMD HIP MMA の gfx12 系では `check` が `force_gemv` を真にし、`moe_dec_max_m()` と `lin_gemv_max_m()` を 16 に設定します。これは通常の診断処理とは別に検証窓のカーネル選択にも作用します。他の HIP MMA デバイスでは同じ上限設定が `exact` によって行われ、CUDA/HIP MMA 以外の分岐でも `exact` が有効なら設定されます。`--spec-exact 0` で `exact` を無効にした場合、この constructor 内の設定は行われません（`engine/src/hy4flash/run/hy4_spec.hip.h:22,77-90`）。

## 適用条件と副作用

- 比較は `cfg.check && !prob_mode` の場合に限られます。speculative 検証に至らない通常 decode、`--draft off`、または正の `--gen` を指定していない offline 呼び出しには比較処理がありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:363-364,701`、`engine/src/hy4flash/run/hy4_spec.hip.h:362,446`）。
- `--serve` での Spec 有効化には、chunk が 8 以上で drafter の初期化が成功することも必要です。`--draft dfly2` でも chunk が 8 未満なら drafter なしで起動し、初期化失敗時も drafter なしで続行します（`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`）。
- 一致しない行があると詳細を `stderr` に出し、不一致数を加算します。詳細行は最初の 12 件までです。終了時の `[spec] check:` 行には再計算行数と不一致数が出ます。不一致そのものを理由に処理を失敗扱いにする分岐は確認できません（`engine/src/hy4flash/run/hy4_spec.hip.h:459-467,513-530`）。
- 比較用の再計算で `forward_chunk` が失敗すると `finish="error"` となり、offline CLI は `spec: <error>` を `stderr` に出して終了コード 1 を返します（同 `:453-470`、`engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1005`）。

## 出力とエラー

不一致の詳細は `[check] ... row differs from 1-token row ...` として `stderr` に出ます。チェック件数と不一致件数は、spec 統計の `[spec] check: <rows> window rows recomputed one token at a time, <mismatches> differ bitwise` に出ます（`engine/src/hy4flash/run/hy4_spec.hip.h:463-466,530`）。比較用 forward の失敗は offline CLI で終了コード 1 になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:1002-1005`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-364,427` — root parser の `SpecCfg` 初期化とフラグ登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701,992-1008` — offline の Spec 実行条件と失敗・統計出力。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-31,77-95` — 設定既定値と `exact` / GEMV 選択への作用。
- `engine/src/hy4flash/run/hy4_spec.hip.h:360-365,446-470,513-530` — cache freeze、greedy verify 後の再計算・比較、診断出力。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341` — serve における Spec の適用条件。
- `docs/cli/README.md:1277-1334` — `strata-hy4` の CUDA/HIP root scope と索引リンク。

調査対象 checkout の `git rev-parse HEAD` は上記 SHA、`git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。CLI help は実行せず、parser と実使用箇所をソースで確認しました。
