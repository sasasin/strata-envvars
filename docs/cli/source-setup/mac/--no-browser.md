# `--no-browser`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` から Apple Silicon の macOS で委譲） |
| オプション | `--no-browser` |
| 別名 | なし |
| 値 | 値を取らないフラグ。未指定時の parser 値は `None` |

## 役割

Metal engine を起動するときに、サーバーが準備できた後のブラウザー自動起動を抑止します。対象は `metal/setup_mac.py` の parser です。macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない `setup.py` は、独自 parser を動かす前に全引数をこのスクリプトへ渡します（`setup.py:82,7703-7707,9068-9069`、`metal/setup_mac.py:327-358`）。

## 使い方

Apple Silicon Mac の Strata checkout ルートで `setup.py` / wrapper 経由で使う例です。

```sh
./setup.sh --no-browser
```

既存モデル設定の起動時は現在の起動だけに適用されます。セットアップを実行して設定へ保存する例:

```sh
./setup.sh --setup --no-browser
```

`setup.sh` は Python 環境を確認・用意してから `setup.py` を実行し、Darwin の通常経路は `metal/setup_mac.py` に委譲します。直接呼び出す場合は `python3 metal/setup_mac.py --no-browser` です（`setup.sh:7-13,39-50`、`setup.py:9068-9069`）。

## 値と既定値

値は不要で、型変換・値域 validation はありません。parser は `dest="browser"`、`action="store_false"`、`default=None` として登録され、指定時は `a.browser` が `False` になります（`metal/setup_mac.py:327-356`）。`--no-browser yes` のように続けて値を付ける構文ではありません。ただし Mac parser は `parse_known_args()` を使うため、`yes` は未知引数として警告され、通常は処理が続きます（`metal/setup_mac.py:356-358`）。

## 実行時の動作

- 既存の Mac 設定があり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていないと、選択済み設定をそのまま起動します。この経路では `--no-browser` を `start()` の引数として渡し、設定ファイルは書き換えません。次回起動にも抑止を残すには設定を作り直す必要があります（`metal/setup_mac.py:369-371`）。
- セットアップでモデル設定を生成する経路では、指定時に `cfg["open_browser"] = False` を設定ファイルへ保存し、生成する `run-<model>.sh` にもブラウザーを開く `--open` 引数が付かない形で反映します（`metal/setup_mac.py:542-570`、`setup.py:7647-7650`）。`--no-start` と併用すると設定と起動スクリプトは保存されますが、その場では server を起動しません（`metal/setup_mac.py:557-570`）。
- 起動時は `start()` が `serve/server.py --engine strata --config ...` を子プロセスとして呼びます。`--no-browser` 指定または config の `open_browser: false` の場合に `--open` を付けず、それ以外なら付けます。設定ファイルの値も `False` なら、フラグ未指定であってもブラウザーは開きません（`metal/setup_mac.py:302-323`）。
- このオプションはブラウザー起動だけを制御します。設定生成、モデル取得や engine 準備、server 起動を省略するものではありません。server は準備完了時に API URL とチャット画面 URL を表示し、その後 `--open` と config 値の条件を満たす場合だけブラウザーを開きます（`metal/setup_mac.py:542-570`、`serve/server.py:9490-9494,9511-9516`）。

## 適用条件と副作用

この scope は Apple Silicon 用の Metal セットアップ経路です。Control mode（`STRATA_CONTROL_INSTALL=1`）では `setup.py` が Mac standalone parser に委譲しないため、この文書の parser は使われません（`setup.py:82,9068-9069`）。

フラグ単独に設定ファイルの副作用はありません。設定を生成する経路で明示した場合はモデル別 JSON と起動スクリプトを書き込みます。通常の既存設定起動では設定を書き換えず、当該起動の server 引数だけを変えます（`metal/setup_mac.py:369-371,557-570`）。

## 出力とエラー

`--no-browser` 固有の validation、警告、失敗処理はありません。余分な未知引数があれば `not used on a Mac: ...` の警告を出して続行します（`metal/setup_mac.py:356-358`）。設定参照先の実行ファイルや GGUF が見つからない場合、またはモデル repack が実行中の場合は、`start()` が通常の setup エラーを出し server を起動しません。これらはこのオプション固有の失敗ではありません（`metal/setup_mac.py:302-323`）。ブラウザーを開かない場合も起動案内は表示され、server 子プロセスの終了コードが返されます（`metal/setup_mac.py:319-323`）。

## 根拠

- parser 宣言、未知引数の扱い: `metal/setup_mac.py:327-358`
- 既存設定の通常起動分岐: `metal/setup_mac.py:369-371`
- server 起動引数とファイル・repack 検査: `metal/setup_mac.py:302-323`
- 新規設定への保存、run script 作成、`--no-start` 分岐: `metal/setup_mac.py:542-570`
- run script の `--open` 付与条件: `setup.py:7647-7650`
- macOS の委譲条件と子プロセス起動: `setup.py:82,7703-7707,9068-9069`
- server の準備完了時の URL 表示とブラウザー起動条件: `serve/server.py:9490-9494,9511-9516`
- 索引上の所属とリンク: `docs/cli/README.md:1594-1619`

調査は上記 commit の parser・分岐・起動処理を対象にしました。CLI help の実行、Release artifact、および実機のブラウザー起動結果は確認していません。
