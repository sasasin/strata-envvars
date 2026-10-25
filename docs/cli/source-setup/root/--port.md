# `--port`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、更新 wrapper から委譲） |
| オプション | `--port` |
| 別名 | なし |
| 値 | HTTP server の TCP port。`int` として解析 |
| 既定値 | 新規設定では `8080`。既存モデルを通常起動するときは設定ファイルの `port`。 |

## 役割

セットアップで作るモデル別設定、または既存モデルの起動で使用する HTTP API server の待受ポートを指定します。Linux / Windows の共通 parser は `--port` に整数変換を指定しています（`setup.py:8460`）。ラッパーは引数を `setup.py` に渡します（`setup.sh:8-13`、`START-HERE.bat:27-34`、`SETUP.bat:1-2`、`update.sh:53-55`、`UPDATE.bat:79`）。

## 使い方

```sh
./setup.sh --port 8081
```

既存の設定済みモデルを一度だけ別ポートで起動する場合も、`./setup.sh --port 8081` を指定できます。Windows では `START-HERE.bat --port 8081` を使えます。

## 値と既定値

- parser は値を一つ受け取り、Python の `int` に変換します。数値でない値は `argparse` の解析エラーになります（`setup.py:8460,8553`）。
- `setup.py` にポート範囲の独自検証はありません。`0` も整数として解析されますが、後段の `a.port or ...` で偽値となるため、明示的な「OS に空きポートを割り当てさせる」指定にはなりません（`setup.py:8651,8382`）。
- 新規設定では省略時に `8080` が使われます。その値はモデル別 JSON の `port` に入り、生成される `run-<model>.sh` / `.bat` とセットアップ完了時の API URL にも使われます（`setup.py:8651,9597-9599,9729-9743`）。
- 既存モデルを通常起動するときに省略した場合、`start()` は設定 JSON の `port` を使い、JSON に値がなければ `8080` にフォールバックします（`setup.py:6737-6746,6775-6776,8677-8691`）。
- 通常起動で正の値を指定した場合、その起動の server command に渡されます。`start()` はこの `port` を設定 JSON に書き戻さないため、通常起動時だけの指定です（`setup.py:6745-6776`）。一方、セットアップで新しい設定を作る経路ではモデル別 JSON と起動スクリプトに反映されます（`setup.py:9597-9599,9729-9730`）。
- 新しい Strata フォルダーが前の設定を引き継ぐ場合、`--port` がなければ以前の設定の `port` を採用します。指定値があればそれが優先されます（`setup.py:8622-8635`）。

## 実行時の動作

通常起動では `setup.py` が `serve/server.py --engine strata --config <設定ファイル> --port <値>` を起動します。`--port` 省略時の値は `start()` が設定 JSON から選び、明示値はそのまま server の引数になります（`setup.py:6745-6776`）。server は socket の bind を試み、成功すると実際の待受 URL を表示します（`serve/server.py:7718-7722,8615-8623`）。

新規モデルのセットアップでは、選んだ値が JSON の `port` に保存されます。また `write_run_script()` が次回起動用の script に同じ値を含め、セットアップ完了表示にも API URL を出します（`setup.py:9597-9599,7260-7271,9729-9743`）。セットアップ中にベンチマークを選んだ場合も、その起動に同じポートを渡します（`setup.py:9761-9766`）。

適用経路には次の違いがあります。

- macOS の通常 setup は `setup.py` の共通 parser に入る前に `metal/setup_mac.py` へ引数を委譲します。そちらも `--port` を整数で受け付け、新規設定時は `a.port or 8080`、既存モデル起動時は設定値を server に渡します（`setup.py:8418-8419,7314-7318`、`metal/setup_mac.py:327-334,369-371,532-533,315-316`）。
- `--backend sycl` は共通 parser の後に `sycl/setup_intel.py` へ引数を転送します。転送先が `--port` を受け付けて適用するかは、この調査では確認できません（`setup.py:8561-8564,7321-7344`）。
- `--update` は更新処理を実行して終了します。`update_install()` は `a.port` を参照しないため、このモードでは `--port` は待受先を変更しません（`setup.py:8617-8619,6682-6709`）。
- `--calibrate` で既存モデルを調整してそのまま起動する経路では、明示した値が `start()` に渡ります。`--no-start` を付けると起動しないため、ポートは bind されません（`setup.py:8674-8676`）。

## 適用条件と副作用

ポートの利用可否は実行環境での socket bind に依存します。server はモデルの読み込み前に指定先の bind を試し、`OSError` の場合はポート使用中、権限、アドレス等に応じたエラーを `argparse` の usage error として報告します（`serve/server.py:144-160,8304-8308`）。範囲外の整数について `setup.py` 独自の検証や補正はなく、OS/socket 側の失敗を含む結果は値と環境に依存します。

セットアップ経路ではモデル別 JSON と起動用 script の書き込みを伴います。通常起動時の一時的な `--port` 指定は server process の待受先に作用しますが、設定 JSON の `port` は更新しません（`setup.py:6312-6347,6745-6776,9729-9730`）。

## 出力とエラー

- `--port` に整数として解釈できない値を渡すと、共通 parser の引数解析で失敗します（`setup.py:8460,8553`）。
- bind が成功すると server は `ready: http://...:<port>/v1` と chat page の URL を表示します（`serve/server.py:8615-8623`）。
- bind が失敗すると、server は失敗理由に応じた `cannot listen` または「port is already in use」の文を usage error として出します（`serve/server.py:144-160,8304-8308`）。
- 新規 setup の完了表示は指定ポートを含む OpenAI / Anthropic API URL です（`setup.py:9740-9743`）。

## 根拠

- 共通 parser、引数解析、設定引き継ぎ、通常起動分岐: `setup.py:8460,8553,8622-8635,8651-8691`
- 起動時の server command、設定値 fallback: `setup.py:6737-6776`
- 新規設定の port 保存、起動 script、完了表示: `setup.py:7260-7271,8381-8387,9597-9599,9729-9743,9761-9766`
- 設定書き込み処理: `setup.py:6312-6347`
- server 側 parser、bind、失敗・成功出力: `serve/server.py:144-160,7718-7722,8140-8156,8304-8308,8615-8638`
- macOS Metal の別 parser と起動: `setup.py:7314-7318,8418-8419`、`metal/setup_mac.py:315-316,327-334,369-371,532-533`
- update / SYCL 委譲: `setup.py:6682-6709,7321-7344,8561-8564,8617-8619`
- wrapper の委譲: `setup.sh:8-13`、`START-HERE.bat:27-34`、`SETUP.bat:1-2`、`update.sh:53-55`、`UPDATE.bat:79`
