# `STRATA_EXPDEC_DR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

EXPDEC の down projection kernel で、lane あたりに処理させる出力行数 `R` を選びます。これは EXPDEC の有効化スイッチではありません。down projection の EXPDEC は別変数 `STRATA_EXPDEC_DOWN` が有効な場合に限って候補になります。`R` が大きいほど kernel 内の1回の pass が扱う行数が増え、行列の分割と起動 grid に影響します。

## 値と判定

環境値は `env_int_or()` が `std::atoi()` で読みます。未設定または空文字なら既定値 `4` です。空白や符号を含む文字列も `atoi` の規則で変換され、数値の後ろに続く文字列は検証されません。変換後の値が厳密に `1` または `2` の場合だけその値を使い、それ以外は `4` にします。

| 環境値の例 | `atoi` の結果 | 採用される `R` |
|---|---:|---:|
| 未設定、空文字 | 既定値 `4` | 4 |
| `1`, `1xyz` | 1 | 1 |
| `2`, `2xyz` | 2 | 2 |
| `0`, `3`, `-1`, `xyz` | それぞれ 0, 3, -1, 0 | 4 |

したがって `1foo` と `2foo` は有効値として扱われます。`1.5` は `atoi` が先頭の整数部分 `1` を返すため `R=1` です。数値として読み取れない文字列は `atoi` が `0` を返すので `R=4` になります。実装は値域エラーを報告せず、一般的な数値構文として文字列全体を検査する処理もありません。

## 有効になる条件

`R` が実際に選択されるのは、grouped native expert の down projection が EXPDEC kernel に進んだときです。まず `STRATA_EXPDEC` が有効であり、`STRATA_OLD_IQ_MMVQ` による旧 kernel 選択が無効でなければなりません。さらに `STRATA_EXPDEC_DOWN` が有効で、layout が対応する型・形状である必要があります: down type `42`（Q2_0）、または `STRATA_EXPDEC_D20` も有効な場合の type `20`（IQ4_NL）、`n_ff == 32 * ED_HB`、`n_embd` が正で128の倍数です。条件を満たさない場合は通常の down kernel が使われるため、`STRATA_EXPDEC_DR` は適用されません。

`STRATA_EXPDEC_DOWN` の既定値は `0` なので、`STRATA_EXPDEC_DR` だけ設定しても down の EXPDEC は有効になりません。旧 IQ MMVQ kernel が選ばれているときも EXPDEC down は使われません。

`docs/EXPERTDEC.md` は EXPDEC を CUDA only と記載しています。この文書もその説明範囲に従います。実装ファイルは HIP gfx906 build でもコンパイル対象になりますが、backend ごとの全 layout でこの kernel が使われるかはこの変数単独の条件からは断定しません。

## 実行時の詳細

`g_expdec_dr` は `iq_kernels.cu` のグローバル初期化時に環境から読み込まれます。したがって通常はプロセス起動時の環境値が使われ、起動後に環境を変更してもこの値は読み直されません。

`expdec_dr()` は読み込んだ値を `1`、`2`、または `4` に正規化します。down kernel の dispatch はこの値でテンプレート実装 `R=1/2/4` を選びます。1 pass あたりの行数は `R * (256 / LANES)` で、`LANES` は IQ4_NL (type 20) なら8、それ以外の対応 down type なら16です。`STRATA_EXPDEC_DRB` が正数なら rows-per-block を別途指定し、0以下なら自動計算しますが、これはこの変数とは別の設定です。

`native_expert_set_expdec_params()` が `down_rows_per_lane > 0` を受け取ると、実行中の内部値を上書きできます。その後も最終選択は同じ正規化を通るので、API 経由で1/2以外が渡された場合は4になります。現 HEAD の Strata 所有コードでこの setter を呼ぶのは `expdec_bench` です。エンジン側では環境由来の設定が使われます。環境または設定 API の値が選択された場合、EXPDEC が初めて対応レイアウトに遭遇すると stderr に `strata expdec: CUDA%d down type ... expdec_down_kernel R ...` の行が出て、採用された `R` と block/grid 情報が記録されます。非対応 layout では `... not covered: the default kernel runs` の診断行が出ます。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3934-3953` — `env_int_or()` の `getenv` / `atoi`、既定値4、1/2/4への正規化。
- `src/kernels/cuda/iq_kernels.cu:3959-3961,4063-4070` — down EXPDEC の有効条件、通常 kernel への fallback 判定と対応 type ごとの dispatch。
- `src/kernels/cuda/iq_kernels.cu:4045-4061` — lane 数、rows-per-pass、R別 kernel 呼び出し。
- `src/kernels/cuda/iq_kernels.cu:4021-4025` — 実際の R と grid を含む診断ログ。
- `src/kernels/cuda/iq_kernels.cu:5022-5042` — `NativeExpertExpdecParams` による実行時上書きと設定値取得。
- `include/strata/kernels/iq_kernels.hpp:108-120` — パラメータ API のフィールド説明。
- `src/kernels/expdec_bench.cpp:104-107,383-385` — 現 HEAD でパラメータ setter を使う同梱ベンチマーク。
- `docs/EXPERTDEC.md:16-26,32-42` — EXPDEC の対象、DR の既定値と関連ノブ、down の別 opt-in 条件の説明。ソースの down 条件および既定値と一致する。
- `CMakeLists.txt:2208-2235` — HIP gfx906 build では `src/*.cu` を HIP としてコンパイルする。EXPDEC の文書上の CUDA only という適用範囲と、ソースファイルの build 対象を区別するための根拠。
