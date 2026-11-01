# `HF_HUB_OFFLINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの動作は対象外。

## 役割

Strata サーバーが `--offline` で起動されたとき、エンジンや画像 reader などの子プロセスへ渡す環境に `HF_HUB_OFFLINE=1` を設定します。Strata 自身が親プロセスの `HF_HUB_OFFLINE` を読んで分岐する箇所はありません。この変数によって外部ライブラリがどう動くかは本調査の対象外です。

## 値と判定

Strata はこの変数の値を parse しません。strict offline の子環境を作る際に文字列 `"1"` を固定で代入します。

| 起動状態 | 子プロセスに渡す `HF_HUB_OFFLINE` |
|---|---|
| `--offline` 指定あり、通常の offline policy import 成功 | `"1"` |
| `--offline` 指定あり、policy import に失敗 | `"1"`（fallback で直接設定） |
| `--offline` 指定なし | 特別な設定なし。親環境をコピーし、設定ファイルの `env` があればその値で上書き |

従って unset、空文字、`0`、その他の文字列を Strata が真偽値として解釈する規則はありません。offline 指定時は、親環境や設定ファイルで指定した値も `"1"` に上書きされます。offline 指定がない場合、`child_env()` はこの名前を除去しないため、親環境または設定ファイル由来の値がそのまま残り得ます。

## 有効になる条件

- サーバー CLI の `--offline` を指定した場合に限り、Strata はこの値を子環境へ明示設定します。オプションは `store_true` で、既定値は偽です。
- offline 起動時には MCP server、`before_load` command、または profile がネットワークを必要とする条件があると、子プロセス起動前に argparse のエラーとして拒否されます。
- 通常の単一エンジン起動、replica 起動、split 起動はそれぞれ `child_env(..., offline=...)` で環境を作ります。設定された環境は Strata engine の起動に渡されます。設定に vision reader がある場合も engine 環境を基にした環境が reader に渡されます。
- この変数に関する OS / GPU backend / build macro の分岐は確認できません。Strata が行うのは子環境への設定です。

## 実行時の詳細

`child_env()` はまずサーバープロセスの `os.environ` を複製し、profile の `env` 項目を反映します。その後 `offline=True` なら `strata_control.offline.OFFLINE_ENV` を適用し、import できない場合も fallback として `HF_HUB_OFFLINE` を `"1"` に設定します。offline policy の定義にも同じ固定値があります。これらは起動ごとに環境辞書を作る処理で、Strata にこの値の static cache や再読み取り処理はありません。

通常のエンジン起動ではこの環境を `StrataEngine` に渡し、`Popen` で子プロセスを起動します。replica と split の各 engine も同じ `child_env` 経路を使います。別プロセスの画像 reader は engine 環境を受け取り、GPU 指定がある場合は可視 GPU の項目だけを変更します。

この変数だけを理由に出す Strata のログ、警告、終了コードは見つかりません。`--offline` と両立しない profile 条件に対する起動拒否はありますが、これは `HF_HUB_OFFLINE` の値を読んだ結果ではありません。外部ライブラリによる値の読み取り後の挙動・エラーはここでは断定しません。

## 根拠

- `serve/server.py:9000-9001` — `--offline` は `store_true` オプション。
- `serve/server.py:9172-9184` — offline 指定時の profile 条件を子プロセス起動前に検査し、不適合なら `ap.error()`。
- `serve/server.py:3747-3777` — 親環境の複製、設定 `env` の反映、offline policy の後勝ち適用、および import failure 時の固定値 fallback。
- `strata_control/offline.py:44-61` — offline 子環境の一括設定中に `HF_HUB_OFFLINE: "1"` を定義。
- `serve/server.py:1077-1079, 9273-9279` — engine 子プロセスへの環境引き渡しと単一 / replica / split 起動経路。
- `serve/server.py:3931-3946, 9223-9224` — vision reader 用環境は engine 環境を引き継ぐ。GPU 指定がある場合に変更するのは可視 GPU 関連項目。
- `serve/server.py:2844-2850` — vision reader の `Popen` にその環境を渡す。
- `strata_control/offline.py:122-136` — `child_environment()` helper は offline 時に同じ辞書を適用し、offline でない場合は辞書中の marker を削除する。ただし本番 server の `child_env()` はこの helper を呼ばず、上記の独立した実装で環境を構成する。
