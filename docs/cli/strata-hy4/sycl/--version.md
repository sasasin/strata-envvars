# `--version`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

SYCL 版 Hy4-Flash エンジンのビルド時バージョン文字列を表示して終了する。モデルの読み込みや推論は行わない。

## 使い方

```sh
strata-hy4-sycl --version
```

## 値と既定値

値を取らず、既定値もない。表示文字列は `HY4_VERSION` マクロであり、このソースでは未定義の場合の既定値を `0.1.66` としている。ビルド時にマクロが別途定義されている場合の実際の値は、ソースだけからは確定できない。

## 実行時の動作

引数走査中に `--version` を見つけると、標準出力へ `strata-hy4 <HY4_VERSION>` と改行を出力し、終了コード `0` で直ちに戻る。従って後続の引数は処理されない。別名や値検証、複数指定時の特別な処理はない。

ただし引数走査より前に、`UR_LOADER_USE_LEVEL_ZERO_V2` が未設定なら起動したプロセスの環境へ `0` を設定し、`ONEAPI_DEVICE_SELECTOR` が未設定なら `HY4_BACKEND` に応じて selector を設定する。このため `--version` でも起動時の環境設定処理は通るが、版表示の経路では GPU 初期化やモデル読み込みには進まない。環境設定は起動した CLI プロセス内のもので、親シェルの環境は変更しない。

オプションは左から順に処理されるため、`--version` より前に不明な引数、または値が必要なオプションの値欠落があると、版表示に到達する前に終了する。反対に、`--version` の後ろにある引数は無視される。

## 出力とエラー

正常時は標準出力へ1行（`strata-hy4 <HY4_VERSION>`）、終了コード `0`。`--version` 自体にエラー経路はない。先行する値必須オプションの値が欠けると `ERR <option> needs a value` を標準出力へ出して終了コード `2`、先行する不明引数は標準エラーへ `unknown arg <arg>` を出して終了コード `2` となる。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:14-16` — `HY4_VERSION` のソース内 fallback 値。
- `engine/src/hy4flash/sycl/sy_main.cpp:79-92` — 引数処理前の環境設定。
- `engine/src/hy4flash/sycl/sy_common.h:33-39` — `hy4s_setenv` が現在のプロセス環境に設定する実装。
- `engine/src/hy4flash/sycl/sy_main.cpp:105-120` — 引数走査順、`--version` の出力と即時終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:109-115` — 値必須引数で値がない場合の出力と終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:190-197` — 不明引数の出力と終了。
- 索引上のスコープ: `docs/cli/README.md:1452-1503` に `strata-hy4-sycl` と `--version` が掲載されている。ツール入口・parser の対応は `docs/cli/000_cli_tools.md:11`。

実行バイナリの help/version 表示は実行していないため、個別ビルドでの `HY4_VERSION` の上書き有無は未確認。
