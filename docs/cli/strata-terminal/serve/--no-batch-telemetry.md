# `--no-batch-telemetry`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--no-batch-telemetry` |
| 別名 | `--batch-telemetry` の否定形（`argparse.BooleanOptionalAction` が生成） |
| 値 | 値を取らない。指定すると `False` |

## 役割

`strata serve` が推論エンジンへ batch telemetry を有効にする設定を渡さないようにする。`strata serve` の parser は `--batch-telemetry` を `BooleanOptionalAction` で登録しているため、Python `argparse` の否定形 `--no-batch-telemetry` も同じ引数の `False` として受理する。ソース上、否定形に別の処理や別 scope はない（`strata_cli/cli.py:45-57`）。

## 使い方

```sh
strata serve --profile /path/to/run-config.json --no-batch-telemetry
```

`--profile`（alias `--config`）は `strata serve` で必須（`strata_cli/cli.py:45-46`）。

## 値と既定値

このフラグ自体は値を取らず、指定すると `batch_telemetry=False` になる。サーバー側 parser も同じ `BooleanOptionalAction` と `default=None` で登録している（`serve/server.py:9983-9984`）。

`strata serve` 経由では、コマンドラインの明示値が保存済み profile の override、run config、環境変数 `STRATA_BATCH_TELEMETRY` より優先する。最終的にどの値も存在しない場合の既定値は `False`。環境変数は値が文字列 `1` の場合だけ有効扱いになる（`strata_cli/cli.py:746-765`）。

## 実行時の動作

`strata serve` は解決した値の由来が run config または既定値以外の場合、内部の server 起動引数に `--batch-telemetry` または `--no-batch-telemetry` を追加する。したがって明示した否定形は、profile や run config、環境変数が有効にしていても server に明示的な無効値として渡される（`strata_cli/cli.py:806-807`）。

server は engine 用環境を作る際、この引数が `False` なら継承環境から `STRATA_BATCH_TELEMETRY` を削除する。`True` の場合は値を `1` に設定し、引数が未指定なら run config の値を使う。通常の `strata` engine 起動時と split engine 起動失敗後の fallback 起動時にこの設定関数が呼ばれる（`serve/server.py:989-996`, `serve/server.py:10178-10183`, `serve/server.py:9546-9547`）。

engine は `STRATA_BATCH_TELEMETRY` が厳密に `1` のときだけ計測を有効化し、batch window の `BSTAT` 標本と grouped pipeline の `PSTAT` 標本を出力する箇所を条件付きで実行する。無効時にはこれらの標本処理を有効化しない（`src/program/generate.cpp:15529-15532`, `src/program/generate.cpp:15541-15548`, `src/program/generate.cpp:16582-16589`）。

## 適用条件と副作用

この設定は engine の起動時環境に反映される。起動済み engine の設定を動的に切り替える処理は、確認した経路では見つからなかった。否定形による副作用は engine 子プロセスへ telemetry 有効化環境変数を渡さないことであり、server 自体の終了や出力ファイル操作を行う指定ではない。

設定ファイルに `batch_telemetry` が含まれる場合、server はその型が厳密な bool であることを確認し、違えば parser error にする（`serve/server.py:10076-10077`）。ただし CLI で否定形を明示した場合は解決値が `False` となり、server 起動時には環境変数を削除する。

## 出力とエラー

`--no-batch-telemetry` 固有の警告やエラー出力は確認できなかった。サーバーの run config に `batch_telemetry` があって bool 以外なら、`ap.error("batch_telemetry must be true or false")` により parser error となる（`serve/server.py:10076-10077`）。

## 根拠

- `strata_cli/cli.py:45-57` — `serve` parser と `--batch-telemetry` の `BooleanOptionalAction` 登録。否定形はこの同一引数の生成形。
- `strata_cli/cli.py:746-765` — CLI / saved profile / run config / 環境変数 / 既定値の優先順位。
- `strata_cli/cli.py:806-807` — 解決値を server 引数に転送する条件と否定フラグ。
- `serve/server.py:989-996` — engine 環境変数の有効化・削除処理。
- `serve/server.py:9983-9984`, `serve/server.py:10076-10077`, `serve/server.py:10178-10183` — server parser、設定型検証、通常 engine 起動前の適用。
- `serve/server.py:9546-9547` — split engine fallback への適用。
- `src/program/generate.cpp:15529-15532`, `src/program/generate.cpp:15541-15548`, `src/program/generate.cpp:16582-16589` — engine 側の環境判定と telemetry 標本出力。
- `docs/TERMINAL.md:270-271` — 利用者向け資料では telemetry を opt-in と説明。具体的な現行処理は上記ソースを根拠とした。

索引 `docs/cli/README.md:16` は `--batch-telemetry` の alias として否定形を記載し、さらに同 `:22` で同じ否定形を独立リンクとして重複掲載している。ソース上は別 option ではなく同一 parser action の否定形であるため、この文書は索引の指定パスに合わせて作成した。索引は依頼範囲外のため変更していない。
