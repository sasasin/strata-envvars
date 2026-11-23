# `STRATA_PF_TQ_G11`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の fused prompt expert kernel が、Gyro の trellis 形式を RDNA3 世代のデバイスで扱うかを選ぶ内部スイッチ。`engine/src/prefill/moe_fused_iq.cu` の `tq_g11_switch()` が値を読み、`tq_g11()` と `tq_hip_pair()` を通じて `native_supported()` の layer-format 判定に使う。対象 GPU では有効になると、対応する Gyro expert の prompt 計算が fused trellis kernel の対象になる。生成 token の挙動を変える目的の CLI オプションではない。`terminal/data/settings-register.json:31176-31204` でも backend は `hip`、用途は診断・A/B 用の内部スイッチとして登録されている。

この名前だけでは機能は有効にならない。HIP 側の `STRATA_PF_FUSED_TQ` も有効である必要があり、これは通常の MMQ ありビルドでは既定で未設定、MMQ なしビルドでは起動前に未設定の場合だけ `"1"` に設定される。`STRATA_PF_TQ_G11` 自体はその起動時既定値リストに含まれない（`engine/src/prefill/moe_fused_iq.cu:3151-3179`、`engine/include/strata/prefill/own_only_switches.hpp:18-25`、`engine/src/prefill/prefill.cpp:223-256`）。

## 値と判定

`parse_switch()` は `getenv()` の結果を文字列として受け取り、未設定または空文字列なら `-1`、先頭文字が `'1'` なら `1`、それ以外なら `0` を返す。整数変換や文字列全体の比較は行わない。したがって空白除去、大文字小文字変換、数値妥当性検証はなく、`1anything` も `1` と同じ判定になる（`engine/include/strata/prefill/fused_tq_hip.hpp:21-22`、読み取り箇所 `engine/src/prefill/moe_fused_iq.cu:3173-3175`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| gfx1100 / gfx1101 / gfx1102、かつ `STRATA_PF_FUSED_TQ` が有効 | `kG11DefaultOn == true` により有効 | `1`, `1anything` | `0`, `0anything`, `true`, ` 1`, 空文字列 |
| gfx1103（Radeon 780M）、かつ `STRATA_PF_FUSED_TQ` が有効 | 無効（明示 opt-in が必要） | `1`, `1anything` | 未設定、空文字列、`0`, `true`, ` 1` |
| その他の HIP GPU、または `STRATA_PF_FUSED_TQ` が無効 | 無効 | なし | すべて |

RDNA3 の discrete GPU 判定は gfx1100/1101/1102 に限られ、gfx1103 は別の `g1103_on()` 分岐で、`sw == 1` のときだけ対象になる。gfx1151 と gfx12 は別ルールを使う（`engine/include/strata/prefill/fused_tq_hip.hpp:24-31, 46-55`、`engine/src/prefill/moe_fused_iq.cu:3177-3187`）。

## 有効になる条件

- HIP backend のビルドであること。変数の読み取りは `#if defined(__HIPCC__)` 節内にあるため CUDA / CPU / SYCL 経路では読み取られない（`engine/src/prefill/moe_fused_iq.cu:3139-3140, 3171-3188`）。
- デバイスが gfx1100、gfx1101、gfx1102 のいずれかであること。これらでは未設定でも `kG11DefaultOn` が true だが、`STRATA_PF_FUSED_TQ` が有効でなければ trellis 経路は無効。MMQ なしビルドは `STRATA_PF_FUSED_TQ` を未設定時に `"1"` にする。gfx1103 は `STRATA_PF_TQ_G11` が先頭 `'1'` の場合だけ opt-in となる（`engine/src/prefill/moe_fused_iq.cu:3171-3187`、`engine/include/strata/prefill/own_only_switches.hpp:18-25`）。
- Strata が HIP fused native kernel を利用できること。デバイス情報の確認に成功し、gfx11 WMMA または gfx12 の対象アーキテクチャで、必要 kernel の属性・共有メモリ・occupancy の確認が通る必要がある。失敗時は `dev_info().ok` が false のままで trellis pair 判定も false になる（`engine/src/prefill/moe_fused_iq.cu:2847-2885`）。
- layer の gate/up と down が対応する trellis ペアであること。Gyro-S は `TQK6` / `TQK7`、Gyro-M は `TQ2_T` / `TQ2_T`。trellis 形式が他形式と混在するペアは選ばれず、さらに `D_ROWS_K <= D_ROWS_N` と両 K 次元の 128 要素境界条件を満たす必要がある（`engine/src/prefill/moe_fused_iq.cu:3535-3543`）。
- `STRATA_PF_FUSED=0`（先頭文字が `0`）または `STRATA_PF_FUSED_NATIVE=0` で fused native 経路が抑止されていないこと。`native_supported()` はこの判定と prompt 側 override を先に確認してから HIP の trellis ペア規則へ進む（`engine/src/prefill/moe_fused_iq.cu:3415-3432`）。

## 実行時の詳細

`tq_g11_switch()` 内の function-local `static const int` が、このプロセスで初めて呼ばれたときに `getenv("STRATA_PF_TQ_G11")` の結果を parse して保持する。その後の判定は cache 値を使うため、実行中に環境を書き換えてもこの変数の判定は更新されない。`tq_g11()` は `STRATA_PF_FUSED_TQ` の読み取り結果と GPU の `DevInfo` を合わせ、RDNA3 discrete GPU または gfx1103 に対象を限定する。これを `tq_hip_pair()` が `native_supported()` の trellis gate/up-down ペア判定へ反映する（`engine/src/prefill/moe_fused_iq.cu:3151-3187, 3535-3543`）。

対応ペアと条件が揃わない場合、`native_supported()` は false を返し、prompt planner は layer を fused native として印付けしない。MMQ tile が使える場合は通常の MMQ 経路に残り、MMQ がないビルドでは利用可能な Strata 側 fallback 経路に残る（`engine/src/prefill/prefill.cpp:2048-2074`）。この環境変数専用の警告、エラー、終了処理は実装されていない。kernel 利用不可時も、この変数自体を理由にプロセスを終了する処理は見つからなかった。

## ログと測定値

この変数の有効・無効や parse 結果を出すログはない。`fused_tq_hip.hpp` のコメントは gfx1100 クラスでの測定を記述している一方、「gfx1100 での測定ではない」と明記しており、コードの根拠だけで性能値や品質への影響を一般化できない。`docs/DETAILS.md` にこのスイッチ固有の説明・測定は見つからなかった。

## 根拠

- 値 parse と device / pair rule: `engine/include/strata/prefill/fused_tq_hip.hpp:21-22, 46-55`
- 環境読み取り、static cache、HIP の device 判定: `engine/src/prefill/moe_fused_iq.cu:3151-3188`
- HIP デバイス属性・kernel 可用性: `engine/src/prefill/moe_fused_iq.cu:2847-2885`
- 共通 fused native 抑止と trellis format / geometry 判定: `engine/src/prefill/moe_fused_iq.cu:3415-3432, 3535-3543`
- MMQ なしビルドの起動時既定値: `engine/include/strata/prefill/own_only_switches.hpp:18-25`、適用箇所 `engine/src/prefill/prefill.cpp:223-256`
- layer planner の fallback: `engine/src/prefill/prefill.cpp:2048-2074`
- 内部・HIP 用スイッチとしての登録情報: `terminal/data/settings-register.json:31176-31204`

