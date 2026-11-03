# `FNX_BENCH_CTX`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`FNX_BENCH_CTX` は同梱ツール `fnx_run` の `bench` モードで、計測する verify window の前に作る初期コンテキスト長を指定します。値 `N` を設定すると、参照 prompt の token を繰り返して N 個の token にし、`Engine::prefill()` で読み込んでからベンチマークを開始します。未設定ならこの事前 prefill を行わず、既定の空の engine 状態から計測します。

これは利用者向けの通常 CLI やサーバー設定ではありません。`fnx_run` は `STRATA_BUILD_TESTS` のビルドで追加されるテスト・診断用ターゲットで、CMake 上は CUDA ソースとしてコンパイルされ CUDA runtime とリンクされます。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | 外側の `getenv()` 判定が偽になり、context の作成と `prefill()` を飛ばす。 |
| 設定済みの整数 | 10 進の符号付き整数を全体 parse し、その値を `int` に変換して context 長に使う。 |
| 空文字、不正形式、`long long` の範囲外 | `env_int()` が例外を投げる。 |

`env_int()` は任意の符号（`+` / `-`）と数字列を受け付けますが、文字列全体が整数である必要があります。前後の空白、数字の後ろの文字、小数点、空文字は受け付けません。`FNX_BENCH_CTX` には正の値の検証や clamp がありません。値 0 は空 vector を `prefill()` に渡します。負値は vector のサイズに使われ、通常は過大サイズとして例外になります。`long long` から `int` への変換にも明示的な範囲検査はありません。

正の値が engine の `FNX_MAX_CTX`（既定 4096）を超えると、prefill 中に `prefill: context full` で拒否されます。`FNX_MAX_CTX` は engine を作る別の環境変数であり、CLI 引数による `FNX_BENCH_CTX` の上書きはありません。

## 有効になる条件

- `fnx_run` の `bench REF.bin T N` モードでだけ参照されます。`check`、`rows`、`gen`、`bench_step` など他モードではこの箇所を通りません。
- `fnx_run` ターゲット自体は `STRATA_BUILD_TESTS` ブロックで追加される CUDA テスト用 executable です。通常の sFNX 実行ファイルやサーバー経路にこの読み取り箇所はありません。
- 設定値が有効でも、モデル・引数・参照 prompt の読み込みなど `bench` の前段が成功してから効果が現れます。prompt token 列は少なくとも 1 個を含む形式でなければなりません。
- `FNX_MAX_CTX` が別途小さく設定されていれば、その engine 上限が prefill 可能な長さを制限します。

## 実行時の詳細

モデルと engine の作成後、コマンド引数から `T` と `n` を読み、`FNX_BENCH_CTX` の設定有無を確認します。設定されていれば整数値 `nc` 個の context vector を確保し、`toks[i % toks.size()]` で参照 prompt を先頭から循環して埋めて `e.prefill(ctx)` を呼びます。その後、`n` 回の verify window を実行し、最初の window は graph capture 用として集計から外し、残りについて wall/GPU 時間を出力します。

この値は `fnx_run_cmd()` の `bench` 処理中に都度読み取られ、static cache には保存されません。`fnx_run` の単独実行では読み取り後にプロセス環境を書き換える経路はありません。環境変数が不正な場合や prefill が失敗した場合、例外は `main()` で `fnx_run: <例外内容>` と stderr に出され、終了コード 1 になります。正常時は stdout に `bench ... wall median ... gpu median ...` の集計行が出ます。

## 根拠

- `src/split/tools/fnx_run.cpp:1280-1313` — `bench` モードの引数処理、変数の設定有無確認、parse、循環 prompt 作成、prefill、計測と結果出力。
- `src/split/src/env.hpp:15-21,33-40` — 符号付き 10 進整数の全体 parse、`long long` 範囲検査、無効値時の例外。
- `src/split/tools/fnx_run.cpp:984-988` — `FNX_MAX_CTX` の既定値 4096 と engine 作成時の読み取り。
- `src/split/src/prefill.cu:982-984,1038-1045` — prefill の前提条件と context 上限超過時の `Refused("prefill: context full")`。
- `src/split/tools/fnx_run.cpp:1364-1373` — 実行時例外の stderr 表示と終了コード。
- `src/split/CMakeLists.txt:126-165` — `STRATA_BUILD_TESTS` 条件下にある `split_fnx_run` ターゲットの定義、CUDA コンパイルとリンク。
