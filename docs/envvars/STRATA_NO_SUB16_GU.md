# `STRATA_NO_SUB16_GU`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA/HIP と SYCL の量子化 expert カーネルで、対応するサブワープ行分割（CUDA/HIP の gate/up では主に16 lane行）を選ばず、全ワープ幅のカーネル構成へ切り替えるための開発・診断用フックです。環境変数を設定しただけでモデル全体の計算方式を一律に変えるものではなく、対象の grouped expert カーネルと形状・データ型の条件に合う経路でのみ効きます。

## 値と判定

CUDA/HIP と SYCL の両実装は同じ `env_on()` 判定を使います。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0` | OFF（例: `0`, `0anything`） |
| 空でなく、先頭文字が `0` 以外 | ON（例: `1`, `2`, `true`, `false`, `anything`） |

文字列全体や数値としての妥当性は調べず、空文字かどうかと先頭文字だけを確認します。大文字小文字、空白、後続文字は判定に影響しません。

## 有効になる条件

- CUDA/HIP では `src/kernels/cuda/iq_kernels.cu` の量子化 grouped expert 実装に作用します。主に split 形式の gate/up および down の multi カーネルで、テンプレート引数によりサブ16経路を外した実装を選びます。gate/up の起動 grid も、`n_embd == 2560` などの条件を満たす場合に16行単位から通常の `GU_ROWS` 単位へ変わります。
- CUDA/HIP の gate/up では、入力形状から1行あたりの dot 数が80でない場合にもコードが自動的にサブ16経路を避けます。その場合、環境変数の有無による差はありません。
- 旧 IQ MMVQ 経路、split でない形式、または別の融合・レイアウト経路が選ばれる場合は、この変数の分岐が実行されないことがあります。たとえば CUDA の `STRATA_EXP_LAYOUTS` の fused gate/up カーネルや `STRATA_EXPDEC` の専用経路では、通常の `launch_gu` / `launch_down` の選択を通らない場合があります。HIP の AMD layout による専用起動経路も別にあります。
- SYCL (`sycl/src/kernels/cuda/iq_kernels.dp.cpp`) では、この変数の参照は grouped expert の down 側 row 数の選択です。`n_ff == 640` かつ旧カーネルでない場合に、未設定なら down の行数を型に応じて32/16/8にし得ますが、ON にすると8行にします。その他では元から8行です。この SYCL 実装では gate/up の分割選択には参照されません。
- 対象 backend 自体がビルド・実行されていない場合や、対応する量子化 grouped expert 経路が使われない場合には効果はありません。

## 実行時の詳細

値は `iq_kernels.cu` または SYCL の対応翻訳単位にある `g_no_sub16_gu` のグローバル初期化時に読み取られます。実行中の環境変更を再読込する処理や、この変数の値を変更する setter はありません。CUDA/HIP では `launch_gu()` と `launch_down()` がこのフラグをテンプレート引数に渡し、通常の16-lane subwarp 行カーネルではなく全ワープ構成の multi カーネルを選びます。staged trellis down カーネルでは codebook staging の選択は保ったまま、行分割だけ切り替えます。

この変数自体を理由にしたログ、警告、エラー出力は実装にありません。関連する `docs/EXPERTDEC.md` は一部 expert カーネルの lane 分割と計算について説明していますが、この環境変数の値判定や適用範囲は記載していません。性能差や出力の同一性をこの調査で測定していません。

## 根拠

- 値判定と読み取り: `src/kernels/cuda/iq_kernels.cu:3273-3279`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3199-3210`。
- CUDA/HIP gate/up の形状条件、staged/unstaged multi kernel の選択: `src/kernels/cuda/iq_kernels.cu:4073-4103`。
- gate/up launch grid と専用経路（fused gate/up、SwiGLU fusion、AMD layouts、expert decode）: `src/kernels/cuda/iq_kernels.cu:4130-4150,5119-5123,5133-5205`。
- CUDA/HIP down のテンプレート分岐および down grid: `src/kernels/cuda/iq_kernels.cu:4154-4169,5232-5236`。
- SYCL down row 数の条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5760-5763`。
- SYCL が独立 backend であること: `CMakeLists.txt:14-19`。
- 関連設計資料: `docs/EXPERTDEC.md:11,46-48`。
