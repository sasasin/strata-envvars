# `--version`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（トップレベル。`generate` の直後にも指定可能） |
| オプション | `--version` |
| 別名 | `-V` |
| 値 | 取らない |

## 役割

エンジンのビルド時バージョンを `strata <version>` の1行で表示し、終了コード0で終了します。バージョン照会用の早期分岐であり、モデルや GPU を使った生成処理には進みません。

## 使い方

```sh
strata --version
strata -V
strata generate --version
```

## 値と既定値

値を取りません。既定値という設定項目はなく、表示文字列はビルド定義の `STRATA_VERSION` です。エンジンの CMake プロジェクト版 `PROJECT_VERSION` がこのマクロに設定されます。

## 実行時の動作

起動後、`argv[1]` と `argv[2]` の範囲を調べ、どちらかが `--version` または `-V` と完全一致すれば、標準出力に `strata <STRATA_VERSION>` と改行を出して直ちに `0` を返します。そのため `strata generate --version` も認識されます。探索はこの2引数までなので、3番目以降の引数にだけ置いた `--version` はこの早期分岐では認識されません。値の validation や複数指定の特別な処理はありません。認識時は後続引数を解析せず終了します。

この分岐より前に標準出力の非バッファ設定と通常の I/O 優先度への復帰が行われます。また Linux HIP ビルドでは NUMA 設定処理があり、Windows HIP ビルドでは実行ファイル隣の `rocm\\bin` が存在する場合に DLL 検索先へ設定します。これらはバージョン照会でも先に実行されますが、バージョン分岐自体は GPU 初期化より前にあります。

## 出力とエラー

認識された場合は標準出力へ1行を出力して終了コード `0` を返します。この分岐では引数エラーを報告せず、値の不正による失敗経路もありません。NUMA 設定処理がメッセージを返した場合は標準エラーへの出力がバージョン分岐前に行われ得ます。

## 根拠

- `engine/src/program/generate.cpp:3680-3705` — 起動時の先行処理、最初の2引数の走査、`--version` / `-V` の判定、出力と成功終了。
- `engine/CMakeLists.txt:13,34` — プロジェクト版の定義と `STRATA_VERSION` への設定。
- `docs/cli/README.md:1036-1042,1227` — `strata-engine` の `strata` エンジン引数（root）階層と対象リンク・alias。
- 配布バイナリでの出力は実行していません。説明は上記 checkout のソースに基づきます。
