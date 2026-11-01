# `STRATA_SM75_EXP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Turing（compute capability 7.5）の CUDA native expert grouped kernel で、gate/up projection に AMD 向けとして実装された expert layout の mode 4 を選ぶスイッチです。通常の CUDA layout は mode 0 です。変数は `exp_mode()` 内で `strata::sm75_switch()` に渡されます。これは名前が候補一覧にあるだけの変数ではなく、Strata が実際に `getenv` で読む設定です。

## 値と判定

`sm75_switch()` はまずデバイスが Turing（または `STRATA_EMULATE_CC=75` による同等の compute capability）かを調べ、Turing 以外ではこの変数を読みません。Turing の場合、設定値を `std::atoi()` で整数変換し、変換結果が 0 以外なら ON、0 なら OFF とします。文字列全体の妥当性検査はありません。

| `STRATA_SM75_EXP` | 判定（Turing の場合） |
| --- | --- |
| 未設定 | `STRATA_SM75_PERF` の判定に従う。`STRATA_SM75_PERF` も未設定なら OFF |
| 空文字 | `atoi("") == 0` なので OFF |
| 数値として 0 に変換される値（例 `0`, `00`, `abc`） | OFF |
| 数値として非ゼロに変換される値（例 `1`, `-1`, `2`, `1tail`） | ON |

`atoi` は先頭の空白と符号を許し、数字列の後ろにある文字列を検査しません。数字で始まらない値は 0 になります。範囲外の整数文字列について、コードは別途エラー処理をしていません。

## 有効になる条件

- 対象は `src/kernels/cuda/iq_kernels.cu` にある native expert layout 選択です。HIP gfx906 は `exp_mode()` の別分岐で既定 mode 7 を返し、`STRATA_SM75_EXP` の判定には進みません。それ以外の共通分岐では、`sm75_switch()` が device capability 7.5 の場合にだけこの変数を判定します。
- デバイス capability が 7.5 でなければ、設定を `1` にしてもこのスイッチは ON になりません。compute capability のエミュレーションを使う場合は `STRATA_EMULATE_CC=75` も capability 判定に影響します。
- unset 時は `STRATA_SM75_PERF` が既定値を決めます。同変数は static 初回評価で `atoi(value) != 0` と判定されるため、値が `1` に限らず非ゼロ整数なら既定 ON です。`STRATA_SM75_EXP` を明示設定すると、その値が `STRATA_SM75_PERF` より優先し、両方向に上書きします。
- `STRATA_EXP_MODE` が 0 以上の整数に変換される場合は `exp_mode()` の明示 mode として優先し、Turing 判定による mode 4 を使いません。native expert benchmark の `native_expert_set_mode()` が mode を設定した場合も、その非負 mode が優先されます。通常利用者向け CLI 引数による `STRATA_SM75_EXP` の上書きは、調査対象ソースでは確認できません。
- CUDA の grouped kernel では、`grid_groups > 0 && grid_groups < cap_groups` のとき gate/up の `em0` は mode 0 に固定されます。したがって設定が ON でも、その呼び出しでは mode 4 の gate/up layout は使われません。
- mode 4 が選ばれた通常設定でも、down projection は `cap_groups > 30` のとき mode 0 に戻ります。ただし `STRATA_EXP_MODE` が設定されている場合（負値を含む）または benchmark setter による mode 指定がある場合、この特別な down fallback は行いません。

## 実行時の詳細

`exp_mode()` は `STRATA_EXP_MODE` を関数内 static 値として初回に読み、同じ関数の `per_dev[64]` に GPU ごとの自動 mode を保存します。自動 mode 選択に入るときだけ `sm75_switch("STRATA_SM75_EXP", ...)` が呼ばれます。helper 自体にはこの変数専用の cache はありませんが、呼び出し元のデバイス別 mode cache に結果が残るため、選択後に環境を変更してもそのデバイスでは再評価されません。`STRATA_SM75_PERF` も helper 内で static cache されます。

Turing でこのスイッチが有効になり、より優先度の高い mode 指定がない場合、`exp_mode()` は mode 4 を返します。通常の CUDA grouped expert 経路はその mode を `em0` として gate/up layout と kernel dispatch に使い、down projection 側も条件を満たせば mode 4 を選びます。down projection については、window が大きいとき（`cap_groups > 30`）に既定の mode 4 が遅いという実装注釈に基づき mode 0 へ戻す分岐があります。

この変数を読み取ったことだけを示す専用ログや警告は見つかりません。CUDA kernel 起動後の `check()` が失敗を報告する経路はありますが、`STRATA_SM75_EXP` の値が無効だから終了する、という検証・終了経路はありません。`docs/DETAILS.md` は Turing kernel 群を opt-in とし、`STRATA_SM75_EXP` を `STRATA_SM75_PERF` の個別上書きの一つとして記載しています。ソース注釈は mode 4 が RTX 2080 Ti 上の実測で mode 0 と bitwise equal だったとしていますが、この調査では計測を再実施していません。

## 根拠

- `include/strata/core/sm75_series.hpp:24-44` — `STRATA_SM75_PERF` の static 読み取り、capability 判定、個別変数の `atoi` 判定と優先関係。
- `include/strata/core/sm75_series.hpp:10-11,33-37` — 非 7.5 デバイスを対象外とする条件と `STRATA_EMULATE_CC` を含む capability 判定。
- `src/kernels/cuda/iq_kernels.cu:5536-5550` — CUDA build にも `STRATA_EXP_LAYOUTS` を含める設定と CUDA の mode 0 既定値。
- `src/kernels/cuda/iq_kernels.cu:6146-6184` — `STRATA_EXP_MODE` と benchmark mode の優先順位、デバイス別 cache、Turing の mode 4 選択。
- `src/kernels/cuda/iq_kernels.cu:6323-6335,6353-6385,6417-6421,6455-6491` — grouped kernel における mode の選択と gate/up・down dispatch。
- `src/kernels/cuda/iq_kernels.cu:6186-6199` — `STRATA_EXP_MODE` が未指定の既定 down fallback と `cap_groups > 30` の条件。
- `docs/DETAILS.md:1069-1079` — Turing kernel 群が opt-in で、個別スイッチが `STRATA_SM75_PERF` に優先するという説明。
