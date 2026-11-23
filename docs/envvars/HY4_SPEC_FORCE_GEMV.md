# `HY4_SPEC_FORCE_GEMV`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の HY4 speculative decode で、gfx12 の `HY4_MMA` ビルドに限り、M（処理行数）5〜8 の verify を GEMV 系へ戻せるようにする環境変数です。`Spec` の `cfg.exact` が有効な場合、値が非ゼロなら gfx12 でも `moe_dec_max_m` と `lin_gemv_max_m` を 16 に設定します。これらの上限以下で MoE decode は GEMV-style kernel、linear は帯域型 GEMV を選びます。上限 4 のままだと M=5〜8 は GEMV 上限を超え、gfx12 の WMMA 側の経路になります（`engine/src/hy4flash/run/hy4_spec.hip.h:74-89`、`engine/src/hy4flash/run/skmoe.hip.h:1470-1480,1508-1527`、`engine/src/hy4flash/run/skhy4.hip.h:28-31,47-60`）。

この変数はデコード方式を単独で切り替える指定ではなく、`Spec` 初期化時に共有の M 上限を 16 にする条件の一部です。gfx12 以外、または `HY4_MMA` なしでは別の分岐が上限を設定するため、この変数による追加の切り替えはありません（`engine/src/hy4flash/run/hy4_spec.hip.h:77-89`）。

## 値と判定

`getenv` で設定有無を確認し、設定されていれば `atoi` の結果が 0 以外かを判定します。文字列全体の検証はありません。先頭の空白と符号付き十進数字を `atoi` が変換し、数字以降の文字は判定に使われません。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `cfg.exact` が有効で `cfg.check` は無効、`HY4_CUDA=0` かつ `HY4_MMA=1`、gfx12 デバイス | `force_gemv=false` | `1`, `-1`, `2`, `1abc`, ` 1`（`atoi` が非ゼロ） | 空文字、`0`, `0anything`, `true`, `false`, 数字で始まらない文字列 |
| `cfg.exact` が有効、同じ HIP + MMA build、gfx12 以外 | 判定値にかかわらず上限 16 を設定 | 同左 | 同左 |
| 上記以外の build、または `cfg.exact` が無効 | この環境変数を読まない | 該当なし | 該当なし |

数値として厳密に妥当か、大文字小文字、末尾文字は検査しません。`atoi` の変換結果が非ゼロかだけが条件です。範囲外の整数文字列に対する `atoi` の結果は C/C++ の仕様上保証されないため、使用可能な境界値として扱えません。読み取り式は `cfg.check || (...)` なので `cfg.check` が true なら短絡評価され、環境変数は読まれません（`engine/src/hy4flash/run/hy4_spec.hip.h:80-82`）。

## 有効になる条件

- `Spec` を作成するコード経路に入る必要があります。HY4 CLI は `--spec-check` で `cfg.check` を有効化でき、`--spec-exact` の既定値は true、`--spec-exact 0` なら `cfg.exact` が false になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:364,427,442,992-1000`）。
- 通常の CLI では `--draft` の既定値が `auto` で、生成時の speculative 経路は `--draft dfly2` かつ `gen > 0`、`alloc_only` ではない場合です。drafter 初期化に失敗すると CLI は `dfly2: ...` を stderr に出して終了し、`Spec` は作られません（`engine/src/hy4flash/run/hy4_main.hip.cpp:363-365,701-716`）。
- serve では draft が `off` 以外で、Runner の chunk が 8 以上、drafter 初期化が成功した場合に `Spec` を作ります。chunk が 8 未満なら `--draft dfly2` 指定時に `[dfly2] chunk %d < 8; starting without drafter` を stderr に出します。初期化失敗時は `[dfly2] drafter unavailable (%s); continuing without drafter` を出して続行し、`Spec` は作りません（`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`）。
- `cfg.exact` が false ならコンストラクター内の環境変数判定を含む上限設定ブロック全体が実行されません（`engine/src/hy4flash/run/hy4_spec.hip.h:77-90`）。
- gfx12 の対象分岐は `!HY4_CUDA && HY4_MMA` のコンパイル条件と、`skd::is_gfx12_device()` の実行時判定の両方に依存します。gfx12 判定は現在のデバイス情報の `gcnArchName` が `gfx12` で始まるかを見ます（`engine/src/hy4flash/run/hy4_spec.hip.h:78-84`、`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-52`）。
- `--spec-check` は `cfg.check` を true にし、環境変数の読み取りを短絡させたうえで gfx12 の上限 16 を許可します（`engine/src/hy4flash/run/hy4_main.hip.cpp:427`、`engine/src/hy4flash/run/hy4_spec.hip.h:80-84`）。
- このコードは上限を 16 に設定するだけで、gfx12 で条件が false の場合に既存値を 4 へ戻しません。たとえば CLI の `--knobs16` は `Spec` 作成より前に両上限を 16 にし（`engine/src/hy4flash/run/hy4_main.hip.cpp:792`）、A/B 経路も `cfg.exact` が true なら同様に設定します（同 `:923-925`）。その状態では `HY4_SPEC_FORCE_GEMV` が未設定または 0 でも、上限 16 が維持されます。通常の初期値は `HY4_MMA` 有効かつ RDNA2 以外で 4 です（`engine/src/hy4flash/run/skmoe.hip.h:1478-1480`、`engine/src/hy4flash/run/skhy4.hip.h:28-31`）。

## 実行時の詳細

値は `Spec` コンストラクター内で評価されます。`cfg.exact` が true で、`cfg.check` が false、かつ `!HY4_CUDA && HY4_MMA` の build では、gfx12 以外でも式の左項を計算するため環境変数を参照しますが、その環境値にかかわらず上限 16 を設定します。gfx12 では非ゼロの場合に限って設定します。`cfg.check` が true の場合は `||` の短絡評価により `getenv` / `atoi` は呼ばれません（`engine/src/hy4flash/run/hy4_spec.hip.h:77-89`）。

環境値を保存する static cache はありません。コンストラクターのたびに判定し、その結果を `skd::moe_dec_max_m()` と `skd::lin_gemv_max_m()` のプロセス内 static な可変上限へ反映します。`Spec` 作成後に環境を書き換えてもそのインスタンスの判定は変わらず、後続のインスタンスを作る場合にだけ再読されます（`engine/src/hy4flash/run/hy4_spec.hip.h:74-89`、`engine/src/hy4flash/run/skmoe.hip.h:1478-1480`、`engine/src/hy4flash/run/skhy4.hip.h:28-31`）。

上限は forward 処理の分岐に使われ、MoE は `M <= moe_dec_max_m()` かつ build 上限内なら decode 用 GEMV-style kernel を起動し、linear は `M <= lin_gemv_max_m()` かつ 16 以下なら `linear_h_gemv` を呼びます。したがって、gfx12 の通常の初期値 4 に対するこの変数の主な差は M=5〜8 の verify kernel 選択です（`engine/src/hy4flash/run/skmoe.hip.h:1508-1527`、`engine/src/hy4flash/run/skhy4.hip.h:47-60`）。

この環境変数に固有のログや警告、失敗・終了経路はありません。値の parse に失敗しても `atoi` が 0 を返すだけで、gfx12 の上限設定条件が成立しない場合も既存値を維持して続行します（`engine/src/hy4flash/run/hy4_spec.hip.h:80-89`）。

## 根拠

- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30,74-97` — `SpecCfg` の既定値とコンストラクターの条件、環境値の読み取り、上限設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:360-365,408-428,442,792,923-925,992-1000` — CLI の設定と、コンストラクターより前に共有上限を変更する経路。
- `engine/src/hy4flash/run/skmoe.hip.h:1470-1480,1508-1527` — MoE の上限と GEMV-style / 他カーネルの分岐。
- `engine/src/hy4flash/run/skhy4.hip.h:28-31,47-60` — linear GEMV の上限と呼び分け。
- `engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-52` — 実行時 gfx12 判定。
- `engine/src/hy4flash/run/hy4_gpu.h:324-354` — HIP build 側の `HY4_CUDA` / `HY4_MMA` 定義。
