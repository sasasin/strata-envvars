# `FNX_PREFETCH_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は sFNX split engine の診断用 probe を有効にする。各層の FFN 入力 `b.mixed` に対して次層の router を別途計算し、各行の上位 `TOPK` expert（現行コードでは top 10）を予測として保存する。実際に次層で選ばれた expert と予測の重なり、RAM 上の expert slot にない expert の重なりを GPU 上で数える。推論の出力 token の選択条件をこの予測で置き換える処理ではない。一方、probe 有効時は router 内で行っていた expert-cache の計画を無効にし、probe 集計後に `moe_cache` 側で計画するため、診断計算と cache 計画の順序が変わる（`engine/src/split/src/engine.cu:230-234, 951-970`、`engine/src/split/src/kernels.cu:1750-1800`）。

環境変数を読むのは sFNX の split `Engine` 初期化時である。対象 engine は `strata-split` で、ビルドは既定で無効の opt-in 機能であり、CUDA または HIP で同じ split engine ソースを使う（`engine/src/split/CMakeLists.txt:1-7, 76-92, 120-140`）。

## 値と判定

`env_flag` は `env_int(name, 0) != 0` を使う。`env_int` は未設定時に 0 を返し、設定時は符号付き base-10 整数全体を `strtoll` で読み、後続文字がある値や整数範囲外を例外にする（`engine/src/split/src/env.hpp:15-21, 33-39, 51-52`）。

| 条件 | unset | 有効になる値 | 無効になる値・エラー |
|---|---|---|---|
| sFNX split の `Engine` 初期化 | 0 として無効 | `1`、`-1`、`+2` など、整数として parse でき 0 でない値 | `0`、`-0`、`+0` は無効。空文字、`true`、`1x`、前後の空白を含む値、`long long` 範囲外は無効値として例外 |

`getenv` が返す設定有無と数値判定を分けているため、空文字は「設定ありで有効」ではなく parse error になる。`1anything` のように数値の後ろを許容せず、大文字小文字を問わず `true`/`false` を認識する処理もない。CLI 引数や別環境変数による上書き・優先順位はない（`engine/src/split/src/env.hpp:15-21, 33-39, 51-52`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` でビルドした sFNX split 実行ファイルであること。split は通常の既定ビルドでは無効（`engine/src/split/CMakeLists.txt:1-7`）。
- engine の card 0 初期化で環境変数が非ゼロ整数として parse されること。カードごとの初期化ループでも `c == 0` の短絡条件内でのみ読み取り・probe buffer 確保を行うため、probe 用 buffer と集計は card 0 に限られる（`engine/src/split/src/engine.cu:156-160, 230-234`）。
- 少なくとも 1 層 window が処理されること。集計カウンタはゼロ初期化され、層ごとの実測と予測の処理が走ると増える。層 0 には前層の予測がないため score せず、最終層には次層予測を作らない（`engine/src/split/src/engine_parts.hpp:50-68`、`engine/src/split/src/engine.cu:960-967`）。
- `cache_live()` が true の場合、probe 有効化によって router 内の cache 計画を使わず、probe score の後 `moe_cache` で計画する。expert slot がない層では `slot_of` を渡さず、picked/guessed の全体集計のみを行う（`engine/src/split/src/engine.cu:951-970`）。

## 実行時の詳細

`Engine` の card buffer 作成中、card 0 で `env_flag("FNX_PREFETCH_PROBE")` を評価し、真なら `[MAXT][NEXP]` の probe logits、`[NL][MAXT][TOPK]` の予測 expert、7 個の `unsigned long long` 集計値をデバイス確保する。`dalloc` は確保領域をゼロ初期化する（`engine/src/split/src/engine.cu:156-160, 230-234`、`engine/src/split/src/engine_parts.hpp:50-68`）。

各 FFN window では、実 router が選んだ `topi` を score し、次層があれば同じ `b.mixed` と次層 router weight で `gemv_f32` を行い、`k_probe_guess` が各行の上位 10 index を求める。同点では小さい index を選ぶ。score は window 単位で distinct な expert 数を集計する。指標は `cnt[0..6]` に picked、guessed、両方、layer-window 数、slot 外 picked、slot 外で guessed された数、picked でなく slot 外にある guessed（コメント上の無駄な copy 候補）を記録する（`engine/src/split/src/engine.cu:960-970`、`engine/src/split/src/kernels.cu:1750-1800`）。

設定は engine の初期化時に読み、その時に probe buffer の有無へ固定される。関数内 static cache ではない。既存 engine の実行中に環境を変更しても反映されず、新しい engine を作るときはその時点の環境値が評価される（`engine/src/split/src/engine.cu:156-160, 230-234`）。

## ログと測定値

`fnx_run` の `mtp` 実行では、最後に `probe_counts()` が値を取得し、layer-window 数が正なら stdout に `prefetch probe: ...` を出す。slot 外 picked の件数が正なら `prefetch probe, experts in RAM: ...` も出す（`engine/src/split/src/engine.cu:697-703`、`engine/src/split/tools/fnx_run.cpp:1136-1144`）。sFNX server の実行経路には `probe_counts()` を表示する呼び出しがなく、ここで挙げた probe 集計の stdout 出力は確認できない（`engine/src/split/tools/sfnx.cpp:1122-1139`）。

整数として parse できない設定値は例外になる。`fnx_run` は stderr に `fnx_run: <理由>` を出して終了コード 1、sFNX は stderr に `sfnx: <理由>` を出し終了コード 1 で初期化失敗を終了する。parse error の理由は `FNX_PREFETCH_PROBE: '<値>' is not a whole number`（`engine/src/split/src/env.hpp:33-39`、`engine/src/split/tools/fnx_run.cpp:1364-1373`、`engine/src/split/tools/sfnx.cpp:1122-1136`）。性能・精度の測定値はソースから確認できないため記載しない。

## 根拠

- 読み取りと buffer 作成: `engine/src/split/src/engine.cu:156-160, 230-234`
- 値の parse と flag 判定: `engine/src/split/src/env.hpp:15-21, 33-39, 51-52`
- probe 計算・cache 計画との順序: `engine/src/split/src/engine.cu:951-970`
- top-10 の同点規則と score 集計: `engine/src/split/src/kernels.cu:1750-1800`
- buffer のゼロ初期化: `engine/src/split/src/engine_parts.hpp:50-68`
- 実行対象の範囲: `engine/src/split/CMakeLists.txt:1-7, 76-92, 120-140`
- `fnx_run` の集計表示と例外経路: `engine/src/split/tools/fnx_run.cpp:1136-1144, 1364-1373`
- sFNX の engine 初期化と例外経路: `engine/src/split/tools/sfnx.cpp:1122-1136`
