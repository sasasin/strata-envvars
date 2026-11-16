# `STRATA_PF_TQ_G1151`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP の fused prompt expert kernels が AMD gfx1151（Strix Halo）で trellis 形式の expert pair を実行するかを選ぶ内部 switch です。主な対象は Gyro-S の TQK6 gate/up + TQK7 down で、この switch が on なら対応する native fused kernels を選べます。Gyro-M の TQ2_T pair は gfx1151 ではこの変数を明示的に `1` にした場合だけ対象です。値が有効でも、`STRATA_PF_FUSED_TQ`、デバイス、形式の組み合わせ、kernel 対応条件を満たさなければ切り替わりません（`src/prefill/moe_fused_iq.cu:2643-2672,2689-2695,2994-3003`）。

## 値と判定

`parse_switch` は未設定 (`nullptr`) または空文字列を `-1` とし、それ以外は先頭 1 文字だけを見ます。先頭が `'1'` なら `1`、それ以外は `0` です。したがって数値全体の parse、空白除去、大文字小文字変換はありません。例えば `1`、`10`、`1anything` は on、`0`、`0anything`、`01`、`true`、` 1`、`-1` は明示 off と判定されます。空文字は明示 off ではなく unset と同じ扱いです（`include/strata/prefill/fused_tq_hip.hpp:20-21`）。

| 条件 | unset または空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP gfx1151、`STRATA_PF_FUSED_TQ` が on | Windows では既定 on。ただし `STRATA_GFX1151_DEFAULTS` の先頭が `0` なら off。Windows 以外は off | 先頭文字が `1`。Gyro-S と Gyro-M の対応 pair が対象 | 空文字以外で先頭文字が `1` 以外。 |
| HIP gfx12、`STRATA_PF_FUSED_TQ` が on | この変数を使わず on | この変数を使わず on | この変数を使わず on |
| その他の HIP デバイス、または `STRATA_PF_FUSED_TQ` が off | off | この変数だけでは on にならない | off |

この表の gfx12 では `device_on` が gfx12 判定をこの switch より先に返し、その他の HIP デバイスは gfx1151 判定を通らず off になります。`STRATA_PF_FUSED_TQ` は先頭文字が `1` の場合に on です。MMQ を含まない fused-prefill build は、起動前の初期化で同変数が未設定の場合に限り `1` を環境へ設定します。既に空文字を含む値があれば保持するため、空文字はこの build でも on になりません（`include/strata/prefill/fused_tq_hip.hpp:24-30`; `src/prefill/moe_fused_iq.cu:2646-2668`; `src/prefill/prefill.cpp:204-235`; `include/strata/prefill/own_only_switches.hpp:18-24,48-56`）。

## 有効になる条件

- HIP backend であること。この読み取りと判定は `__HIPCC__` のコードにあります。CUDA、SYCL、Metal の経路をこの変数が制御するコードはありません（`src/prefill/moe_fused_iq.cu:2634,2689-2704,2994-3003`）。
- 対象 device が gfx1151 で、`STRATA_PF_FUSED_TQ` が先頭文字 `1` であること。MMQ なし build ではこの別変数が未設定時に build 初期化で `1` にされます。ユーザーが既に設定した値は維持されます（`src/prefill/moe_fused_iq.cu:2643-2668`; `src/prefill/prefill.cpp:204-235`）。
- Gyro-S は TQK6 gate/up と TQK7 down の pair が対象です。Gyro-M の TQ2_T / TQ2_T は、この変数の判定値が厳密に `1` のときだけ対象です。gfx1151 の unset 既定 on は Gyro-M を有効にしません（`include/strata/prefill/fused_tq_hip.hpp:32-36`; `src/prefill/moe_fused_iq.cu:2994-3003`）。
- 対象型の kernel が要求する形状条件 `D_ROWS_K <= D_ROWS_N`、`D_ROWS_K % 128 == 0`、`GU_ROWS_K % 128 == 0` と、デバイス判定 `d.ok` も必要です。別の trellis 型の組み合わせはこの分岐で選ばれません（`src/prefill/moe_fused_iq.cu:2994-3003`）。
- `STRATA_PF_FUSED=0`、`STRATA_PF_FUSED_NATIVE=0`、または小カード prompt path による fused override が fused native 経路を止める場合、この変数が on でも実行されません（`src/prefill/moe_fused_iq.cu:2891-2908`）。
- unset の既定 on は Windows gfx1151 だけです。`STRATA_GFX1151_DEFAULTS` の先頭文字が `0` ならこの既定を無効にします。`STRATA_PF_TQ_G1151=1` を明示した場合は switch 判定が先に確定するため、この既定値用設定は判定を変えません（`src/prefill/moe_fused_iq.cu:2653-2668`; `include/strata/prefill/fused_tq_hip.hpp:24-30`）。

## 実行時の詳細

値は `tq_g1151_switch()` の関数内 `static` で初回呼び出し時に一度読み取られ、その後の呼び出しでは同じ値を使います。`STRATA_PF_FUSED_TQ` と `STRATA_GFX1151_DEFAULTS` もそれぞれ関数内 `static` で初回読み取り結果を保持します。そのため、これらの値をプロセス起動後に変更しても、最初の評価後には反映されません。CLI 引数によるこの変数の上書きは確認できません（`src/prefill/moe_fused_iq.cu:2646-2668`）。

fused native pair の可否は `native_supported()` から device/format 判定へ流れます。条件を満たさない pair は fused trellis kernel を選びません。MMQ がある build では該当 pair のコメント上の代替は MMQ です。MMQ を含まない own-only build では fused kernel が対応しない layer は FP16 path になります（`src/prefill/moe_fused_iq.cu:2690-2704,2891-2908,2994-3003`; `src/prefill/prefill.cpp:204-210,373-385`）。

## ログと測定値

この変数の読み取り・有効化・無効化を示す専用ログ、警告、終了経路は確認できません。値が無効または条件不足でも、この switch 判定自体は false を返し、対象 pair の fused kernel 選択を止めます（`src/prefill/moe_fused_iq.cu:2653-2672,2994-3003`）。ソースコメントには Windows gfx1151 の Gyro-S 等に関する測定記述がありますが、この文書では再現条件一式を確認できないため性能値として採用していません（`include/strata/prefill/fused_tq_hip.hpp:15-17`）。

## 根拠

- 候補名の全参照確認: `include/strata/prefill/fused_tq_hip.hpp:6-7,15-21,32-36`; `src/prefill/moe_fused_iq.cu:2650-2655,3001-3003`。他の出現は設計コメント、テスト、ビルド用登録情報でした。実環境から値を取得する箇所は `src/prefill/moe_fused_iq.cu:2653-2655` です。
- build 初期化と別 switch の相互作用: `include/strata/prefill/own_only_switches.hpp:18-24,48-56`; `src/prefill/prefill.cpp:204-235`; `src/prefill/moe_fused_iq.cu:2646-2668`。
- pair の選択条件: `include/strata/prefill/fused_tq_hip.hpp:20-36`; `src/prefill/moe_fused_iq.cu:2689-2704,2891-2908,2994-3003`。
- Gyro の型の説明との照合: `docs/GYRO.md:31-37`。
