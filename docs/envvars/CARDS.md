# `CARDS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`CARDS` は通常実行時の設定ではなく、分割エンジン `strata-split-N` を何枚の GPU 向けにビルドするかを、Linux 向け CUDA/HIP packaging スクリプトに渡すビルド時入力である。CUDA スクリプトの既定は `2`、HIP スクリプトの既定は `2 3 4`。スクリプトは値を CMake の `STRATA_SPLIT_CARDS` に渡し、その数ごとに `strata-split-N` ターゲットをビルドする。`src/split/CMakeLists.txt` は各ターゲットに `FNX_NCARD=N` を定義するため、値は生成される別個の実行ファイルとそのカード分割構成に反映される（`packaging/build_split_cuda.sh:19-29`、`packaging/build_split_hip.sh:24-38`、`src/split/CMakeLists.txt:107-120,129-144`）。

`CARDS` を読む Strata 所有コードはこの2スクリプトであり、通常の CLI、サーバー、ビルド済みエンジンの実行時読み取りは見つからない。したがって実行中のプロセスから値を変更しても動作は変わらず、値はビルドした実行ファイルに固定される。Strata のトップレベル CMake では `STRATA_BUILD_SPLIT` は既定 OFF で、ON のときだけ `src/split` を追加する（`CMakeLists.txt:794-799`）。

## 値と判定

両スクリプトとも Bash の `${CARDS:-既定値}` を使うため、変数が未設定または空文字ならスクリプトごとの既定値に置き換わる。空白区切りの各値は、CMake に渡すときに各リテラル空白を `;` に置換し、ビルド対象を選ぶ `for n in $CARDS` ではシェルの単語分割で列挙する。値自体を数値として parse する処理はスクリプトにはない（`packaging/build_split_cuda.sh:19,24,28-29`、`packaging/build_split_hip.sh:24,32,37-38`）。

| ビルド経路 | 未設定 | 設定時に有効になる値 | 無効値・扱い |
|---|---|---|---|
| CUDA (`packaging/build_split_cuda.sh`) | `2` | `2`、`3`、`4`。複数指定例は `CARDS="2 3"` | CMake が各要素を検査し、`2`、`3`、`4` 以外（例: `1`、`5`、`2x`）で configure を `FATAL_ERROR` にする。 |
| HIP (`packaging/build_split_hip.sh`) | `2 3 4` | `2`、`3`、`4`。複数指定例は `CARDS="2 4"` | CUDA と同じ CMake 検査で configure が失敗する。 |

両経路で明示的な空文字も未設定と同じ既定値になる。大文字小文字の扱いや数値文字列の変換規則はなく、CMake の正規表現 `^[234]$` に各セミコロン区切り要素が完全一致するかで有効性を判定する。そのため `02` や `2x` のような余分な文字を含む要素は受理されない（`src/split/CMakeLists.txt:107-110`）。スクリプトの置換は ASCII 空白だけをセミコロンに変える。セミコロン区切り値は CMake の検査を通る場合がある一方、後段の `for n in $CARDS` はセミコロンを単語区切りにしないため、Ninja に複数カード数を個別ターゲットとして渡せず、生成物チェックまで進まない。通常は記載例どおり空白区切りの `2 3 4` を使う（`packaging/build_split_cuda.sh:24,28-32`、`packaging/build_split_hip.sh:32,37-40`）。

## 有効になる条件

- 2つの読み取り箇所は packaging 用の CUDA/HIP ビルドスクリプトに限られる。CUDA スクリプトでは `B` と `CUDA`、HIP スクリプトでは `B` と `HP` も必須で、未指定なら各スクリプトは `set -eu` と必須変数展開によって処理を止める（`packaging/build_split_cuda.sh:12-20`、`packaging/build_split_hip.sh:17-25`）。
- 分割エンジン自体を生成するには `STRATA_BUILD_SPLIT=ON` が必要。CMake は Linux の CUDA または HIP 構成以外では分割ターゲットをスキップし、量子化ヘッダーが欠ける場合もスキップする（`CMakeLists.txt:794-799`、`src/split/CMakeLists.txt:20-34`）。
- HIP 経路は `STRATA_ENABLE_HIP` が ON かつ `STRATA_ENABLE_CUDA` が OFF のときだけ HIP 分岐に入る。指定された HIP アーキテクチャが許可リスト外の場合も分割ターゲットはスキップされる（`src/split/CMakeLists.txt:20-27,43-57`）。
- `CARDS` は利用可能 GPU の選択や実行時 fallback を指定しない。起動時には各実行ファイルがコンパイル時の `NCARD` と見えている GPU 数を照合し、不一致なら例外にする（`src/split/src/model.hpp:18-21`、`src/split/src/model.cpp:1237-1248`）。

## 実行時の詳細

スクリプト実行時に環境変数を読み、CMake configure の引数 `-DSTRATA_SPLIT_CARDS=...` に渡す。CMake は値ごとに `strata-split-N` を作り、CUDA/HIP それぞれのターゲット定義に `FNX_NCARD=N` を埋め込む。各スクリプトはその名前の Ninja ターゲットを順にビルドする。よって `CARDS="2 4"` は2枚用と4枚用の別バイナリを作る指定であり、単一バイナリが実行時に枚数を切り替える指定ではない（`packaging/build_split_cuda.sh:22-30`、`packaging/build_split_hip.sh:30-40`、`src/split/CMakeLists.txt:107-120,129-144`）。

値はスクリプト起動時にシェル展開される。ビルド後の `strata-split-N` が `CARDS` を再読込したり、CLI 引数や別の環境変数でコンパイル時の `FNX_NCARD` を上書きしたりする経路は確認できない。分割エンジンの説明書も、ビルド時に `STRATA_SPLIT_CARDS` でカード数ごとの実行ファイルを作ると記載している（`docs/SPLIT_ENGINE.md:92-95`）。

## ログと測定値

無効なカード数は CMake が `STRATA_SPLIT_CARDS: 2, 3 or 4, not <値>` の形式で configure を失敗させる（`src/split/CMakeLists.txt:107-110`）。値が有効でも、ビルドした実行ファイルが見つからなければ CUDA は `build_split_cuda.sh: no strata-split-N`、HIP は `build_split_hip.sh: no strata-split-N` を stderr に出して終了する（`packaging/build_split_cuda.sh:28-32`、`packaging/build_split_hip.sh:37-40`）。

`docs/SPLIT_ENGINE.md` には分割エンジン全体の内部測定があるが、`CARDS` の値ごとの比較測定ではないため、本変数の効果を示す測定値としては記載しない。

## 根拠

- `packaging/build_split_cuda.sh:6-10,12-39` — CUDA 用の既定値、CMake への転送、カード数別ビルド、生成物チェック。
- `packaging/build_split_hip.sh:10-16,17-60` — HIP 用の既定値、CMake への転送、カード数別ビルド、生成物チェック。
- `CMakeLists.txt:794-799`、`src/split/CMakeLists.txt:20-34,107-144` — 分割ビルドの有効条件、値の検査、ターゲットと `FNX_NCARD` 定義。
- `src/split/src/model.hpp:18-21`、`src/split/src/model.cpp:1237-1248` — コンパイル時カード数と実行時に見える GPU 数の照合。
- `docs/SPLIT_ENGINE.md:92-95` — ビルド時の `STRATA_SPLIT_CARDS` とカード数別実行ファイルの説明との照合。
