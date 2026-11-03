# `CARDS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`CARDS` は、Linux 向けの分割エンジンをビルドする `packaging/build_split_cuda.sh` と `packaging/build_split_hip.sh` が、生成する `strata-split-N` のカード数 `N` を選ぶためのビルド時環境変数です。Strata の実行時エンジンやサーバーが `CARDS` を読む箇所は見つかりませんでした。各スクリプトは値を CMake の `STRATA_SPLIT_CARDS` に渡し、その値ごとに Ninja で対応するターゲットをビルドします（`packaging/build_split_cuda.sh:18-28`, `packaging/build_split_hip.sh:23,30-37`, `src/split/CMakeLists.txt:92-103`）。

## 値と判定

| スクリプト | 未設定または空文字 | 設定時の扱い |
|---|---|---|
| CUDA | `2` | 文字列中の ASCII 空白を `;` に置き換えて `STRATA_SPLIT_CARDS` に渡し、元の値をシェルの `for` で語分割して各ターゲットを指定します。 |
| HIP | `2 3 4` | CUDA と同じ変換・ターゲット選択です。 |

どちらも `${CARDS:-既定値}` を使うため、未設定だけでなく空文字でも既定値になります。既定値以外の値は数値としてシェル側で変換されません。CMake は `STRATA_SPLIT_CARDS` の各要素が `2`, `3`, `4` のいずれかに完全一致するかを検査し、それ以外なら `STRATA_SPLIT_CARDS: 2, 3 or 4, not <値>` の fatal error で構成を失敗させます（`src/split/CMakeLists.txt:92-95`）。たとえば `CARDS="2 4"` は CMake に `2;4` を渡し、2 と 4 のターゲットを要求します。スクリプトの記述例もカード数を空白区切りで指定しています（`packaging/build_split_cuda.sh:6-9`, `packaging/build_split_hip.sh:10`）。

## 有効になる条件

この変数が使われるのは、該当するビルドスクリプトを実行したときだけです。CUDA スクリプトは Linux CUDA 構成を、HIP スクリプトは Linux HIP 構成をそれぞれ CMake に指定します。CMake 側では分割エンジンが有効であり、対応する Linux backend と llama.cpp の `ggml-cuda/vecdotq.cuh` がある `STRATA_GGML_DIR` が必要です。条件を満たさなければ `src/split/CMakeLists.txt:20-30` の backend 分岐または警告の後に分割エンジン構成をスキップし、`CARDS` の値からターゲットは作られません。

スクリプトは CMake を呼ぶ前に対象 build directory の `CMakeCache.txt` を削除してから `-DSTRATA_SPLIT_CARDS=...` を明示します。そのため、既存 CMake cache の値より今回の `CARDS`（または空・未設定時のスクリプト既定値）が使われます（`packaging/build_split_cuda.sh:18-23`, `packaging/build_split_hip.sh:23-31`）。この変数は CLI 引数や別の実行時環境変数とは連動しません。

## 実行時の詳細

値はスクリプト実行時に通常のシェル変数展開で読み取られ、プロセス内に cache されません。スクリプトは CMake にカード数リストを渡した後、`CARDS` の各空白区切り項目に対応する `strata-split-N` ターゲットを順に Ninja でビルドします。実行ファイルが見つからない・実行可能でない場合、CUDA では `build_split_cuda.sh: no strata-split-N`、HIP では `build_split_hip.sh: no strata-split-N` を stderr に出して終了コード 1 で終了します（`packaging/build_split_cuda.sh:27-30`, `packaging/build_split_hip.sh:36-39`）。正常時は生成した実行ファイルのパスを1行ずつ最後に stdout へ出します（同 CUDA `:36-38`, HIP `:56-60`）。

ここでビルドされた `strata-split-N` は、カード数 `N` を compile definition `FNX_NCARD` に埋め込んで作られます（`src/split/CMakeLists.txt:96-103,111-114`）。したがって、`CARDS` はビルド成果物の種類を変えるもので、起動済みの Strata プロセスのカード選択を変更する設定ではありません。

## 根拠

- `packaging/build_split_cuda.sh:18-28` — CUDA の既定値、CMake への値の受け渡し、カード数ごとのターゲット指定。
- `packaging/build_split_hip.sh:23-37` — HIP の既定値、CMake への値の受け渡し、カード数ごとのターゲット指定。
- `src/split/CMakeLists.txt:13-16,20-30,92-103` — CMake 側の設定既定値、backend/依存条件、受理するカード数、ターゲットと `FNX_NCARD`。
- `docs/SPLIT_ENGINE.md:79-82` — ビルド資料。実装上の判定は上記スクリプトと CMakeLists を根拠としています。
