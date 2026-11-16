# `STRATA_I8_N8`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

OWN-I8 の native expert int8 kernel が使う「N8」変種を選ぶ補助スイッチ。N8 は各スライスの entry 幅を16から8にし、tile 2〜4で各 thread が2 weight rowsを担当する実装である。値未設定時はtile 2だけでN8を使い、`1`系の値はtile 2〜4で使い、`0`系の値は使わない。これはタイルの内部変種を選ぶもので、OWN-I8自体を有効化しない。出力計算の各(row, entry)で加算する項と順序は同じとカーネルコメントに記載されている。`src/kernels/cuda/i8_expert.cuh:535-538`、`include/strata/kernels/i8_expert_rule.hpp:85-93`。

読み取りは `native_expert_i8` が `I8Args` を作る時点で行われ、その状態と選択済みtileから `a.n8` を決める。`i8_launch_tm` は `a.n8` に応じて同じ tile の `NR=true/false` kernel を起動する。tile 8用の別kernelはこのN8フラグを使わない。`src/kernels/cuda/iq_kernels.cu:6344-6373`、`src/kernels/cuda/i8_expert.cuh:1096-1107,1123-1144`。

## 値と判定

環境変数文字列は `std::getenv` で取得し、`i8_switch_parse` に渡す。helperは文字列全体を数値や真偽値としてparseせず、未設定または空文字なら `-1`、先頭文字が `'0'` なら `0`、それ以外の非空文字列なら `1` を返す。したがって大文字小文字・後続文字・数値としての妥当性は検査せず、先頭空白も除去しない。`src/kernels/cuda/iq_kernels.cu:6372-6373`、`include/strata/kernels/i8_expert_rule.hpp:28-31,89-93`。

| 条件 | unset | 有効になる値（N8を選ぶ） | 無効になる値（N8を選ばない） |
|---|---|---|---|
| tile 2〜4 | N8を選ぶ | `1`, `true`, `x`, ` 0` など、先頭文字が `0` 以外の非空文字列 | 空文字、`0`, `0anything`, `00` |
| tile 8 | N8なし | 該当なし | すべて（このtileに8-entry形式はない） |

上表の「有効」はN8変種の選択を示す。タイル2〜4で unset は `i8_n8_takes(-1, tile)` によりtile 2だけが有効、`1`状態は2〜4すべてで有効、`0`状態はすべて無効となる。値が `true` や空白で始まる文字列でも先頭文字が `'0'` でなければ `1` と判定される。`include/strata/kernels/i8_expert_rule.hpp:29-31,90-93`。

## 有効になる条件

- OWN-I8 の native expert int8 kernel が呼ばれる経路であること。通常の prompt 経路では `STRATA_EXPERT_I8` 等による経路選択が先にあり、融合・staged経路が選ぶ場合は OWN-I8 が選ばれない。`src/prefill/prefill.cpp:5966-5999`。
- 対象層が OWN-I8 の対応形式・形状・shared memory 条件を満たすこと。`native_expert_i8_supported` は対応型、nibble/tail/Hadamardの除外、次元・blobサイズ、および最小tileのshared memory条件を検査する。`src/kernels/cuda/iq_kernels.cu:6330-6333`。
- 実際に選ばれたtileが2〜4であること。`STRATA_I8_TM`、entry数、形状、shared memory上限でtileが決まり、tile 8ではN8形式を使わない。`src/kernels/cuda/iq_kernels.cu:6363-6373`、`src/kernels/cuda/i8_expert.cuh:1146-1157`。
- この変数はCUDA/HIP用の共有OWN-I8 kernel実装で参照される。OSやCLI引数による別判定はこの読み取り箇所にはない。`src/kernels/cuda/iq_kernels.cu:6372-6373`、`src/kernels/cuda/i8_expert.cuh:1126-1142`。

## 実行時の詳細

`native_expert_i8` 呼び出しごとに `getenv("STRATA_I8_N8")` を評価する。関数内staticへの保存はなく、プロセス実行中に環境値を変更した場合も、後続の呼び出しでは新しい値を読み得る。`I8Args::n8` はその呼び出しの両方のkernel launch（gate/up と down）で使われる。`src/kernels/cuda/iq_kernels.cu:6372-6373`、`src/kernels/cuda/i8_expert.cuh:1096-1107,1123-1144`。

tileは `STRATA_I8_TM` で指定されるか、平均entry数と形状から決まる。最終tileは2、3、4、または8に正規化され、tile 8は両weight typeがtile 8対応で形状条件も満たす場合だけ選ばれる。その後、shared memory上限を超えるtileは小さくされる。従って `STRATA_I8_N8=1` でも、tileが8なら効果はなく、tile 4等がshared memory制限で縮小された場合は縮小後のtileでN8判定される。`src/kernels/cuda/iq_kernels.cu:6363-6373`。

N8 kernelではスライス幅を8 entryとし、2 weight rowsを1 threadが担当する。ホスト側の `i8_launch_tm` が `a.n8` を見て `NR=true` または元の `NR=false` kernelを起動し、tile 8は専用 `i8b_kernel` を起動する。`src/kernels/cuda/i8_expert.cuh:535-538,1123-1157`。

## ログと測定値

`STRATA_I8_N8` の値、選択結果、または無効値に対する専用ログ・警告は、この読み取りと分岐にはない。カーネル起動後は通常の `check("native_expert_i8/gu")` と `check("native_expert_i8/down")` が呼ばれるが、これは本変数固有のログではない。`src/kernels/cuda/iq_kernels.cu:6372-6396`。

`include/strata/kernels/i8_expert_rule.hpp:85-88` のコメントはA4000、P100、R9700とFlash-Next形状のベンチマーク結果ファイルを参照し、tile 2/3での速度差を記録している。しかし、この調査対象ツリーには参照先の `par/RESULTS-I8-MMQOFF.md` がなく、詳細な測定条件を照合できないため、数値はここでは再掲しない。`docs/DETAILS.md` に本変数の説明は見つからなかった。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:6372-6373` — 実際の環境読み取りとtileからのN8判定。
- `include/strata/kernels/i8_expert_rule.hpp:28-31,85-93` — 文字列判定、既定値、tile別の規則。
- `src/kernels/cuda/i8_expert.cuh:535-538,1096-1107,1123-1157` — N8 kernelの役割とdispatch。
- `src/prefill/prefill.cpp:5966-5999` — OWN-I8 prompt経路の選択条件。
- `src/kernels/cuda/iq_kernels.cu:6330-6333,6363-6373` — 対応条件とtile選択。
