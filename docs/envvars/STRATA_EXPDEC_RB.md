# `STRATA_EXPDEC_RB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

EXPDEC の gate/up CUDA カーネルが 1 ブロックで処理する出力行数を指定します。EXPDEC が実際に選ばれた場合、値が大きいほど 1 ブロックが担当する行数が増え、カーネル grid の x 方向のブロック数が変わります。down カーネル用の行数は別変数 `STRATA_EXPDEC_DRB` が担当します。

値の既定値は 0 で、自動決定を選びます。これは EXPDEC 自体を有効にするスイッチではありません。`STRATA_EXPDEC` が有効で、旧カーネルが無効、対象 layout が対応形式・形状である場合に限り gate/up の EXPDEC カーネルで使われます（`src/kernels/cuda/iq_kernels.cu:4060-4073,4085-4095,4151-4165`）。

## 値と判定

この値は `env_int_or("STRATA_EXPDEC_RB", 0)` で読み、helper は環境値が未設定または空文字なら既定値、それ以外なら `std::atoi` の結果を返します（`src/kernels/cuda/iq_kernels.cu:4055-4059,4071`）。文字列全体の検証やエラー報告はありません。

| 環境値 | 読み取られる値 | 行数の決定 |
|---|---:|---|
| 未設定 / 空文字 | 0 | 自動決定 |
| `0` または `-1` など 0 以下 | 0 以下 | 自動決定 |
| 正の整数 `N` | `atoi` が変換した整数 | `16 * R` の倍数へ切り上げ、対象行数を上限にする |
| `12tail` | 12 | `16 * R` の倍数へ切り上げ、対象行数を上限にする |
| 数字で始まらない文字列 | 0 | 自動決定 |

`atoi` のため、先頭空白や符号は通常の `atoi` 規則で扱われ、末尾の文字は検査されません。整数として表現できないほど大きい入力の結果は C/C++ の `atoi` の範囲外であり、このコードには安全な範囲検査がありません。文字列形式の不正を理由に Strata が警告したり終了したりする経路は見つかりませんでした。

正数 `N` は `ceil(N / (16 * R)) * (16 * R)` に丸められ、`2 * n_ff` を超える場合は `2 * n_ff` に制限されます。`R` は `STRATA_EXPDEC_R` から決まり、値が 2 の場合だけ 2、それ以外は 1 です。0 以下のときの自動決定は、初期値 `16 * R` から倍々に増やし、次の倍数へ増やすと `ceil(nrow / (2 * rb)) * max(cap_groups, 1)` が `STRATA_EXPDEC_MINBLK` 未満になる直前の行数を選びます（`src/kernels/cuda/iq_kernels.cu:4063,4085-4095,4102-4105`）。通常の既定 `STRATA_EXPDEC_MINBLK=800` は同ファイル `:4073` にあります。

## 有効になる条件

- カーネルのソースは `src/kernels/cuda/iq_kernels.cu` で、CMake の GPU backend 用 `strata_kernels` に含まれます（`CMakeLists.txt:412-425,456-506`）。HIP backend も `.cu` を HIP 言語として扱う設定です（`cmake/hip_backend.cmake:123-130`）。プロジェクトの EXPDEC 説明は CUDA の機能として記載しています（`docs/EXPERTDEC.md:1-4`）。CPU-only、Metal、SYCL の別実装によるこの環境変数の読み取りは見つかりませんでした。
- EXPDEC のモードが有効である必要があります。`STRATA_EXPDEC` は別の `env_on` 判定で、未設定・空文字・先頭文字が `0` の値では無効、先頭文字が `0` 以外なら有効です（`src/kernels/cuda/iq_kernels.cu:3395-3398,4060-4062`）。アーキテクチャ既定値などから API でモードを設定する経路もあります。
- `STRATA_OLD_IQ_MMVQ` が有効なら EXPDEC は使われず、既定の gate/up kernel に戻ります（`src/kernels/cuda/iq_kernels.cu:3399-3400,4151-4156,6410-6415`）。
- gate/up の形式は type 16、17、18、21、22 のいずれかで、`n_embd == 32 * 80`、`n_ff > 0` かつ 64 の倍数が必要です（`src/kernels/cuda/iq_kernels.cu:4077-4080`）。条件外では既定 kernel が使われます。
- `STRATA_EXPDEC_RB` は down 用には適用されません。down の EXPDEC は `STRATA_EXPDEC_DOWN` などの条件と対応する down layout を満たし、行数は `_DRB` を使います（`src/kernels/cuda/iq_kernels.cu:4070-4073,4081-4083,4185-4192`）。

コマンドライン引数や設定ファイルによる `STRATA_EXPDEC_RB` の上書きは見つかりませんでした。実装 API `native_expert_set_expdec_params()` は `gu_rows_per_block >= 0` なら内部値を上書きできますが、調査対象ソース中の呼び出しはベンチマーク専用 `src/kernels/expdec_bench.cpp` に限られ、通常実行経路からの呼び出しはありません（宣言・setter: `include/strata/kernels/iq_kernels.hpp:119-130`, `src/kernels/cuda/iq_kernels.cu:6218-6226`）。

## 実行時の詳細

環境値は `iq_kernels.cu` の namespace scope 初期化時に一度読み、`g_expdec_rb` に保持します（`src/kernels/cuda/iq_kernels.cu:4055-4059,4071`）。そのため、カーネルライブラリがロード・初期化された後に環境を変更しても再読み込みされません。前述の内部 setter は後から値を差し替えられます。

EXPDEC gate/up が選ばれると、`expdec_gu_r()` が `nrow = 2 * n_ff` と `rpp = 16 * R` から rows-per-block を計算し、grid の x 寸法を `ceil(nrow / rb)` にします。`expdec_note()` は対応形式ごとに初回、stderr に実際の `R`、`MINB`、rows-per-block、grid を出力します。非対応 layout で EXPDEC 判定まで到達した場合は `not covered: the default kernel runs` と記録します（`src/kernels/cuda/iq_kernels.cu:4102-4105,4123-4148,4151-4165`）。EXPDEC が無効、または旧カーネルが選ばれる場合はこのノート経路に入らず、呼び出し元が既定 kernel を起動します（同 `:4151-4156,6410-6415`）。

通常の実行経路では verifier の grouped expert 計算から `native_expert_grouped()` に到達します（`src/core/verify.cpp:2221-2236`）。この環境変数が変えるのはその GPU 計算内の gate/up kernel の行分割であり、モデル形式の対象外、別の grouped 実装、または gate/up を EXPDEC に切り替えない場合には値は使われません。

この環境変数の値そのものによるログ、エラー、終了経路はありません。記載した stderr ログは EXPDEC の layout 判定と実際の kernel 選択を示すもので、行数入力の検証結果ではありません。

## 根拠

- 全参照検索では、値を読む Strata 所有コードは `src/kernels/cuda/iq_kernels.cu:4071` の 1 箇所です。`env_int_or` の定義と変換は同 `:4055-4059`、値を使う行数計算は同 `:4085-4095,4102-4105` です。
- 対象 layout・実行条件・既定 kernel への fallback は同 `:4077-4083,4151-4165,6410-6415` にあります。
- `docs/EXPERTDEC.md:23-26` は `STRATA_EXPDEC_RB` / `_DRB` を「rows per block」、0 を `STRATA_EXPDEC_MINBLK` に基づく自動値として説明しています。現行ソースでも gate/up の自動値は `g_expdec_minblk`（既定 800）を使うため整合します。
- 候補一覧 `docs/envvars/000_envvers.md:774` に名前があります。コードでの読み取りを確認しました。
