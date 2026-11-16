# `STRATA_PF_FUSED_TQ`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA と HIP の fused prompt-expert 経路で、Gyro の trellis 量子化層を Strata の fused kernel に載せるかを制御するスイッチです。対象は Gyro-S の TQK6 gate/up + TQK7 down と Gyro-M の TQ2_T gate/up + TQ2_T down です。条件を満たさなければこの fused pair を選ばず、既存の MMQ 経路に残します（CUDA: `src/prefill/moe_fused_iq.cu:2929-2939`、HIP: 同 `:2994-3003`）。

CUDA では未設定時にも一部の大きな sm_86 クラス GPU で Gyro-S に既定有効です。HIP では gfx12 で明示的な有効値が必要ですが、gfx1151 は別スイッチによる条件付き経路です。MMQ なしの fused 専用ビルドでは、ユーザーが値を設定していないと起動前にこの変数を `1` に設定するため、通常の未設定規則とは異なります（`src/prefill/prefill.cpp:204-237`）。

この設定は prompt の expert kernel 選択に関するもので、モデル自体や生成設定を選ぶ CLI 引数ではありません。Strata 所有ソースに CLI 引数からこの値を上書きする処理は見つかりませんでした。

## 値と判定

CUDA helper は `getenv` の結果が null または空文字なら `-1`（未設定扱い）、先頭文字が `'1'` なら `1`、それ以外は `0` にします。HIP は `getenv != nullptr && value[0] == '1'` だけを判定します。従って全体を数値 parse せず、`1anything` も有効、` 1`・`true`・`0`・`2` は無効です。大文字小文字や後続文字は判定しません（CUDA: `include/strata/prefill/fused_tq_default.hpp:23-31`、HIP: `src/prefill/moe_fused_iq.cu:2643-2649`）。

| ビルド / backend | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA、MMQ あり | `-1`。Gyro-S は sm_86 クラスかつ 80 SM 以上で既定有効、Gyro-M は無効 | 先頭文字 `1`。セットアップ可能な sm_80+ で trellis kernel を有効化 | 空文字は unset 扱い。それ以外は先頭文字が `1` でなければ無効（例: `0`, `2`, `true`, ` 1`） |
| HIP、MMQ あり | 無効 | 先頭文字 `1`。gfx12 で有効要求。gfx1151 でも必要条件 | 空文字を含め、先頭文字が `1` でなければ無効 |
| fused 専用ビルド（`STRATA_PREFILL_FUSED` 定義、`STRATA_PREFILL_MMQ` 未定義） | 起動前 initializer が変数不在時に `1` を設定。ユーザー指定値（空文字を含む）は保持 | 既定設定された `1`、またはユーザー値の先頭文字が `1` | 既に存在する空文字や `0` などは保持され、CUDA の unset 規則または HIP の無効判定になる |

CUDA の helper では空文字は未設定と同じ既定判定になる一方、専用ビルドの initializer は環境変数が存在するか（値ではなく null かどうか）で上書き可否を決めます。そのため明示的な空文字は専用ビルドでも `1` に置き換えられません（`include/strata/prefill/fused_tq_default.hpp:24-26`、`include/strata/prefill/own_only_switches.hpp:48-56`）。

## 有効になる条件

- **CUDA:** 環境判定が `1` なら sm_80+ のカードで対象 kernel 群をセットアップします。未設定または空文字なら `fused_tile::s86_class` のクラス（compute capability 8.6。ソース上は 8.0 / 8.9 も含む）かつ 80 SM 以上でセットアップします。`STRATA_PF_FUSED_SM86=0` はこのクラス判定を外します（`src/prefill/moe_fused_iq.cu:2422-2429,2495-2503`; `include/strata/prefill/fused_tq_default.hpp:4-10,26`）。
- **CUDA の global fused gate:** `STRATA_PF_FUSED=0` または `STRATA_PF_FUSED_NATIVE=0` なら trellis pair を含め fused 経路を選びません。これらの判定は `native_supported` の共通入口で行われます（`src/prefill/moe_fused_iq.cu:2891-2908`）。
- **HIP:** `1` が必要です。gfx12 では Gyro-S / Gyro-M とも対象になります。gfx1151 は `STRATA_PF_TQ_G1151` の判定も必要で、`1` なら有効、他の設定値なら無効、未設定時は Windows かつ `STRATA_GFX1151_DEFAULTS` が `0` でないとき Gyro-S を既定有効にします。gfx1151 の Gyro-M は `STRATA_PF_TQ_G1151=1` の場合だけです。その他の HIP デバイスでは有効になりません（`include/strata/prefill/fused_tq_hip.hpp:20-36`、`src/prefill/moe_fused_iq.cu:2650-2672`）。
- どちらの backend でも、実行バイナリに対象 kernel があり、デバイス情報が利用可能で、対象 kernel のセットアップがすべて成功する必要があります。CUDA は TQK6/TQ2_T gate/up と TQK7/TQ2_T down のセットアップを一括で行い、いずれかが失敗すると `d.tq` は立ちません（`src/prefill/moe_fused_iq.cu:2385-2415,2495-2503`）。
- レイヤーの gate/up と down が Gyro-S の TQK6/TQK7 または Gyro-M の TQ2_T/TQ2_T の組であり、コンパイル時形状が 128 値境界などの geometry 条件を満たす必要があります。別形式との混在や不適合形状は fused trellis 経路に入りません（CUDA: `src/prefill/moe_fused_iq.cu:2931-2939`、HIP: 同 `:2998-3003`）。CUDA の Gyro-M は `STRATA_PF_FUSED_TQ` が明示的な `1` の場合だけで、CUDA の未設定時既定は Gyro-S のみです（`include/strata/prefill/fused_tq_default.hpp:28-29`）。
- CUDA の NT=256 / warp-specialized 経路が選ばれている場合は trellis pair の条件を満たしません（`src/prefill/moe_fused_iq.cu:2939`）。

## 実行時の詳細

CUDA は `tq_env()` 内の関数ローカル `static` で helper の値を一度 cache し、GPU ごとの `DevInfo` 初期化時にセットアップ可否を決めます（`src/prefill/moe_fused_iq.cu:2284-2287,2379-2385,2495-2503`）。HIP も `tq_hip_requested()` の関数ローカル `static` で最初の判定値を cache します（同 `:2646-2649`）。したがって、これらの読み取り後にプロセス環境を変更しても判定には反映されません。

MMQ なしの fused 専用ビルドでは、`src/prefill/prefill.cpp` の静的初期化が `main()` 前に実行されます。`getenv(name) != nullptr` ならユーザーが指定済みとして保持し、不在時は CUDA/HIP backend ごとの既定スイッチ一覧に含まれるこの変数を `setenv`（Windows は `_putenv_s`）で `1` にします（`src/prefill/prefill.cpp:204-237`、一覧と不在時だけ設定する規則: `include/strata/prefill/own_only_switches.hpp:18-25,48-56`）。

選択された pair は CUDA の `native_supported` から gate/up と down の fused trellis instance へ進みます。CUDA の Gyro-S / Gyro-M は native kernel の trellis 実装を使い、HIP は `native_w11_kernel` の trellis instance を使います。条件不足時の Strata 側の扱いは fused trellis pair を選ばないことです。ここで外れた後の外部ライブラリ内部の選択挙動は本書の対象外です（CUDA: `src/prefill/moe_fused_iq.cu:2929-2939,3309-3311,3328-3331`、HIP: 同 `:2994-3003,3214-3215,3227-3231`）。

## ログと測定値

この変数の値、有効化理由、またはセットアップ失敗を直接表示する Strata のログ出力は、確認した本番コードには見つかりませんでした。CUDA のセットアップ条件が成立しない場合は `d.tq` が立たず、選択条件を満たさない layer pair は trellis fused 経路から外れます（`src/prefill/moe_fused_iq.cu:2495-2503,2931-2939`）。文書 `docs/DETAILS.md` にこの変数の記載は見つかりませんでした。数値性能は記載しません。

## 根拠

- 値の解釈と CUDA 既定規則: `include/strata/prefill/fused_tq_default.hpp:23-31`
- fused 専用ビルドの起動前設定: `src/prefill/prefill.cpp:204-237`; helper: `include/strata/prefill/own_only_switches.hpp:18-25,48-56`
- CUDA の読み取り cache、デバイス条件、kernel setup: `src/prefill/moe_fused_iq.cu:2284-2287,2379-2429,2495-2503`
- CUDA の layer pair 判定と global gate: `src/prefill/moe_fused_iq.cu:2891-2908,2929-2939`
- HIP の値読み取り、OS / GPU class 条件: `src/prefill/moe_fused_iq.cu:2643-2672`; helper: `include/strata/prefill/fused_tq_hip.hpp:20-36`
- HIP の layer pair 判定と kernel 経路: `src/prefill/moe_fused_iq.cu:2994-3003,3214-3215,3227-3231`
