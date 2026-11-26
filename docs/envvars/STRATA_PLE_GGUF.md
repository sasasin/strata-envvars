# `STRATA_PLE_GGUF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`ple_parity` 診断プログラムが PLE テーブルを含む GGUF ファイルとして開くパスの既定値を指定する。通常の `strata` 推論エンジンが読む設定ではなく、CUDA 系と SYCL 系の `engine/.../kernels/ple_parity.cpp` にだけ実行時環境変数の読み取りがある。いずれも起動時に値を文字列として取り込み、`--gguf` 引数があればその値で置き換える（CUDA 系 `engine/src/kernels/ple_parity.cpp:252-268`、SYCL 系 `engine/sycl/src/kernels/ple_parity.cpp:301-319`）。

## 値と判定

数値や真偽値には変換しない。`std::getenv` が null かどうかだけで未設定を判定し、設定されていれば返された文字列全体をパスとして使う。したがって空文字も「設定済み」であり、空のパスになる。空白の除去、大文字小文字変換、パス存在確認はこの判定時には行わない。

| 実行経路 | unset | 設定時に使われる値 | 無効値・境界の扱い |
|---|---|---|---|
| CUDA/HIP 系 `ple_parity` | `../../Q2_0/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf` | 文字列全体をパスとして使用。空文字、`0`、`true`、空白を含む文字列もそのままパスになる | 文字列としての受理拒否はない。存在しない・不適合なファイルかは後続の `PleTable::open` 等で判定 |
| SYCL `ple_parity` | 同じ相対パス | 同じ規則 | 同じ規則 |

環境変数を設定していても、コマンドラインに `--gguf <path>` を指定すると、その引数の値が優先される。`--gguf` の後続引数が存在しない場合は別の不正引数として usage を出して終了する。CUDA 系 `engine/src/kernels/ple_parity.cpp:256-269`、SYCL 系 `engine/sycl/src/kernels/ple_parity.cpp:305-319`。

## 有効になる条件

- 対象は `ple_parity` 実行ファイルを起動した場合に限る。通常の推論実行・サーバーモードの設定としては使われない（環境変数名の全参照はこの 2 つの読み取りと CMake 設定、および設定レジストリ項目）。
- CUDA 系では PLE parity 実行ファイルがビルド・登録された経路、SYCL 系では SYCL テスト設定内の `ple_parity` が対象。トップレベル CUDA 系 CMake は `ple_parity` を `--selftest` 付きで登録し、作業ディレクトリを engine ソースルートにする（`engine/cmake/strata_gpu_engine.cmake:1214-1229`）。SYCL CMake は `ple_parity` を engine ルートを作業ディレクトリとして登録する（`engine/sycl/CMakeLists.txt:494-501,533-543`）。
- `--selftest` または `--check-fixtures` を付けた実行では GGUF が必須。テーブルを開けない、行数が異なる、ファイルサイズが想定と異なる場合は stderr に `ple_parity: required PLE table is missing or incompatible: ...` を出し、終了コード 2（CUDA 系 `engine/src/kernels/ple_parity.cpp:281-285`、SYCL 系 `engine/sycl/src/kernels/ple_parity.cpp:330-334`）。
- 通常診断で GGUF を開けない場合はテーブルとブロック検査をスキップして部分診断として終了する。`--selftest` なら終了コード 1、通常実行ではそれまでの検査結果 `bad` に応じて 0 または 1（CUDA 系 `engine/src/kernels/ple_parity.cpp:455-459`、SYCL 系 `engine/sycl/src/kernels/ple_parity.cpp:503-509`）。
- SYCL CMake には同名の CMake cache 変数 `STRATA_PLE_GGUF` もある。これは `-DSTRATA_PLE_GGUF=...` から `ple_parity --gguf ...` を構成するビルド・テスト設定であり、実行時環境変数とは別経路。値が空でなければ CLI 引数に追加されるため、実行時環境変数より CLI 値が優先される（`engine/sycl/CMakeLists.txt:533-543`）。CUDA 系 CMake の `ple_parity` 登録はこの同名 cache 変数を使わず、実行時環境変数か直接指定した `--gguf` がパスを決める（`engine/cmake/strata_gpu_engine.cmake:1218-1229`）。

## 実行時の詳細

各 `main` の開始時に環境を読み、ローカル `std::string gguf` に格納する。別の static cache はなく、そのプロセスの実行中に環境を変更しても格納済みパスは変わらない。起動後の変更を反映するには新しい `ple_parity` プロセスが必要。CLI 引数は環境読み取り後に走査されるため、`--gguf` があれば最後にそのパスとなる（CUDA 系 `engine/src/kernels/ple_parity.cpp:252-268`、SYCL 系 `engine/sycl/src/kernels/ple_parity.cpp:301-317`）。

`--selftest` / `--check-fixtures` の場合は GPU 呼び出し前の preflight で `PleTable::open(gguf, err)` を呼ぶ。`PleTable::open` は GGUF を開き、`per_layer_token_embd.weight` を探してテーブル形状・形式などを検査する（CUDA 系共通実装 `engine/src/kernels/ngram.cpp:360-389`）。通常診断では後段の IQ4_NL テーブル検査で開く。値はこの GGUF の選択だけに使われ、生成モデルや推論時の出力を切り替える処理はない。

## ログと測定値

無効な値形式そのものを示す警告はない。ファイルを開けないときのログと終了の扱いは「有効になる条件」に記した通り。通常診断では `cannot open the PLE table: ...` と `TABLE AND BLOCK SKIPPED; partial diagnostic only` を stdout に出す（CUDA 系 `engine/src/kernels/ple_parity.cpp:455-459`、SYCL 系 `engine/sycl/src/kernels/ple_parity.cpp:503-509`）。この変数による性能測定値は該当しない。

## 根拠

- `engine/src/kernels/ple_parity.cpp:252-285,455-459` — CUDA/HIP 系プログラムの環境読み取り、CLI 上書き、preflight と失敗経路。
- `engine/sycl/src/kernels/ple_parity.cpp:301-334,503-509` — SYCL 系プログラムの同等処理。
- `engine/src/kernels/ngram.cpp:360-389` — GGUF を開き、PLE テーブルを検査する処理。
- `engine/cmake/strata_gpu_engine.cmake:1214-1229` — CUDA 系 parity 実行ファイルと selftest の登録。
- `engine/sycl/CMakeLists.txt:494-501,533-543` — SYCL parity 実行ファイル、CMake cache 変数、`--gguf` 引数の組み立て。
