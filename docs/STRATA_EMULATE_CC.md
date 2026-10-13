# `STRATA_EMULATE_CC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

テスト用の環境変数です。GPU の compute capability と opt-in shared-memory 上限を、ホスト側の Strata コードが判定する際に指定値へ置き換えます。GPU 自体や CUDA/SYCL のデバイスコードをエミュレートするものではありません。たとえば、新しい GPU 上で古い世代向けにコンパイルされた PTX を実行するとき、ホスト側の経路選択もその世代に合わせるためのフックです。ヘッダーのコメントは「速度の測定値は実 GPU の性能を示さないが、結果は実 GPU 上で得たもの」と説明しています（`include/strata/core/emulate.hpp:1-7`）。

## 値と判定

`std::getenv()` の値を `std::atoi()` で整数に変換し、`75 <= 値 < 120` なら有効、それ以外は無効（0）です。`atoi` は文字列全体を検証しないため、先頭の整数部分だけが使われます。

| 値 | 判定 |
|---|---|
| 未設定、空文字、整数に変換できない文字列 | 無効（0） |
| `75`〜`119`（両端を含む） | その整数を emulated CC として使用 |
| `74`以下、`120`以上 | 無効（0） |

したがって、コメントに例示される `75`、`80`、`86`、`89` だけでなく範囲内の他の整数も受け付けます。たとえば `86junk` や `86.5` は `atoi` により 86 として扱われます。`+80` は80、`-80` は範囲外です。空白は `atoi` が整数の前に読み飛ばします。値の大文字小文字判定はありません。

`emulated_cc()` の関数内 `static const int` に変換結果を保存します。最初にこの関数が呼ばれた後でプロセス環境を変更しても再読込されません（`include/strata/core/emulate.hpp:14-24`）。

## 有効になる条件

この変数専用のビルドや GPU 世代チェックはありませんが、効果があるのは Strata が `emulated_cc()`、`cc_major_of()`、`cc_minor_of()`、`smem_optin_of()` を使う経路です。無効時はそれぞれ実 GPU から得た値を返します。

- Compute capability は `cc_major_of` / `cc_minor_of` が指定整数の十の位より上／一の位を返します。これにより CUDA のデバイス情報、SYCL のデバイス情報を使った Strata の経路選択と診断表示が変わります。
- shared-memory 上限は `smem_optin_of` が CC 75 なら 65,536 bytes、CC 80 なら 166,912 bytes、それ以外の有効値なら実 GPU の値を最大 101,376 bytes に制限して返します。無効時は実値のままです。
- 指定した世代のカーネルがビルドに含まれていることや、実 GPU がそのカーネルを実行できることを保証しません。たとえば SM 90+ の cluster kernel / PDL 経路は emulated CC が条件を満たしても、コンパイル済みカーネルの PTX / binary version 等も確認し、条件を満たさない場合はその経路を使いません（`src/kernels/cuda/qsa_select.cu:1238-1255`、`src/kernels/cuda/sampler.cu:1197-1228`、`src/kernels/cuda/verify_kernels.cu:1380-1403`）。
- HIP 向けコードには専用の実 GPU 世代分岐がある箇所があります。たとえば fused-GR の小タイル判定は HIP では GFX906 / その他の分岐を使いますが、共有メモリ値には `smem_optin_of` が適用されます。したがって全 backend の判定を一律に置き換えるものではありません（`src/kernels/cuda/fused_gr.cu:914-937`）。

## 実行時の詳細

代表的な読み取りと効果は次のとおりです。

- CUDA デバイス情報の組み立てでは compute capability と opt-in shared memory を置き換え、ggml CUDA 側に渡します。HIP の同じ箇所は AMD アーキテクチャ情報を使う別分岐です（`src/prefill/ggml_cuda_host.cu:74-99`）。
- CUDA の fused-GR 経路では、CC 75 判定により小さい tile を選び、shared-memory 容量から一度に処理する token 数を計算します。GDN chunked 経路では CC 8 以上かどうかと shared-memory 容量の条件に使われ、条件を満たさなければ `cudaErrorNotSupported` を返して別経路へ戻します（`src/kernels/cuda/fused_gr.cu:914-978`、`src/prefill/kernels.cu:1022-1043`）。
- QSA attention / prefill attention の kernel 選択や共有メモリ上限チェックにも使われます。値によって Turing / Ampere などを想定した経路が選ばれたり、必要容量を上限超過と判断してエラー終了したりします（`src/kernels/cuda/qsa.cu:657-691`、`src/kernels/cuda/qsa_prompt_attn.cu:1455-1482`）。
- CUDA SM 90+ cluster kernel と Programmatic Dependent Launch (PDL) の候補判定では、emulated CC だけでなく、該当するコードの PTX / binary version や runtime 条件も必要です。候補にならない場合は既存経路へ fallback します（上記の各判定箇所）。
- `strata generate` の GPU 情報ログでは、指定が有効なら compute capability の表示を置き換え、末尾に ` (STRATA_EMULATE_CC: a test mode, the card is emulated)` を付けます。指定自体が無効なら注記は付きません（`src/program/generate.cpp:4597-4599`、SYCL 側 `sycl/src/program/generate.cpp:4094-4105`）。

ヘッダーは CC 値の範囲を例として `75|80|86|89` と書きますが、実装は 75〜119 の全整数を通します。shared-memory 上限の分岐も 75 と 80 以外は一律 101,376 bytes 上限です。そのため、たとえば `90` を指定しても CC 90 としてのホスト側判定が行われる一方、shared-memory 値は実 GPU 値を 101,376 bytes までに制限する処理になります。これらの設定値は実 GPU の能力を変更せず、選ばれた経路の実行可否や性能を保証しません。

## 根拠

- 値の読み取り、`atoi`、受理範囲、CC と shared-memory 変換: `include/strata/core/emulate.hpp:14-34`
- CUDA デバイス情報への反映と HIP 分岐: `src/prefill/ggml_cuda_host.cu:74-103`
- fused-GR と GDN chunked の条件・容量計算: `src/kernels/cuda/fused_gr.cu:914-978`、`src/prefill/kernels.cu:1022-1043`
- QSA の上限チェックと compute-capability による attention 選択: `src/kernels/cuda/qsa.cu:657-691`、`src/kernels/cuda/qsa_prompt_attn.cu:1455-1482`
- SM 90+ cluster / PDL の追加条件: `src/kernels/cuda/qsa_select.cu:1238-1275`、`src/kernels/cuda/sampler.cu:1197-1235`、`src/kernels/cuda/verify_kernels.cu:1380-1403`
- CUDA と SYCL の診断表示: `src/program/generate.cpp:4597-4599`、`sycl/src/program/generate.cpp:4094-4105`

`docs/DETAILS.md` と `docs/` 内にはこの環境変数を説明する記述が見つからなかったため、性能値や実 GPU 上での一致性は独自に確認していません。
