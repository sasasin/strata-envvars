# `STRATA_VIT_CPU_QB`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

自前 CPU Vision Tower (`VitCpu`) の attention 計算で、1 task がまとめて処理する query 行数 `QB` を指定する診断用設定です。未指定時の既定値は 96 行です。query のグループ分け、task 数、attention 用 scratch 領域の大きさを変えます。attention 内では QK、softmax、PV の計算を同じ順序で行い、ソースコメントはこのグループ分けによって結果は bit-identical と説明しています。`vit_cpu.cpp` の CPU 実装だけが参照し、GPU 実装や `VitRef` の計算を直接変更しません（`tools/vision/own/vit_cpu.cpp:289-296,332-363`; GPU/CPU reader の分岐は `tools/vision/own/own_reader.cpp:128-149`）。

## 値と判定

`std::getenv` で取得した文字列を `std::atoi` に渡し、整数 `v` が 48 以上かつ 48 の倍数なら採用し、それ以外は 96 に戻します。未設定時は `v=0` となり既定値です。空文字、数値に変換できない文字列、`0`、`47`、`49`、負数も 96 に戻ります。`atoi` が数値として読める先頭部分だけを変換するため、`48tail` や ` 48` は 48 として採用され、`96junk` は 96 として採用されます。先頭が数値でない `true` / `false` は 0 となり既定値です。大文字小文字の比較はありません。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `VitCpu::encode` の attention | 96 | `48`, `96`, `144`, `48tail` | 空文字, `0`, `47`, `49`, `-48`, `true` |

判定は `tools/vision/own/vit_cpu.cpp:16-18,293` にあります。数値変換後の範囲検査は下限と 48 での剰余だけで、上限 clamp はありません。従って実装上は `atoi` の `int` 変換可能範囲内にある正の 48 の倍数を受け付けます。

## 有効になる条件

- 自前の CPU Vision Tower が選ばれ、`VitCpu::encode` が実行されること。`strata-vision` は `--tower own` で明示選択でき、`auto` では読み込み可能な場合に自前 tower を選びます（`tools/vision/strata_vision.cpp:137-145,161-170`; `tools/vision/own/own_reader.cpp:49-82,128-149`）。
- CPU 経路であること。`--gpu` の自前経路は `VitGpu::encode` を呼び、`STRATA_VIT_CPU_QB` の読み取り箇所には到達しません（`tools/vision/own/own_reader.cpp:114-128,143-149`）。
- CPU 自前 tower の通常経路であること。別の `STRATA_VIT_CPU=ref` を設定すると `VitRef` が選ばれ、この変数は使われません（`tools/vision/own/own_reader.cpp:128-137`）。
- CMake で `vit_cpu.cpp` を含む `strata_vit_own` がビルドされていること。製品用 `strata-vision` はこのライブラリをリンクし、`tools/vision/own` を追加します。単独の `strata-vision-own` も同じライブラリをリンクします（`tools/vision/CMakeLists.txt:128,166-167`; `tools/vision/own/CMakeLists.txt:74-75,168-169`）。
- `--tower`, `--threads`, `--max-tokens` には `QB` を上書きする指定はありません。これらの引数は reader 選択やスレッド数・画像 token 上限に使われ、`QB` は別に環境から読まれます（`tools/vision/strata_vision.cpp:101-128,161-170`; `tools/vision/own/vit_cpu.cpp:293-296`）。

## 実行時の詳細

値は `VitCpu::encode` 内の関数ローカル `static const int` として初回に一度だけ評価されます。同じプロセスで後から環境を変更しても再評価されません。reader 起動後、CPU tower の画像 encoding が初めて行われるときに初期化されます（`tools/vision/own/vit_cpu.cpp:194-203,293`）。

採用した `QB` から query task 数を `ceil(N / QB)` とし、head ごとに query 行ブロックを分担します。各ブロックの処理行数は末尾で `N` に合わせます。scratch は thread ごとに `QB` に比例する領域を確保し、各 task は query 行ブロックごとに全 key tile を走査して QK、online softmax 更新、PV を実行します（`tools/vision/own/vit_cpu.cpp:294-296,332-363`）。その後、得られた context は既存の出力 projection・merger に渡され、reader は embedding rows を出力します（`tools/vision/own/vit_cpu.cpp:364-395`; `tools/vision/own/own_reader.cpp:190-203`）。

この値に固有のエラー、警告、fallback 分岐はありません。値が条件を満たさない場合は既定値 96 で計算を続けます。CLI 引数による優先順位設定もありません。

## ログと測定値

この変数を読み取ったことや、採用値 `QB` を表示する専用ログはありません。`STRATA_VIT_PROF` が設定されている場合は stderr に `vit-cpu-prof ... attention ... (%d tasks: QK ..., softmax ..., PV ...)` の計測行が出ますが、`QB` の値そのものは表示しません（`tools/vision/own/vit_cpu.cpp:204-205,398-401`）。ソースコメントには `QB` が 48 の倍数という診断条件の記載がありますが、比較可能な実測は `QB` ごとに示されていません。本 checkout に `RESULTS-OWN-3V.md` はなく、ここでは性能値を記載しません。

## 根拠

- 読み取り、既定値と条件: `tools/vision/own/vit_cpu.cpp:16-18,289-296`
- attention の task 分割、scratch、計算: `tools/vision/own/vit_cpu.cpp:332-363`
- CPU tower / reference / GPU の選択: `tools/vision/own/own_reader.cpp:114-149`
- `strata-vision` の自前 tower 選択と実行: `tools/vision/strata_vision.cpp:137-175`
- ライブラリと実行ファイルへの組み込み: `tools/vision/CMakeLists.txt:128,166-167`; `tools/vision/own/CMakeLists.txt:74-75,168-169`
- profiler の出力: `tools/vision/own/vit_cpu.cpp:398-401`
