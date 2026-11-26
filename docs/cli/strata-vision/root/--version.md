# `--version`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（`strata-vision` / `strata-vision-hip` / `strata-vision-sycl` の各実行ファイル） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

起動した画像 reader のビルド種別を標準出力に表示して、モデルの読み込みや常駐処理へ進まず終了する。表示はビルドマクロに応じた名前（HIP では対応 GPU architecture も含む）であり、Strata 製品や engine の数値バージョン、commit SHA を報告するものではない。

## 使い方

```sh
strata-vision --version
strata-vision-hip --version
strata-vision-sycl --version
```

各コマンドは対応するビルドの実行ファイル名に置き換える。引数解析では `--version` に値を要求しない。

## 値と既定値

値を取らず、既定値や値の validation はない。parser は引数を左から順に処理し、`--version` に到達すると表示してただちに `return 0` する。そのため `--mmproj` を指定しなくても単独で使える。一方、`--version` より前に値が必要な別オプションの値を省略したり、未知の引数を置いたりすると、そのエラーで終了して version 表示には到達しない。`--version` より後ろの引数は解析されない。

## 実行時の動作

出力はコンパイル時の条件で決まる。

- `STRATA_VISION_HIP` ビルド: `strata-vision hip (GPU architectures: <architecture list>)`
- `STRATA_VISION_METAL` ビルド: `strata-vision metal`
- `STRATA_VISION_SYCL` ビルド: `strata-vision sycl (Intel GPU)`
- それ以外: `strata-vision`

parser の分岐は `printf` の後すぐ成功終了するため、`--mmproj` の必須確認、GPU 可視性の切り替え、常駐 reader の実行には進まない。従って、このオプションで画像を処理したり、server protocol の `READY` 行を出したりはしない。CUDA ビルドはこの分岐で専用の文字列を出す条件がなく、コード上は `strata-vision` と表示する。

## 適用条件と副作用

どの backend ビルドにも共通する引数だが、表示内容は実行ファイルに組み込まれた compile definition に依存する。HIP の architecture 表示もビルド時の `STRATA_VISION_HIP_ARCHS` から設定される。

引数解析より前に、Windows の HIP ビルドでは実行ファイル隣の `rocm\\bin` が存在すれば DLL 検索先に設定され、非 Windows の HIP ビルドでは実行ファイル位置を使って kpack path の初期化が行われる。その後の parser 内では `--version` 分岐から戻るため、GPU の検出・初期化やモデルファイルへのアクセスには進まない。

## 出力とエラー

成功時は backend 表示を標準出力へ1行出し、終了コード `0` を返す。数値バージョン、stderr 出力、ファイル出力はこの分岐にはない。失敗時は、引数解析より前に発生する起動時エラーを除き、`--version` 自体に固有の validation error はない。先行する引数の値不足は stderr に `<option> needs a value` を出して終了コード `2`、先行する未知引数は stderr に `unknown argument <argument>` を出して終了コード `2` となる。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:36-60` — `main` 冒頭の HIP 固有初期化。Windows では隣接 `rocm\\bin` を条件付きで DLL 検索先に設定し、非 Windows では kpack path を適用する。
- `terminal/tools/vision/strata_vision.cpp:61-91` — 左からの引数解析、値不足・未知引数のエラー、および `--version` の backend 別出力と即時成功終了。
- `terminal/tools/vision/strata_vision.cpp:93-96, 97-107, 140` — `--mmproj` 確認、GPU 可視性設定、reader 実行は `--version` の早期 return より後にある。
- `terminal/tools/vision/CMakeLists.txt:25-39, 84-98` — HIP / SYCL / Metal の build 条件と compile definition、実行ファイル名の設定。
- `docs/cli/README.md:1644-1657` — `strata-vision` root scope と、作成対象の `--version` 索引リンク。
- `docs/cli/000_cli_tools.md:14` — `strata-vision` の tool ID、parser 所在、root scope。
