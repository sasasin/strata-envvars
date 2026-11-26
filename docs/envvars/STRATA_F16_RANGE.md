# `STRATA_F16_RANGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の prefill 処理で FP16 に変換される値の最大絶対値と、FP16 の有限範囲を超えた値などの個数を数え、prompt ごとに stderr へ診断行を出すための計測スイッチです。数値として parse されず、設定有無だけで計測フラグを有効にします。計測分岐は `hf_sat` と FP16 GEMM の変換・出力処理にあります（`engine/src/prefill/prefill.cpp:2724-2731,7968-7974`、`engine/src/prefill/kernels.cu:58-77`、`engine/src/prefill/gemm.cu:88-124`）。

この変数自体は FP16 prompt 経路を有効化しません。HIP の FP16 prompt GEMM は別の `STRATA_HIP_PROMPT_F16` 判定で選ばれます（`engine/src/prefill/gemm.cu:681-712`）。

## 値と判定

`std::getenv(...) != nullptr` による設定有無の判定です。文字列の変換、空白・大文字小文字・数値形式の検査はありません。空文字も設定済みとして有効で、`0`、`false`、`0anything` も同じく有効です。未設定だけが無効です（`engine/src/prefill/prefill.cpp:2730-2731,7969-7971`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP (`__HIPCC__`) | 診断フラグを有効にしない | 空文字を含む、環境に存在するすべての値 | なし（値の内容は判定しない） |
| CUDA / その他の `prefill.cpp` ビルド | 診断フラグを有効にしない | 読み取り側では設定済みと判定するが、計測関数が実効化されない | なし |

CUDA では `set_f16_range` と `gemm_set_f16_range` が引数を無視し、`f16_range_read` と `gemm_f16_range_read` は `false` を返します。そのため設定しても診断行は出ません（`engine/src/prefill/kernels.cu:2921-2950`、`engine/src/prefill/gemm.cu:130-155`）。

## 有効になる条件

- `STRATA_F16_RANGE` が設定されていること。`Prefill::init` 内の設定有無判定が true になると、activation と GEMM の各計測フラグを on にします（`engine/src/prefill/prefill.cpp:2724-2731`）。
- 計測カウンターを持つ実装は HIP のみです。CUDA カーネルは `hf_sat` で計測フラグを読まず、計測用 device symbol も HIP 条件内にあります（`engine/src/prefill/kernels.cu:62-77`、`engine/src/prefill/gemm.cu:85-99`）。
- ログを出すには prompt 完了時に activation と GEMM の両方の読み取りが成功する必要があります。どちらかが false なら `fprintf` は実行されません（`engine/src/prefill/prefill.cpp:7968-7974`）。
- 実際に FP16 prompt GEMM の重み・出力が計測対象になるには、別条件として `Gemm::bf16` の HIP 実装で `f16_io_` が true である必要があります。これは `Prefill::init` が `prompt_f16()` の結果を設定し、`prompt_f16()` は `STRATA_HIP_PROMPT_F16` と device 判定で決めます（`engine/src/prefill/prefill.cpp:2727-2729`、`engine/src/prefill/gemm.cu:681-712,1169-1181`）。

## 実行時の詳細

環境変数は `Prefill::init` の関数内 `static const bool` で初回評価され、その後の init では再読込されません。prompt 終了側にも別の `static const bool` があり、最初にその箇所へ到達したときの設定有無を保持します。したがって、実行中に環境変数を追加・削除しても、各 cache の初期化後は反映されません（`engine/src/prefill/prefill.cpp:2724-2731,7968-7971`）。

HIP では init 中に現在の stage device のもとでカーネルの計測フラグを設定します。activation 側の `hf_sat` は `|f| > 65504` または NaN を数え、最大絶対値を保持します。FP16 GEMM 側は BF16 重みを飽和付き FP16 に変換する値（slot 0）と、FP16 GEMM 出力を FP32 に widen する際の値（slot 1）を計測します（`engine/src/prefill/prefill.cpp:2724-2731`、`engine/src/prefill/kernels.cu:66-77`、`engine/src/prefill/gemm.cu:94-124`）。

prompt 終了時にカウンターを読み、読み取り成功時はリセットを要求します。両方の読み取りに成功すると `strata f16 range: ...` を stderr に出します。activation 側の読み取り・リセットに失敗した場合は false、GEMM 側の読み取り失敗も false となり、この診断行は出ません（`engine/src/prefill/kernels.cu:2932-2949`、`engine/src/prefill/gemm.cu:141-155`、`engine/src/prefill/prefill.cpp:7968-7974`）。

device symbol への計測フラグ設定に失敗した場合は、activation 側が `prefill: setting the FP16 range check failed: %s`、GEMM 側が `prefill gemm: setting the FP16 range check failed: %s` を stderr に出し、どちらも `exit(1)` します（`engine/src/prefill/kernels.cu:2921-2927`、`engine/src/prefill/gemm.cu:130-139`）。

## ログと測定値

計測行は次の実装文字列で stderr に出ます。`n` はその prompt の token 数、`xm/xo` は activation 計測、`wy[0]/wyo[0]` は BF16 重みから FP16 への変換、`wy[1]/wyo[1]` は FP16 GEMM 出力の値です。

```text
strata f16 range: %lld tokens: activation images max |x| %.1f (%llu beyond 65504 or NaN), BF16 weights max |w| %.3f (%llu), FP16 GEMM outputs max |y| %.1f (%llu not finite)
```

設定がないときは計測行を出しません。計測値そのものや性能測定値はソースから確認できず、本書には記載していません（`engine/src/prefill/prefill.cpp:7968-7974`）。

## 根拠

- `engine/src/prefill/prefill.cpp:2724-2735` — init 時の読み取り、static cache、stage device 上の計測 flag 設定、および独立した `STRATA_HIP_PROMPT_F16` との関係。
- `engine/src/prefill/prefill.cpp:7968-7974` — prompt 終了時の読み取り、reset 要求、出力条件と stderr の文言。
- `engine/src/prefill/kernels.cu:58-77,2921-2950` — HIP 限定の activation counter、65504/NaN 判定、設定失敗時の終了、CUDA の no-op / false。
- `engine/src/prefill/gemm.cu:85-155,1169-1181` — HIP 限定の重み・GEMM 出力 counter、read/reset、および FP16 prompt GEMM の条件。
- `engine/src/prefill/gemm.cu:681-712` — `prompt_f16()` が HIP で別途 `STRATA_HIP_PROMPT_F16` と device 情報から FP16 prompt 経路を決める箇所。
