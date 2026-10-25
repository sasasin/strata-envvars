# `strata-gguf`（GGUF 検査 CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-gguf` |
| コマンド | `strata-gguf` |
| 主な実装 | `src/artifact/gguf_reader.cpp`、`include/strata/artifact/gguf_reader.hpp` |
| 用途 | CMake で生成される単体の GGUF 読み取り・検査用 CLI |

## 役割

指定した GGUF ファイルを読み取り、version、tensor 数、metadata 数、データ開始位置、ファイルサイズを表示します。任意の `--check` を付けると、tensor の block geometry と GGUF 内の配置の整合性、および対応する architecture metadata の検査結果も表示します。これは CMake 生成の診断・開発用プログラムで、Terminal CLI の `strata` サブコマンドではありません（`CMakeLists.txt:261-262`、[`docs/cli/README.md`](../../README.md) の CMake 生成単体 CLI 節）。

## 基本的な使い方

ビルド済みの実行ファイルに対して、次のように GGUF ファイルを渡します。

```sh
strata-gguf ./model.gguf
strata-gguf ./model.gguf --check
```

ビルド後の実行ファイルの置き場所は CMake の build directory によります。位置引数には検査対象のファイルを一つ指定します。`--check` は省略可能です。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 基本表示 | `strata-gguf FILE.gguf` | ファイルを開いて GGUF の基本情報を表示します。 |
| 検査付き表示 | `strata-gguf FILE.gguf --check` | 基本情報に加え、`blk.*` tensor 数、global tensor 数、Q2_0/BF16/F32 数、geometry bracket、architecture guard の結果を表示します。 |

## 主な動作と副作用

- ファイルを読み取り専用で開き、Windows では read-only file mapping、他の環境では `O_RDONLY` と `mmap(..., PROT_READ, MAP_PRIVATE, ...)` で読み込みます。ファイルを書き換える処理はありません（`include/strata/artifact/gguf_reader.hpp:414-446`）。
- reader は GGUF v3 以外を拒否します。header の範囲外読み取り、bad magic、重複 tensor 名、tensor dimension の異常なども例外として拒否します（`include/strata/artifact/gguf_reader.hpp:273-280,459-504`）。
- `--check` の geometry 検査では、認識できない type は `types unknown` に数えてその tensor の geometry 判定を飛ばします。既知 type については、計算した tensor byte 数が次の tensor までの offset 差（最後の tensor ではファイル末尾まで）の範囲に収まるかを調べます（`src/artifact/gguf_reader.cpp:29-56`）。
- `--check` は標準出力へ結果を表示します。ファイル操作以外に、ネットワーク接続、GPU 起動、外部プロセス起動、検査結果ファイルの生成は行いません（`src/artifact/gguf_reader.cpp:13-65`）。

## 注意点

- 引数の処理は簡易的です。第1引数をファイル名、第2引数が文字列 `--check` のときだけ検査モードとして扱い、それ以外の追加引数はエラーにせず無視します。したがって `--check` を第2引数以外に置いた場合は検査されません（`src/artifact/gguf_reader.cpp:7-12`）。
- `--check` の architecture guard は結果を `PASS` または `FAIL - ...` と表示しますが、その結果だけでは非ゼロ終了になりません。終了コードを 1 にする検査結果は geometry の `bad` が 1 件以上ある場合です（`src/artifact/gguf_reader.cpp:56-60`）。
- CMake のターゲット定義は確認しましたが、この調査ではビルド済み配布物や Release archive の実体を確認していません。実行ファイルはソースから生成する target として確認した範囲に限ります（`CMakeLists.txt:261-262`）。

## オプション文書

- [`--check`](--check.md) — 追加の geometry / architecture 検査。

## 根拠

- Strata `src/artifact/gguf_reader.cpp:7-65` — 引数の扱い、基本情報と検査結果の出力、終了コード、例外処理。
- Strata `include/strata/artifact/gguf_reader.hpp:273-280,380-446,459-504` — header 読み取り、read-only file mapping、GGUF v3 と構造の検証。
- Strata `CMakeLists.txt:253-265` — `strata_artifact` と `strata-gguf` の CMake target。
- [`docs/cli/README.md`](../../README.md) — `strata-gguf` の tool-id、root command scope、`--check` 文書リンク。
