# `HIPK_CFG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 の HIP i-quant expert 計算で、register-weights matrix-core kernel の tile 構成を選びます。指定値は gate/up と down の各 launch に使う行 tile 幅と列 tile 構成を選び、計算式そのものは切り替えません。HIP build の `ds4_iq.cu` から呼ばれる経路に限られ、CUDA / Metal / CPU の経路では読み取られません。`HIPK_CFG` 自体は matrix-core 経路を有効にしません。デバイス・モデル形式などの適用条件を満たし、別変数 `STRATA_DS4_HIPK` によりその経路が有効なときだけ参照されます。

## 値と判定

読み取りは `std::getenv("HIPK_CFG")` と `std::atoi` です。未設定なら 0、空文字も `atoi` の結果 0 になります。整数として完全に検証せず、`atoi` が読む先頭の数値部分と符号・先行空白に従います（例: `2tail` は 2、数値で始まらない文字列は 0）。`int` の範囲を超える値の変換結果は保証されません。範囲制限やエラー報告はなく、変換後の値が 1〜11 のいずれかに一致した場合だけ明示 tile を選びます。

| 値 | 選択する register-weights tile | 適用条件 |
|---|---|---|
| 1 | `BM=32, NW=4, NTW=1`（列幅 64） | `max_rows <= 32` |
| 2 | `BM=32, NW=8, NTW=1`（列幅 128） | `max_rows <= 32` |
| 3 | `BM=32, NW=2, NTW=2`（列幅 64） | `max_rows <= 32` |
| 4 | `BM=32, NW=8, NTW=2`（列幅 256） | `max_rows <= 32` |
| 5 | `BM=32, NW=2, NTW=1`（列幅 32） | `max_rows <= 32` |
| 6 | `BM=64, NW=8, NTW=1`（列幅 128） | 常時 |
| 7 | `BM=32, NW=8, NTW=1`（列幅 128） | 常時 |
| 8 | `BM=128, NW=8, NTW=2`（列幅 256） | 常時 |
| 9 | `BM=64, NW=4, NTW=2`（列幅 128） | 常時 |
| 10 | gate/up: `BM=128, NW=8, NTW=1`（列幅 128）。down: `BM=128, NW=8, NTW=2`（列幅 256） | 常時 |
| 11 | `BM=64, NW=8, NTW=2`（列幅 256） | 常時 |
| 未設定、0、その他 | 行数に応じた自動設定 | 常時 |

1〜5 は `max_rows > 32` ならその指定を採らず、自動設定に進みます。自動設定は `max_rows <= 32` で `BM=32, NW=4, NTW=2`、`<=64` で `BM=64, NW=4, NTW=2`、それより大きければ `BM=128, NW=8, NTW=1` です。

## 有効になる条件

- HIP build で DeepSeek-V4.1 i-quant expert の gate/up または down kernel が `launch_set` に到達すること。`HIPK_CFG` の読み取りは `STRATA_USE_HIP` の実装内にあります。
- 対象の量子化型が IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S / IQ4_XS / IQ1_S / IQ1_M / IQ4_NL のいずれかであること。
- 現在の GPU が gfx11 または gfx12 系として認識され、`STRATA_DS4_HIPK` の判定で matrix-core 経路が有効であること。通常判定では gfx12 は `STRATA_DS4_HIPK` が未設定または先頭文字が `0` 以外で有効、gfx11 は gfx1151 で未設定なら有効、その他 gfx11 は先頭文字が `1` の場合に有効です。gfx11 で `STRATA_DS4_HIPK` の `atoi` 結果が 2 のときは shared-memory weights kernel 専用のため、この変数を読む register-weights 分岐に入りません。
- `max_rows > 16`、K が 256 の倍数、出力列数 N が 64 の倍数、`ldx` が 8 の倍数、`ldo` が 2 の倍数で、対象入力ポインターが 16-byte aligned であること。

明示 tile の列幅が N を割り切らない場合、`runr` は false を返し、呼び出し元は標準 HIP tile kernel に進みます。よって値が 1〜11 でも、常に指定 tile が起動するわけではありません。別変数 `STRATA_DS4_X16` は gate/up の register-weights kernel で F16 入力経路を選ぶ条件に関係しますが、`HIPK_CFG` の tile 選択値は変更しません。

## 実行時の詳細

`HIPK_CFG` は `hipk::launch<T, GU>` の関数テンプレート内の `static const int` として、対応経路が最初に呼ばれたときに読み取られます。テンプレートの各型・gate/up/down の特殊化ごとに初期化され、その特殊化では以後再読込されません。したがって、プロセス実行中に環境値を変えても、既に初期化された特殊化には反映されません。

値 1〜11 が選ぶ register-weights tile は `set_kernel_r` を dispatch し、その他の値や条件不成立時は行数ベースの自動設定に進みます。`runr` 内では選択した列 tile 幅で N を割り切れるかを確認し、不成立なら `false` を返します。`launch_set` は `hipk::launch` が false のとき標準 HIP kernel を起動します。matrix-core 対象外、モデル型・次元条件不成立、または `STRATA_DS4_HIPK` が経路を無効にする場合も `HIPK_CFG` による選択には至らず、呼び出し元の標準 kernel 経路へ進みます。

`HIPK_CFG` を表示するログや、値の不正を通知するエラーはこの経路にありません。kernel launch の `cudaPeekAtLastError()` が失敗すると `runr` は false を返して呼び出し元の標準 kernel に移ります。`HIPK_CFG` の値自体による終了・警告は確認できません。

## 根拠

- `src/dsv41/ds4_iq_hip.inc:10-12` は HIP build 条件と実装 namespace、`src/dsv41/ds4_iq.cu:1184-1201` は include と `STRATA_USE_HIP` 下での dispatch、および false 時の標準 kernel 経路を示します。
- `src/dsv41/ds4_iq_hip.inc:21-23,297-334` は対応量子化型、共通の適用条件、`STRATA_DS4_HIPK` と `HIPK_CFG` の分岐、値ごとの tile と自動設定を示します。
- `src/dsv41/ds4_iq_hip.inc:237-270` は gfx 世代ごとの有効条件と device ごとの状態 cache を示します。
- `src/dsv41/ds4_iq_hip_r.inc:211-231` は選択 tile の列幅検査、kernel launch、launch error 時の戻り値を示します。
- `src/dsv41/ds4_iq_hip_r.inc:217-231` は `HIPK_DBG` / `STRATA_DS4_X16` を読む register-weights kernel と launch の処理を示します。
- Strata `docs/DETAILS.md` に `HIPK_CFG` / `STRATA_DS4_HIPK` の記述は見つかりませんでした。上記の説明は現行ソースの分岐に基づきます。
