# `CHAIN_GU`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

これは一般利用者向けの `strata` 実行時設定ではありません。リポジトリ内での読み取りは `metal/tests/token_chain.cpp` のみで、Metal の `token_chain` テスト実行ファイルで MoE expert の gate/up カーネルのタイル寸法を上書きします。Strata 本体や他の実行経路が読む実装は確認できません。

このテストは GGUF の実際の重みを使って Metal の decode chain を実行し、カーネル時間を測るものです。テストソースの説明では活性値は合成値であり、数値検証ではなく実データ列のタイミング測定とされています。

## 値と判定

値は `sscanf(e, "%d,%d,%d", &gl, &gr, &gs)` で読みます。要素は順に lanes per row (`gl`)、rows per lane (`gr`)、simdgroups (`gs`) です。文字列全体の検証や範囲検査はありません。

| 環境変数 | 初期値 | 設定時の処理 |
|---|---:|---|
| unset | `32, 1, 4` | 初期値を使う |
| 空文字 | `32, 1, 4` | `sscanf` が変換できず、初期値のまま |
| 3個の整数をカンマ区切りで指定 | 各値を上書き | 例: `16,2,4` は `gl=16`, `gr=2`, `gs=4` |
| 一部だけ変換できる入力 | 変換に成功した先頭要素だけ上書き | 例: `16,2,x` は `gl=16`, `gr=2`, `gs=4` |
| 先頭要素が整数として読めない入力 | 初期値のまま | 例: `x,2,4` |

`%d` は符号付き10進整数を読み、各変換前の空白は読み飛ばします。リテラルのカンマは必要です。3個目の後ろにある文字列は検査されず、たとえば `16,2,4tail` も3値を設定します。0、負数、カーネルに不適切な値も入力時点では拒否されません。

## 有効になる条件

Metal 用の `token_chain` 実行ファイルをビルドして実行し、その MoE expert の gate/up dispatch に到達した場合にだけ参照されます。`metal/CMakeLists.txt` は `tests/*.cpp` を個別の実行ファイルとして登録するため、これはテスト・測定プログラム内のフックです。CMake は macOS 以外では Metal ビルドを終了します。

通常の `strata` 実行ファイルや CUDA/HIP/SYCL の設定に `CHAIN_GU` が作用する根拠はありません。`000_envvers.md` に列挙された名前だけから、一般ユーザー向け設定とは判断できません。

## 実行時の詳細

テスト内では初期値 `gl=32`, `gr=1`, `gs=4` を置き、環境変数が設定されている場合に `sscanf` の変換結果で更新します。計算される `a.gx_gu` は `NFF / (gs * (32 / gl) * gr)` です。さらに `gl`, `gr`, `gs` から Metal pipeline 名 `moe_gu_<type>_<gl>_<gr>_<gs>` を構成し、dispatch の threadgroup 幅は `32 * gs` にします。そのため、この変数は単なる表示用ではなくテストで起動する gate/up カーネルの構成に使われます。

static cache はなく、gate/up dispatch の設定処理に到達するたびに `getenv` と `sscanf` を実行します。`gl` や `gr` が0の場合は `gx_gu` の式でゼロ除算になり得ます。値域の検査や不正値からの fallback はありません。

## 根拠

- `metal/tests/token_chain.cpp:1-4`: プログラムの用途を decode-chain のタイミング測定として説明。
- `metal/tests/token_chain.cpp:540-545`: 環境変数の読み取り、既定値、および `gx_gu` の計算。
- `metal/tests/token_chain.cpp:579-590`: gate/up pipeline 名、引数、threadgroup 幅を使った dispatch。
- `metal/CMakeLists.txt:1-9,41-46`: Metal の独立プロジェクトであること、および `tests/*.cpp` を個別実行ファイルにする設定。
- `docs/DETAILS.md`: `CHAIN_GU` の説明は見つかりませんでした。

