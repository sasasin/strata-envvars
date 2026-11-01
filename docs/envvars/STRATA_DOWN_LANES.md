# `STRATA_DOWN_LANES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL の grouped expert down kernel で、1 行の計算を担当する lane 数を選びます。対象ファイル内の `native_down_kernel` は 256 work-item の work-group を `256 / lanes` 行に分けるため、この値は行あたりの並列度と work-group 内の行数を決めます。Strata はこの値をモデルや他の backend 全般には適用せず、SYCL の `native_expert_grouped` が lane kernel を起動する経路で使います。

## 値と判定

環境変数の文字列を `std::atoi` で整数に変換し、結果が `4`, `8`, `16`, `32` のときだけ採用します。それ以外は compile-time の `kExpertLanes` に戻ります。`atoi` のため文字列全体の厳密な検証はなく、先頭の空白や符号を許し、数値の後ろにある非数値部分を無視します（例: `" 16tail"` は `16`）。`""`, `"0"`, 負数、数値で始まらない文字列は有効値になりません。

| 環境値 | 判定結果 |
|---|---|
| 未設定 | `kExpertLanes` |
| 空文字 | `atoi` が `0` を返すため `kExpertLanes` |
| `4`, `8`, `16`, `32`（または `atoi` が同じ値を返す文字列） | その値 |
| その他の値 | `kExpertLanes` |

`kExpertLanes` は `STRATA_EXPERT_LANES` の compile-time 値で、マクロ未定義時は `8` です。ビルド時にマクロを上書きしている場合は、その値が fallback になります。dispatch の switch は `4`, `16`, `32` を個別に選び、それ以外を 8-lane kernel に割り当てます。

## 有効になる条件

- SYCL build の grouped native expert 経路であること。通常の CUDA/HIP 実装や別 backend がこの読み取り箇所を共有している証拠はありません。
- モデルの expert layout が native 経路として選ばれ、`native_expert_grouped` に到達すること。SYCL の生成処理は各 layer の形式を `native_expert_supported` で事前確認します。
- down kernel が起動し、かつその format / runtime 分岐が `launch_down_lanes` を使うこと。`kSplit<TD>` の format で `STRATA_EXPERT_SPLIT` が有効、かつ `STRATA_OLD_IQ_MMVQ` が無効なら multi-entry down kernel に進み、この変数は読まれません。split 形式でも旧 kernel が有効なら lane kernel が使われます。

`STRATA_DOWN_LANES` 自体に OS、CLI、モデル状態による値の上書きはありません。kernel 経路がこの値を使わない場合には、設定値が有効でも動作への効果はありません。

## 実行時の詳細

`down_lanes()` は `static const int` に結果を保存し、`launch_down_lanes()` から選択時に初期化します。したがって、最初の該当 dispatch で環境を読み、その後の dispatch では同じプロセス内の cache 値を使います。プロセス起動後に環境を書き換えても、初回評価後の値は変わりません。プロセス起動時に別のコードが先にこの関数を呼ぶわけではなく、`native_expert_grouped` の down 処理から lane kernel に進んだ時点が読み取り契機です。

採用値に応じて `down_port_km<TD, LN>` が `LN=4/8/16/32` の kernel を起動します。down kernel は各 work-item の lane ID を `LN` で分け、`256 / LN` 個の行を処理します。環境値の parse や選択について専用ログ、警告、エラー出力はありません。無効値は既定値へ fallback し、値自体を理由に終了・失敗する経路もありません。kernel 起動後の SYCL エラー処理は `native_expert_grouped/down` の共通 `check()` 経路です。

この変数は down の lane kernel 選択だけを変えます。Strata のコードから性能差や数値結果の同一性を一般化できる測定根拠は確認できません。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:712`。
- SYCL grouped expert 用の compile-time 既定値: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:887-894`。
- `atoi`、許容値検査、`down_lanes()` の static cache: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4487-4496`。
- lane 数に応じた kernel の dispatch と fallback 先: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4560-4569`。
- down kernel の launch path。split format の場合に multi-entry kernel を選ぶ条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4622-4634`。
- grouped native expert の down format dispatch と終了後の `check`: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5761-5795`。
- down kernel 内で `LN` が行数と lane ID の分割に使われる箇所: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2330-2345`。
- split kernel と runtime selector の定義: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:959-964,1018,1050,1087,1126,1171,1219,1244,1272,1309-1311,3200-3210`。
- SYCL 生成処理が native expert 対応形式を事前確認する箇所: `sycl/src/program/generate.cpp:2664-2676`。
- grouped expert を native layout で起動する server-side expert 経路: `sycl/src/core/remote_experts.cpp:431-442`。
