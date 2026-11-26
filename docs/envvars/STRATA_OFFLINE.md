# `STRATA_OFFLINE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この名前は Strata の serve サーバーが `--offline` を有効にしたとき、エンジンなどの子プロセスへ渡す環境マーカーである。Strata の本番コードに親環境から `STRATA_OFFLINE` を読み取る箇所はなく、この変数自体がサーバーのオフライン動作を切り替えるわけではない。切替元は CLI の `--offline` で、子環境へは文字列 `1` が設定される（`terminal/serve/server.py:9189-9190,4007-4049`; `terminal/strata_control/offline.py:42-59,120-134`）。

## 値と判定

Strata は受け取った `STRATA_OFFLINE` の値を parse しない。親プロセスで未設定・空文字・`0`・`false`・その他の値のいずれでも、サーバー側の分岐には影響しない。

| 条件 | 親環境の値 | 子環境での結果 |
|---|---|---|
| `serve --offline` を指定 | 任意（未設定・空文字を含む） | 子環境の既存値を上書きして `STRATA_OFFLINE=1` を設定 |
| `serve --offline` を指定しない | 親環境または設定に値がある | サーバーの `child_env` はこの名前を消さず、組み立てた値を子へ渡す |
| `strata_control.offline` の import が失敗し、`--offline` 指定中 | 任意 | fallback で `STRATA_OFFLINE=1` を設定 |

値の大文字小文字、空白、数値変換、境界値は Strata では判定されない。`strata_control.offline.child_environment` helper は offline が false なら `OFFLINE_ENV` のキーを削除するが、serve の `child_env` は offline が false のときこの helper を呼ばない。そのため serve の通常経路では、親環境や設定 `env` にあった値は子環境に残る（`terminal/strata_control/offline.py:126-134`; `terminal/serve/server.py:4027-4049`）。

## 有効になる条件

- サーバーがこの変数を `1` に明示設定するのは `serve --offline` が指定された場合である。これは `store_true` の CLI フラグであり、`STRATA_OFFLINE` を CLI 引数や設定値から判定する処理ではない。offline を指定しない場合でも、親環境や設定に存在する値がそのまま子へ継承されることはある（`terminal/serve/server.py:9189-9190,4010,4027-4049,9375-9394`）。
- offline 起動は MCP サーバーおよび `before_load` コマンドが設定されていると CLI エラーになり、さらに `ensure_strictly_offline` が返すプロファイル上のネットワーク要件があれば起動前に拒否する（`terminal/serve/server.py:9372-9384`; `terminal/strata_control/offline.py:137-164`）。
- 通常エンジン、replica、split、および split fallback の子環境を組み立てる経路で `offline` 引数が渡される（`terminal/serve/server.py:8788-8824,8829-8852,8899-8919,9472-9477`）。
- `--offline` が false でも、親プロセスにこの名前が設定されているだけでは有効にならない。Strata のコードはその値を参照しない。

## 実行時の詳細

`child_env` はまず親環境を複製し、設定の `env` を適用する。その後 offline が true なら `OFFLINE_ENV` を最後に更新するので、設定に `STRATA_OFFLINE` があっても値は `1` になる。offline が false の場合、serve の `child_env` はこの名前を消さず、親環境または設定由来の値があればそのまま子に渡す（`terminal/serve/server.py:4010,4027-4049`）。別の `child_environment` helper は offline false 時に `OFFLINE_ENV` のキーを削除するが、serve の `child_env` から呼び出されてはいない（`terminal/strata_control/offline.py:120-134`）。offline policy モジュールを import できない場合も fallback で `STRATA_OFFLINE`、`HF_HUB_OFFLINE`、`TRANSFORMERS_OFFLINE` を `1` に設定する（`terminal/serve/server.py:4040-4049`）。

これはサーバー起動時に各子プロセス用の環境辞書へ設定され、環境変数のプロセス内 cache や実行中の再読込はありません。`strata_control.offline` にある `child_environment` も `offline` 引数で同様に辞書を設定・削除する helper であり、`STRATA_OFFLINE` 自身を読みません（`terminal/strata_control/offline.py:120-134`）。

Strata がこのマーカーを子へ渡す事実から、子プロセスがそれを読むか、どのような意味で扱うかは断定できない。Strata の serve 側のネットワーク制約や URL 判定は `offline` 引数を使う別の処理であり、この環境変数の読み取り結果ではない（`terminal/strata_control/offline.py:88-117`）。

## 根拠

- `terminal/strata_control/offline.py:42-59` — 子環境用変数の定義と `STRATA_OFFLINE` の値。
- `terminal/strata_control/offline.py:120-134` — `offline` 引数による環境辞書の設定・削除。
- `terminal/serve/server.py:4007-4049` — Strata サーバーの子環境構築、設定優先関係、fallback。
- `terminal/serve/server.py:9189-9190,9372-9394,9472-9477` — `--offline` の定義、事前条件、子起動への伝播。
- `terminal/serve/server.py:8788-8824,8829-8852,8899-8919` — 単一エンジン fallback、replica、split 起動時の適用。
