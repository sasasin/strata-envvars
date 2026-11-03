# `HF_HUB_DISABLE_TELEMETRY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の状態は `## main...origin/main`（変更表示なし）。

## 役割

Strata 自身がこの変数を読み取って動作を変える箇所は見つかりませんでした。Strata のサーバーが engine 子プロセスへ環境変数を渡すとき、`--offline` が有効で offline policy の import に成功すると、`HF_HUB_DISABLE_TELEMETRY=1` を環境辞書に設定します。したがって、Strata 側で確認できるのは子プロセスへの設定・転送です。この変数名を受け取る外部ライブラリの挙動は本書の対象外です。

## 値と判定

| 経路 | 子プロセスに渡す値 |
|---|---|
| `--offline` あり、`strata_control.offline` の import 成功 | 親環境やプロファイルにある値にかかわらず、`"1"` に上書き |
| `--offline` あり、offline policy の import が `ImportError` | この変数は Strata が設定しない。親環境・プロファイル値があればその値が残る |
| `--offline` なし | 親環境の値を引き継ぎ、プロファイルの `env` に同名キーがあればその文字列値で上書き。どちらにもなければ未設定 |

Strata はこの変数の値を parse・検証しません。空文字や任意の文字列も、通常経路ではそのまま環境辞書に残ります。`--offline` と import 成功時だけ固定値 `"1"` に置き換えます。CLI の別引数やこの変数の値の大小による優先順位はなく、上記の環境構築順で決まります。

## 有効になる条件

- 変数を Strata が明示設定する経路は、`serve/server.py` の `--engine strata` と `--offline` を併用し、`strata_control.offline` の import に成功する場合です。`--offline` は `store_true` の CLI 引数です。
- `--offline` の事前検査では、MCP server または `before_load` command が設定されている場合に起動を拒否します。また offline policy による profile 要件検査でネットワーク要件が見つかった場合も拒否します。これらは変数値の検査ではありません。
- offline policy の import に失敗した場合、fallback は `STRATA_OFFLINE`、`HF_HUB_OFFLINE`、`TRANSFORMERS_OFFLINE` のみを設定し、この変数は設定しません。
- OS、GPU backend、build macro、モデル状態によるこの変数固有の分岐はありません。`--offline` を付けない通常経路では、Strata はこの名前を特別扱いしません。

## 実行時の詳細

サーバー起動時に `child_env()` が親環境を複製し、config の `env` 項目を文字列化して反映します。その後 `offline=True` なら offline policy の環境を最後に適用するため、profile の同名設定より `"1"` が優先します。offline policy が import できなければ上記の限定的な fallback を使います（`serve/server.py:4054-4084`）。

engine 起動時にはこの環境辞書を `StrataEngine` に渡し、`Popen` に設定します。通常起動、split fallback、replica の各起動経路でも `child_env()` の結果が渡されます（`serve/server.py:9114-9143,9164-9171,9238`、子プロセス生成は `serve/server.py:1153`）。設定時期は子プロセス起動ごとの環境辞書作成時であり、Strata によるキャッシュやリクエストごとの再評価はありません。起動済み子プロセスの環境は後から書き換わりません。

この変数専用のログ、警告、終了・失敗処理は見つかりませんでした。`--offline` の profile 条件違反は argparse のエラーとして起動前に拒否されますが、その判定は profile の MCP・`before_load`・ネットワーク要件に対するもので、この変数の値には依存しません（`serve/server.py:9707-9719`）。

## 根拠

- `strata_control/offline.py:44-61` — offline 用の子環境定数に、この変数を値 `"1"` として登録。
- `serve/server.py:4054-4084` — 親環境・profile `env` を辞書に反映し、offline 時は policy の環境を後から適用。import 失敗時の fallback はこの変数を含まない。
- `serve/server.py:9533-9536,9707-9729` — `--offline` の CLI 定義、事前条件検査、engine 環境の作成。
- `serve/server.py:9114-9143,9164-9171,9238` — 通常 engine、fallback、replica、split engine 起動に環境辞書を渡す箇所。
- `serve/server.py:1153` — engine の `Popen` に環境辞書を渡す箇所。
- リポジトリ全体で名前の完全一致を検索したところ、実装上の直接参照は `strata_control/offline.py:50` のみでした。Strata による環境読み取りは確認できていません。
