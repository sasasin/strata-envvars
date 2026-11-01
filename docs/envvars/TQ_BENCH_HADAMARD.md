# `TQ_BENCH_HADAMARD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 同梱ツール `tq_sycl_parity` の `--bench` 経路で、合成入力を使う grouped expert kernel ベンチマークに Hadamard 条件を設定します。Strata の通常の engine 実行を切り替える変数ではありません。ツールの `--synthetic` と実テンソル比較経路はこの変数を読みません。

この実行経路は `STRATA_NATIVE_EXPERTS` が有効な SYCL CMake 構成で `tq_sycl_parity` ターゲットをビルドした場合に含まれます。CMake のオプション既定値は ON です。

根拠: `sycl/CMakeLists.txt:171,454-473`、`sycl/src/kernels/tq_sycl_parity.cpp:374-385,414-415`。

## 値と判定

値を parse せず、`std::getenv(...) != nullptr` の真偽だけで判定します。

| 環境の状態 | ベンチマーク内の `had` |
|---|---|
| 未設定 | `false` |
| 空文字を設定 | `true` |
| `0`, `false` など任意の非空文字列 | `true` |

数値変換、文字列比較、clamp、無効値時の fallback はありません。既定は Hadamard 条件なしです。CLI の `--bench GU/DOWN ...` がベンチマーク経路を選び、環境変数がその経路の Hadamard 条件を決めます。別経路の `--synthetic --hadamard` は CLI 引数を直接判定し、この環境変数とは独立です。

根拠: `sycl/src/kernels/tq_sycl_parity.cpp:374-385`。

## 有効になる条件

`argc >= 3` かつ第 1 引数が `--bench` の場合にだけ読み取られます。`tq_sycl_parity` のビルドが存在しても、この CLI 経路に入らなければ影響しません。OS/backend をまたいだ設定ではなく SYCL ツールのコードに限られます。

根拠: `sycl/src/kernels/tq_sycl_parity.cpp:374-381`、`sycl/CMakeLists.txt:454-473`。

## 実行時の詳細

`main()` が `--bench` を選んだ時点で一度読み、結果を `bench()` へ渡します。static cache はなく、同じプロセスから別途この実行ファイルを起動すれば、その起動時の環境で判定されます。起動後に環境を書き換えて再評価する処理はありません。

`had` が真の場合、ベンチマークは固定 seed から gate/up 幅 2560 と down 幅 640 の符号列を作り、レイアウトに Hadamard block 128 と down 側の符号列を設定します。grouped kernel は `L.had_block > 0` のとき SwiGLU 後の hidden row に Hadamard 変換を適用してから量子化します。出力の `bench ...` 行には ` hadamard` が付きます。偽の場合はこのレイアウト設定と変換を行わず、ラベルも付きません。

環境変数固有の警告やエラー出力はありません。要求された型ペアを native expert kernel が扱えない場合は `<GU>/<DOWN>: not a pair the GPU expert kernels take` を標準出力に出し、`bench()` は終了コード 1 を返します。正常時は median 時間等を標準出力へ出し、終了コード 0 です。GPU 実行中の失敗についてはこの環境変数用の個別処理を確認できませんでした。

根拠: `sycl/src/kernels/tq_sycl_parity.cpp:312-324,353-368,374-381`、`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5719-5723`。

## 根拠

候補一覧 `docs/envvars/000_envvers.md:1681-1684` の名前は、`sycl/src/kernels/tq_sycl_parity.cpp:379` で実際に環境から読み取られています。Strata リポジトリ全体を名前で検索した結果、この直接参照以外の読み取り・転送・helper 経由参照はありませんでした。
