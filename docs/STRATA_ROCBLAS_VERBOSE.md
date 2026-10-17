# `STRATA_ROCBLAS_VERBOSE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の prefill GEMM において、rocBLAS tuning table を使う経路の診断ログを有効にします。各 GEMM shape に選ばれた solution、solution が拒否されたときの fallback、state 破棄時の `tuned_launches` / `fallbacks` 集計を stderr に出します。この変数自体は tuning table の選択や GEMM の計算経路を切り替えず、ログだけを制御します。

## 値と判定

コードは数値や文字列を parse せず、`std::getenv("STRATA_ROCBLAS_VERBOSE")` が null かどうかだけを判定します。

| 値 | 判定 |
|---|---|
| 未設定 | verbose ログを出さない |
| 空文字を含む設定済みの値 | verbose ログを出す |
| その他の任意の文字列（`0`、`false` を含む） | verbose ログを出す |

環境変数は state destructor および shape の初回選択・fallback のログ箇所で参照されます。値を static cache する処理はなく、各参照時のプロセス環境が使われます。

## 有効になる条件

- `src/prefill/gemm.cu` が HIP コンパイラでコンパイルされ、`STRATA_ROCBLAS_AVAILABLE` が定義されたビルドでのみ、この変数を読む rocBLAS tuning 経路がコンパイルされます。
- tuning の実行には別途 `STRATA_ROCBLAS_TUNING` が空でないパスに設定され、有効な tuning table のロードに成功している必要があります。未設定または空なら `create_rocblas_state()` は null を返し、table を使う GEMM 呼び出しは default kernel に進みます。
- 値が設定済みでも、変数によって通常の cuBLAS/HIP GEMM のログが一律に詳細化されるわけではありません。ログ対象は rocBLAS table 経路の診断です。

## 実行時の詳細

`Gemm::init()` と `Gemm::init_external()` は、HIP と `STRATA_ROCBLAS_AVAILABLE` の条件下で `create_rocblas_state()` を呼びます。table がロードされると tuning 有効化の要約は常に stderr に出ます。`STRATA_ROCBLAS_VERBOSE` が設定されている場合、各 shape の初回選択時に solution 番号または default kernel 選択理由を出し、rocBLAS が solution を拒否したときも通常は詳細を出します。拒否が同じ shape で3回に達した場合は default kernel に固定する警告が、この変数に関わらず出ます。

rocBLAS の呼び出しが成功すれば `tuned_launches` を増やします。呼び出しが拒否されたときは当該呼び出しで default kernel に fallback し、同じ shape で拒否が3回に達すると以後その shape は default kernel を使います。これらは `STRATA_ROCBLAS_VERBOSE` の効果ではなく、tuning table 実行経路自体の動作です。state の破棄時、verbose が設定されていれば累計 `tuned_launches` と `fallbacks` を stderr に出します。

## 根拠

- `src/prefill/gemm.cu:403-420`: HIP / `STRATA_ROCBLAS_AVAILABLE` のコンパイル条件、state destructor の集計ログ。
- `src/prefill/gemm.cu:424-478`: table パスの読み込み、失敗時の default kernel 継続、および初期化ログ。
- `src/prefill/gemm.cu:483-530`: shape 選択と verbose 診断、拒否時の fallback と3回後の固定。
- `src/prefill/gemm.cu:583-605,622-645`: 通常・外部初期化から rocBLAS state を作る呼び出し。
- `src/prefill/gemm.cu:1202-1213`: `f16_inplace()` が tuning 呼び出しに成功しなければ default の `cublasGemmEx` に進む。
- `docs/AMD_HIP.md:814-839`: rocBLAS table の用途、verbose ログ、および測定・smoke test の説明。ここに記載された性能値は資料上の測定であり、本調査で再測定していません。
