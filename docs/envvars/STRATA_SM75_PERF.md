# `STRATA_SM75_PERF`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA compute capability 7.5（Turing / RTX 20 系）向けに用意された、ビット単位で同じ結果になるとされる複数のカーネル実装を、各機能の既定経路として選ぶための共通 opt-in です。個々のカーネルを直接一つ選ぶ変数ではなく、この変数が有効で、GPU が 7.5 と判定され、かつ個別スイッチが未設定の場合に、その機能の Turing 実装を選びます。

該当する機能には、interleaved small-batch matvec、expert layout mode 4、hyper-connection の read/up/down、QSA の selection/top-k、decode attention、Q2_0 matvec、decode 層の wait 統合、BF16 dequant の vector store、prompt attention v1 prefetch があります。各実装の具体的なゲート名と範囲は `docs/DETAILS.md:2244-2261` に列挙されています。

## 値と判定

共通 helper は `std::getenv("STRATA_SM75_PERF")` の結果を `std::atoi(e) != 0` で判定し、結果を関数内の `static const bool` に保存します（`include/strata/core/sm75_series.hpp:24-31`）。文字列全体の妥当性は検査しません。

| 値 | helper の結果 |
|---|---|
| 未設定 | `false` |
| 空文字 | `false`（`atoi("")` は 0） |
| 数値として 0 に変換される文字列（例 `0`, `junk`, `0x1`） | `false` |
| 数値として 0 以外に変換される文字列（例 `1`, `-1`, `2`, `1junk`） | `true` |

`atoi` は先頭の空白と符号を許容し、先頭の数値部分を変換します。したがって `" 1x"` は有効、`"x1"` は無効です。値の判定はプロセス内で `sm75_series()` が最初に呼ばれた時に一度だけ行われ、その後の環境変更では更新されません。

## 有効になる条件

- helper の GPU 判定が compute capability 7.5 であること。判定は `is_sm75()` から `cc_major_of()` / `cc_minor_of()` を通り、通常は GPU 属性を使います。`STRATA_EMULATE_CC=75` を設定したテスト経路では、実 GPU が別世代でも 7.5 として判定され得ます（`include/strata/core/sm75_series.hpp:33-37`, `include/strata/core/emulate.hpp:14-24`）。
- CUDA の該当実装がビルドされ、その機能を使う実行経路に入ること。HIP ではこの Turing 系列は選択されず、たとえば `src/core/verify.cpp:276-280` の `device_is_sm75()` は HIP ビルドで常に `false` を返します。
- 対応する個別スイッチが未設定であること。個別スイッチは系列の既定を上書きします。たとえば `STRATA_SM75_IL=0` は matvec table を無効化し、`STRATA_SM75_IL=1` は有効化します（`src/kernels/cuda/native_mmvq.cu:3056-3064`）。`STRATA_SM75_EXP` も同様に expert layout を個別制御します（`src/kernels/cuda/iq_kernels.cu:4182-4187`）。

個別スイッチの形式は統一されていません。`sm75_switch()` を使うものは、対象 GPU が 7.5 である場合に限り、個別変数が設定されていれば `atoi(value) != 0`、未設定なら本変数の値を使います（`include/strata/core/sm75_series.hpp:39-44`）。一方、個別関数が本変数の既定値を参照する機能もあります。たとえば QSA の `STRATA_TOPK_SPLIT` は `=1` なら GPU 世代に関係なく有効、未設定時は本変数と 7.5 判定の両方が成立する場合だけ有効です（`src/kernels/cuda/qsa_select.cu:2246-2258`）。個別変数の条件があるため、本変数だけで全 GPU に一律のカーネル選択を強制するものではありません。

数値の和順を変えるなど結果の数値に影響するオプションは、この系列スイッチに含まれず、それぞれ明示 opt-in のままです。例は `STRATA_SELECT_SIMT`、`STRATA_PA_V2T`、`STRATA_PF_FUSED_SM75`、`STRATA_BF16_TC` です（`include/strata/core/sm75_series.hpp:13-15`, `docs/DETAILS.md:2259-2261`）。

## 実行時の詳細

この変数の読み取り自体は共通 header の helper に集約されています。`sm75_default()` は 7.5 判定と系列スイッチを組み合わせ、個別ゲートが未設定の場合の既定値を返します。呼び出し側の多くは GPU ごとに属性確認結果を cache します。別の呼び出し箇所では `sm75_switch()` を通じて、個別スイッチを優先し、未設定時だけ系列スイッチへ fallback します。

コード上の適用箇所は次の通りです。

- `src/core/verify.cpp:275-290`: CUDA の Turing 判定を cache し、decode wait 融合の既定条件に使います。
- `src/kernels/cuda/fused_gr.cu:1190-1206,1208-1230`: hyper-connection up カーネルと、条件を満たす token 数（4 または 6）の staged down カーネルを選びます。
- `src/kernels/cuda/native_mmvq.cu:2476-2490,3056-3088`: Q2_0 warp rows と interleaved matvec table の既定選択に使います。
- `src/kernels/cuda/qsa_select.cu:1676-1707,2246-2258,2476-2492`: QSA scorer、decode selection、prompt top-k の個別選択既定に使います。
- `src/kernels/cuda/qsa_decode_attn.cu:437-450`: decode attention v3 を選びます。
- `src/kernels/cuda/qsa_prompt_attn.cu:2324-2332`: Turing の prompt attention v1 経路で prefetch 版を選ぶ既定に使います。
- `src/kernels/cuda/iq_kernels.cu:4182-4204`: Turing expert layout mode 4 を選びます。大きい group 数の down projection では CUDA layout に戻します。
- `include/strata/core/tc_sm75.hpp:19-23` と `src/kernels/cuda/dequant_bf16.cu:378-389`: BF16 dequant の vector-store 版を個別スイッチ `STRATA_TC_SM75` の既定として選ぶ経路があります。出力アラインメントと row stride の条件も満たす必要があります。

環境変数に関する stdout/stderr ログや、無効値の警告はこれらの読み取り経路にはありません。各機能の実際の起動条件（形状、アラインメント、個別フラグなど）を満たさなければ、変数が有効でも Turing 版は呼ばれません。

## 根拠

- 共通の読み取り、`atoi` 判定、static cache、デバイス世代の絞り込み: `include/strata/core/sm75_series.hpp:24-44`。
- 世代エミュレーション: `include/strata/core/emulate.hpp:14-24`。
- Turing 系列の対象機能と、数値変更オプションの除外: `docs/DETAILS.md:2244-2261`。同資料は RTX 2080 Ti で測定された性能として decode +5〜6%、prompt 最大 +30% を記していますが、この文書ではコードから測定を再確認していません。
- 上記の実装箇所: `src/core/verify.cpp:275-290`, `src/kernels/cuda/fused_gr.cu:1190-1230`, `src/kernels/cuda/native_mmvq.cu:2476-2490,3056-3088`, `src/kernels/cuda/qsa_select.cu:1676-1707,2246-2258,2476-2492`, `src/kernels/cuda/qsa_decode_attn.cu:437-450`, `src/kernels/cuda/qsa_prompt_attn.cu:2324-2332`, `src/kernels/cuda/iq_kernels.cu:4182-4204`, `include/strata/core/tc_sm75.hpp:19-23`, `src/kernels/cuda/dequant_bf16.cu:378-389`。
