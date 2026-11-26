# `STRATA_PREFILL_BF16X2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系と SYCL 系の prefill にある BF16 重みの projection で、BF16 に丸めた活性値だけでなく、その丸めで失われた BF16 remainder も別 GEMM で積算するかを選びます。出力は通常の積 `W·hi` に remainder の積 `W·lo` を加えた形になり、prompt の数値結果が変わります。これ自体が decode の計算を切り替えるものではありません（`engine/src/prefill/prefill.cpp:885-898`、`engine/sycl/src/prefill/prefill.cpp:355-369`）。

## 値と判定

両実装とも `std::getenv` の結果を `std::atoi` に渡し、未設定なら `0` とします。変換した整数がちょうど `1` の場合は hyper-connection の remainder も有効にし、その他の非ゼロ値は hyper-connection を除く BF16 projection で remainder を有効にします。整数として `0` になる値は無効です。範囲検証・clamp はありません（`engine/src/prefill/prefill.cpp:891-898,998`、`engine/sycl/src/prefill/prefill.cpp:362-369,381`）。

| 実装経路 | unset | hyper-connection を含む有効値 | hyper-connection 以外の有効値 | 無効になる値の例 |
|---|---|---|---|---|
| CUDA/HIP (`engine/src/prefill`)・SYCL (`engine/sycl/src/prefill`)、FP16 I/O ではない場合 | `0` | `1` | `2`、`-1` など `atoi` 結果が非ゼロで `1` 以外 | 空文字、`0`、`0anything`、`true`、`false` |
| 同じ経路で `f16_io` が有効な場合 | `0` | 無効 | 無効 | 設定値にかかわらず remainder は無効 |

`atoi` は文字列全体の厳密な検証ではありません。先頭の空白と符号を許し、数値接頭部を変換するため、たとえば `" 1tail"` は `1`、`"2tail"` は `2`、数値接頭部のない文字列と空文字は `0` になります。したがって `"1anything"` は hyper-connection を含むモード、`"0anything"` は無効です。大文字小文字を判定する文字列比較はありません。`atoi` の表現可能範囲を超える入力の結果はこの実装で規定されていません。

## 有効になる条件

- BF16 活性値を使う prefill の BF16 projection が実行される必要があります。CUDA/HIP 系と SYCL 系にはそれぞれ読み取り実装があります。Metal 側はこの名前を読みません（ソース全体の完全一致検索では、読み取りは `engine/src/prefill/prefill.cpp:893` と `engine/sycl/src/prefill/prefill.cpp:364` のみ）。
- 各段の `f16_io` が false である必要があります。`f16_io` が true ならモード値にかかわらず `bf16x2_mode` は `0` を返します。HIP の FP16 prompt 経路は `prompt_f16()` が決め、`Prefill::init` が段ごとに `m.f16_io` へ設定します（`engine/src/prefill/prefill.cpp:2724-2729`、`engine/src/prefill/gemm.cu:681-699`）。SYCL の同じ初期化位置は `engine/sycl/src/prefill/prefill.cpp:1606-1611` です。
- `f16_io` を有効にする要因は別環境変数 `STRATA_HIP_PROMPT_F16` とそのデバイス別既定値です。この場合は本変数が数値的に有効でも remainder 部分は使われません。CLI 引数や設定ファイルが本変数の値を上書きする経路は確認できません。
- 対象の BF16 projection がモデル経路上で実行される必要があります。たとえば SSM alpha/beta、QSA indexer、MoE router、shared-expert gate、PLE key/value は mode が非ゼロのとき low-part バッファを使います。mode が `1` のときだけ hyper-connection の down/up/inject も low-part バッファを使います（`engine/src/prefill/prefill.cpp:2779-2780,5124-5157,5191-5192,5239-5240,5586,5654-5656`、SYCL の例: `engine/sycl/src/prefill/prefill.cpp:3459-3509,3541-3542,3574-3575,3925-3937`）。

## 実行時の詳細

環境変数を読む `bf16x2_mode` の `v` は関数内 `static const` です。初回呼び出し時の `getenv` / `atoi` 結果をプロセス内でキャッシュし、その後の環境変更は反映しません。mode の参照は prefill の workspace sizing と carve、および実際の projection 処理にあります（例: `engine/src/prefill/prefill.cpp:2255-2260,2779-2780,3746-3748`、`engine/sycl/src/prefill/prefill.cpp:1672-1673,2463-2465`）。そのため読み取りは初期化より前の sizing 呼び出しで起こる場合があります。

非 HC projection 用の low-part バッファは mode が非ゼロのとき確保され、HC 用の `xn16_lo` / `lo16_lo` は mode がちょうど `1` のときだけ確保されます。実行時は活性値を BF16 image と remainder に分け、通常の BF16 GEMM 後に remainder を同じ出力へ加算します。PLE では BF16 key weight がある場合に両方を GEMM し、key weight が native 型の場合は key projection 自体は native GEMM のままですが、value projection に remainder を加えます（`engine/src/prefill/prefill.cpp:5033-5045`）。router projection の結果は expert routing に渡されるため、丸め差が routing 結果に波及する可能性があります（同 `5584-5587`）。

## ログと測定値

この変数を直接報告するログ、専用の警告、専用の終了経路はありません。関連する BF16 projection が失敗を返した場合は既存の prefill 呼び出し元へ `false` が伝播しますが、この環境変数用のエラー文言はありません（例: `engine/src/prefill/prefill.cpp:5124,5155-5157,5191-5192`）。

Strata の benchmark report は `STRATA_PREFILL_BF16X2=1` を「各 BF16 活性値に low part も加える旧経路」の比較基準として挙げていますが、ここではその結果を本変数の一般的な速度・品質効果として扱いません（`docs/bench-results/2026-10-04-rdna2-fp16-prompt/README.md:125-129,149-155`）。

## 根拠

- 値変換、既定値、mode `1` と `2` の分岐、FP16 I/O 抑制: `engine/src/prefill/prefill.cpp:885-898,998`、`engine/sycl/src/prefill/prefill.cpp:355-369,381`。
- 初期化と段ごとの FP16 I/O 設定: `engine/src/prefill/prefill.cpp:2724-2729`、`engine/src/prefill/gemm.cu:681-699`、`engine/sycl/src/prefill/prefill.cpp:1606-1611`。
- 追加バッファと実際の low-part GEMM: `engine/src/prefill/prefill.cpp:2779-2780,5033-5045,5124-5157,5191-5192,5239-5240,5586,5654-5656`、`engine/sycl/src/prefill/prefill.cpp:1672-1673,3459-3509,3541-3542,3574-3575,3925-3937`。
- 関連資料の比較基準: `docs/bench-results/2026-10-04-rdna2-fp16-prompt/README.md:125-129,149-155`。
