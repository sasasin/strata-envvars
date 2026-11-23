# `CARDS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`CARDS` は Strata の通常起動時に読む設定ではなく、同梱の `tools/packaging/build_split_cuda.sh` と `tools/packaging/build_split_hip.sh` が、カード数ごとの `strata-split-N` 実行ファイルをどの `N` でビルドするか決めるビルド時入力である。両スクリプトは値を `STRATA_SPLIT_CARDS` として CMake に渡し、CMake は各値をターゲット名 `strata-split-N` とコンパイル定義 `FNX_NCARD=N` に使う。したがって選ばれるカード数の構成を変えるが、Strata 起動後の GPU 選択や実行時のカード数を直接指定するものではない。`terminal/strata_control/split_engine.py` の自動選択条件や起動時の `--split-engine` とは別の層である。同ランチャーはモード、AMD のカード数・architecture・expert type などで実行経路を判定する（`terminal/strata_control/split_engine.py:436-466`）。ビルド時の根拠は `tools/packaging/build_split_cuda.sh:19,23-29`、`tools/packaging/build_split_hip.sh:24,31-38`、`engine/src/split/CMakeLists.txt:116-126,138-140`。

## 値と判定

| ビルドスクリプト | 未設定 | 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|---|
| `build_split_cuda.sh` | `2` | `2`（`${CARDS:-2}` が未設定と null/空の両方を既定扱い） | `2`、`3`、`4`。複数は空白区切り（例: `2 3`） | CMake に渡されたリスト要素が `2`・`3`・`4` 以外なら構成時に失敗。例: `0`、`1`、`true`、`false`、`0anything` |
| `build_split_hip.sh` | `2 3 4` | `2 3 4`（`${CARDS:-2 3 4}` が未設定と null/空の両方を既定扱い） | `2`、`3`、`4`。複数は空白区切り（既定値は3種類すべて） | CMake に渡されたリスト要素が `2`・`3`・`4` 以外なら構成時に失敗。例: `0`、`1`、`true`、`false`、`0anything` |

両スクリプトとも文字列を数値として parse するのではない。CMake 引数を作るときに値中の ASCII 空白をセミコロンへ置換し、そのリストの各要素を正規表現 `^[234]$` と照合する。前後空白の trim、大小文字変換、真偽値変換、数値としての範囲丸めはない。従って `2x` は受理値にならない。区切りにした ASCII 空白は CMake 側の複数要素になる。スクリプトの後段では元の値を未引用の `for n in $CARDS` でも展開しており、空白で分割された各値について Ninja のターゲットを要求する（`tools/packaging/build_split_cuda.sh:19,24,28-29`、`tools/packaging/build_split_hip.sh:24,32,37-38`、`engine/src/split/CMakeLists.txt:116-120`）。

## 有効になる条件

- 対象は CUDA 用または HIP 用の `tools/packaging/build_split_*.sh` によるビルドである。CUDA スクリプトは `B` と `CUDA`、HIP スクリプトは `B` と `HP` の指定を要求する。各スクリプトが `STRATA_BUILD_SPLIT=ON` と対応 backend を指定して CMake を起動する（`tools/packaging/build_split_cuda.sh:13-24`、`tools/packaging/build_split_hip.sh:18-32`）。
- CMake の split 構成がプラットフォーム/backend 条件を通過する必要がある。HIP は CUDA が無効で Apple 以外のとき HIP 経路となり、CUDA は Linux CUDA 経路が必要。条件不一致や必要ヘッダー欠落などでは CMake が split をスキップして早期 return するため、後段のカード数リスト処理には進まない（`engine/src/split/CMakeLists.txt:20-34`）。
- リストの各要素が `2`、`3`、`4` のいずれかでなければ CMake は `FATAL_ERROR` を出して構成を失敗させる。受理された要素ごとに `strata-split-N` ターゲットを追加し、`FNX_NCARD=N` をコンパイル定義にする（`engine/src/split/CMakeLists.txt:116-126,138-140`）。
- この変数はビルド時のみ参照される。実行時 CLI、モデル状態、GPU 台数、他の実行時環境変数によって `CARDS` が読み直されたり上書きされたりするコードは見つからない。どのビルド済みエンジンを起動するか、また実機構成で split を使うかは別のランチャー条件で決まる。

## 実行時の詳細

シェルスクリプト開始時に `${CARDS:-既定値}` で値を展開し、同じ値を CMake の `-DSTRATA_SPLIT_CARDS=...` と後段のビルドループに使う。CUDA は未設定時 `2`、HIP は未設定時 `2 3 4` であり、どちらも明示的な空文字は既定値と同じ扱いになる（`tools/packaging/build_split_cuda.sh:19,23-29`、`tools/packaging/build_split_hip.sh:24,31-38`）。CMake はカード数ごとのターゲットを作り、スクリプトはその各ターゲットを `ninja` でビルドする。HIP は生成された各実行ファイルを `strata-split-N-amd` にコピーして出力し、CUDA は生成ファイルのパスを出力する（`engine/src/split/CMakeLists.txt:116-126,138-140`、`tools/packaging/build_split_hip.sh:37-60`、`tools/packaging/build_split_cuda.sh:28-39`）。

読み取りはスクリプト実行時のシェル展開で、プロセス起動後に親環境の値を変えて反映させる経路や、子プロセスで `CARDS` を読み直す経路はない。CMake へは変換済みの `STRATA_SPLIT_CARDS` が渡される。

## ログと測定値

無効なカード数要素では CMake が `STRATA_SPLIT_CARDS: 2, 3 or 4, not <要素>` の形式で `FATAL_ERROR` を出す（`engine/src/split/CMakeLists.txt:116-119`）。有効値ごとにスクリプトは対応する `strata-split-N` をビルドする。対象ファイルに `CARDS` の値を表示する専用ログや測定値はない。ビルド後の検査が失敗する場合、HIP は `build_split_hip.sh:40-54` の診断を stderr に出して終了し、CUDA は実行ファイル欠落時 `build_split_cuda.sh:31`、peer 関数検出時 `build_split_cuda.sh:33-35` の診断を出して終了する。これらはビルド成果物検査であり、値 `CARDS` 自体の別解釈ではない。

## 根拠

- `tools/packaging/build_split_cuda.sh:6-10,18-29,31-39` — CUDA ビルド用入力の既定値、CMake への転送、ターゲットごとのビルド。
- `tools/packaging/build_split_hip.sh:10-16,24-38,40-60` — HIP ビルド用入力の既定値、CMake への転送、ターゲットごとのビルドと成果物検査。
- `engine/src/split/CMakeLists.txt:20-34,116-140` — 条件による早期スキップ、カード数の許容値、ターゲットと `FNX_NCARD` の設定。
- `docs/SPLIT_ENGINE.md:92-95` — ビルド時の `STRATA_SPLIT_CARDS` とスクリプトの位置。挙動の根拠は上記ソースコード。
