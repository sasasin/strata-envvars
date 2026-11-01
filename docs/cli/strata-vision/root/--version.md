# `--version`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、作業ツリーは clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl`（ビルド構成による実行ファイル名） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 値を取らない |

## 役割

実行ファイルのビルド variant を標準出力へ表示して、終了します。表示はコンパイル時の定義で決まり、HIP 版は対応 GPU architecture の文字列も表示します。実行ファイル名と variant の対応はビルド構成に依存します（`tools/vision/CMakeLists.txt:96-116`）。

## 使い方

```sh
strata-vision --version
```

同じ parser を使う HIP / SYCL 版では、実際に配布・配置された実行ファイル名を使います（`docs/cli/README.md` の `strata-vision` 節）。

## 値と既定値

値は不要です。値の validation や既定値はありません。`--version` に到達すると、選択されたビルド分岐に応じて次の形式の一行を stdout に出し、終了コード 0 で直ちに終了します（`tools/vision/strata_vision.cpp:102-112`）。

- HIP: `strata-vision hip (GPU architectures: <ビルド対象>)`
- Metal: `strata-vision metal`
- SYCL: `strata-vision sycl (Intel GPU)`
- 上記以外: `strata-vision`

これはバージョン番号や commit SHA の表示ではありません。表示分岐はソース上で HIP、Metal、SYCL、汎用の順に選ばれます（`tools/vision/strata_vision.cpp:103-111`）。

## 実行時の動作

引数を左から解析し、`--version` に達した時点で表示して `return 0` します。そのため通常の画像読み取りに必要な `--mmproj` と `--model` は不要で、vision encoder やモデルの読み込みにも進みません（引数解析: `tools/vision/strata_vision.cpp:93-112`、必須引数確認: 同 `:125-128`、backend 初期化: 同 `:141-143`）。

この parser は `--version` 専用の早期 parser ではなく逐次処理です。先行する引数は通常どおり解析されるため、先に未知の option があれば `unknown argument` を stderr に出して終了コード 2 になり、値を要求する option の値が欠けていれば `<option> needs a value` を stderr に出して終了コード 2 になります（`tools/vision/strata_vision.cpp:93-97, 123`）。一方、`--version` より後ろの引数は検査されません。

## 適用条件と副作用

表示内容はビルド時に有効な compile definition によります。CMake は HIP 版を `strata-vision-hip`、SYCL 版を `strata-vision-sycl` として出力し、それぞれ対応する定義を付けます。Apple で Metal が有効な場合は Metal 表示用の定義を付けます（`tools/vision/CMakeLists.txt:103-116`）。個別の Release artifact の有無や、実行環境での GPU 利用可否はこの option からは判定できません。

通常は表示後に終了するため、モデル・画像ファイルの読み込み、GPU/backend 初期化、常駐処理は行いません（`tools/vision/strata_vision.cpp:112, 141-143`）。ただし Windows の HIP 版では、option 解析より前に実行ファイル位置を調べ、隣に `rocm\\bin` があれば `SetDllDirectoryW` でこのプロセスの DLL 検索先を設定します。これは `--version` でも通る起動時処理です（`tools/vision/strata_vision.cpp:72-87`）。

## 出力とエラー

variant の一行は stdout、終了コードは 0 です。オプション引数を要求する先行 option の値不足と、先行する未知の引数は stderr へエラーを出し、終了コード 2 で終わるため、version 行は出ません（`tools/vision/strata_vision.cpp:96-97, 102-112, 123`）。

## 根拠

- `tools/vision/strata_vision.cpp:71-87` — `main` 冒頭の Windows HIP DLL 検索先設定。
- `tools/vision/strata_vision.cpp:93-128` — 手書き argument parser、`--version` の出力・早期終了、エラーと必須引数確認。
- `tools/vision/strata_vision.cpp:141-143` — backend 初期化位置（version 分岐より後）。
- `tools/vision/CMakeLists.txt:96-116` — 実行 target 名と HIP / Metal / SYCL compile definition。
- `docs/cli/README.md:1511-1526` — 独立 CLI としての scope、予定リンク、build variant の索引上の説明。

調査では同一 revision のソースを確認しました。`--help` の実行、build、GPU 実行、テストは行っていません。
