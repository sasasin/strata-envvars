# `STRATA_EXPDEC_R`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

EXPDEC の gate/up カーネルで、lane がまとめて計算する出力行数 `R` を選びます。既定値は 1 で、値が整数としてちょうど 2 の場合だけ 2 が使われます。EXPDEC 自体を有効にするスイッチではありません。

## 値と判定

`env_int_or()` は環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を使います。その後 `expdec_r()` が結果を検査し、整数値が 2 なら 2、それ以外はすべて 1 に正規化します。

| 環境値 | `atoi` の結果 | gate/up の R |
|---|---:|---:|
| 未設定、空文字 | 既定値 1 | 1 |
| `2`, `02`, `+2`, `2junk`, `2.5` | 2 | 2 |
| `1`, `0`, `-2`, `true`, `junk`, `0x2` | 変換結果（例では 1 / 0 / -2 / 0） | 1 |

文字列全体の妥当性は検査しません。`atoi` が先頭の空白と符号を許容し、数値以降を読み飛ばすため、たとえば `  +2tail` も 2 になります。`true` のような変換不能文字列は 0 になり、既定値へ戻るのではなく `R=1` になります。整数の表現範囲を超える入力の結果は、この実装から保証できません。

## 有効になる条件

- この設定値を読む実装は `src/kernels/cuda/iq_kernels.cu` にあります。同 `.cu` は CUDA/HIP の kernel target に含まれますが、backend により前段の layout 分岐が異なります。EXPDEC の説明資料は CUDA 専用機能としています。HIP での実機動作はこの調査では確認していません。
- EXPDEC の gate/up 経路が有効である必要があります。環境変数 `STRATA_EXPDEC` または呼び出し側の `native_expert_set_expdec()` により EXPDEC が有効で、かつ `STRATA_OLD_IQ_MMVQ` が有効でない場合にのみ候補になります。
- gate/up の量子化 type が `16`, `17`, `18`, `21`, `22` のいずれかで、`n_embd == 32 * ED_XB`、`n_ff` が 64 の倍数かつ正である必要があります。対象外なら既定カーネルへ進みます。
- `STRATA_EXPERT_V2` の専用経路（条件を満たす場合）および `STRATA_EXPERT_V2K` の専用経路では `native_expert_grouped()` が先に return するため、EXPDEC gate/up の判定に到達しません。
- AMD layout を選ぶ `STRATA_EXP_MODE` の分岐でも、対応 layout を選んだ場合は EXPDEC の gate/up 判定を通らないことがあります。モード 0 などで通常 layout 側へ進む場合は、以降の条件を満たせば判定されます。
- gfx12（RDNA4）では、`STRATA_DEFAULTS=026` でなく `STRATA_GFX12_DEFAULTS` が `0` で始まらない場合、Strata は `STRATA_EXPDEC=1` を architecture default として追加します。ただし利用者が `STRATA_EXPDEC` を何らかの値で設定済みならその値が優先されます。この既定設定は `STRATA_EXPDEC_R` の値自体を変更しません。
- C++ API の `native_expert_set_expdec_params()` が呼ばれ、`gu_rows_per_lane > 0` を渡すと、その値が環境から読み込んだ値を上書きします。Strata の通常エンジン内でのこの setter 呼び出しは確認できず、同梱 `expdec_bench` からは呼び出されます。

## 実行時の詳細

`g_expdec_r` は `iq_kernels.cu` のグローバル変数初期化で `env_int_or("STRATA_EXPDEC_R", 1)` を呼びます。したがって値は同翻訳単位の初期化時に読み取られ、以後の環境変更では再読込されません。正の値を渡す API setter による上書きは別途可能です。読み取り自体は `STRATA_EXPDEC` の有効／無効にかかわらず初期化時に行われますが、値がカーネル選択に使われるのは前節の条件を満たす EXPDEC gate/up 経路です。

EXPDEC 経路では `R=2` または `R=1` のテンプレートカーネルを選び、`R` に応じて行ごとの処理と rows-per-block の計算が変わります。EXPDEC が有効な状態で該当形式に初めて遭遇すると stderr に `strata expdec: CUDA... gate/up type ...: expdec_gu_kernel R <値> ...` が出ます。形式・形状が未対応なら `... not covered: the default kernel runs` と出て通常カーネルを使います。ゲート／アップ形状の `n_ff` が 32 で割り切れない場合は、それより前に `native_expert_grouped: n_ff ...` を出して `exit(1)` しますが、これはこの環境値の検査やエラーではありません。

`docs/EXPERTDEC.md` は EXPDEC を CUDA 専用と説明します。一方、コードは HIP build にも含まれる共有 `.cu` 実装で、AMD layout 分岐が EXPDEC に到達せず通常 layout に続く場合は同じ判定を呼びます。gfx12 の architecture default にも `STRATA_EXPDEC=1` が含まれます。よって資料の「CUDA 専用」という説明と、この commit の共有実装・gfx12 default の関係には差があります。実機での backend 動作確認はこの調査では行っていません。

`STRATA_EXPDEC_R` 自体に無効値のエラー、警告、終了経路はありません。別の down projection 用値 `STRATA_EXPDEC_DR` はこの値とは独立です。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:773`。これは候補名の一覧であり、実装根拠ではありません。
- 値の読み取り、既定値、整数化、正規化: `src/kernels/cuda/iq_kernels.cu:4055-4059,4063-4064,4074-4075`。
- EXPDEC の gate/up 条件、形式・形状、旧 kernel による無効化、カーネル選択: `src/kernels/cuda/iq_kernels.cu:4077-4080,4110-4118,4151-4165`。
- `STRATA_OLD_IQ_MMVQ` の読み取り: `src/kernels/cuda/iq_kernels.cu:3395-3401`。
- V2/V2K 専用分岐と EXPDEC 呼び出し箇所: `src/kernels/cuda/iq_kernels.cu:6267-6279,6284-6321,6410-6415`。
- AMD layout 分岐と共有 `.cu` の HIP 向け注記: `src/kernels/cuda/iq_kernels.cu:5536-5550,6328-6403`。kernel target への収録: `CMakeLists.txt:502`。gfx12 で `STRATA_EXPDEC=1` を追加する default と利用者値の優先: `src/core/arch_defaults.cpp:25-53,167-189`; default 適用時期: `src/program/generate.cpp:3400`。
- API setter による上書きと実行時パラメータ公開: `src/kernels/cuda/iq_kernels.cu:6216-6238`。同梱 bench の setter 呼び出し: `src/kernels/expdec_bench.cpp:106`。
- grouped expert 呼び出し: `src/core/verify.cpp:2221-2236`。形状エラーと終了: `src/kernels/cuda/iq_kernels.cu:6246-6252`。
- ログの文言と一形式あたりの初回出力: `src/kernels/cuda/iq_kernels.cu:4120-4141`。
- 機能が CUDA 専用であること、既定 R=1: `docs/EXPERTDEC.md:1-4,23-24`。ヘッダー上の環境ノブ説明: `include/strata/kernels/iq_kernels.hpp:113-123`。
