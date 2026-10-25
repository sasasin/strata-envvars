# `--browser`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。調査対象 checkout の状態は `main`、未コミット変更なし。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから起動） |
| オプション | `--browser` |
| 別名・対になる指定 | `--no-browser`（同じ `browser` 引数を反転して設定） |
| 値 | 値を取らないフラグ |

## 役割

モデルの起動準備ができたとき、ローカルのチャットページをブラウザで開く設定を有効にします。通常は既定で開くため、主に以前 `--no-browser` で保存した設定を再び有効にするときに使います。parser は両フラグを同じ `browser` 宛てに登録し、`--no-browser` は `False`（未指定時 `None`）、`--browser` は `True` を設定します（`setup.py:8476-8480`）。

## 使い方

既にモデルを設定済みの checkout で起動時に有効化する例:

```sh
./setup.sh --browser
```

Windows では同じ引数を `START-HERE.bat --browser` に渡せます。`setup.sh` は引数を `setup.py` に転送し（`setup.sh:76`）、`START-HERE.bat` も選択した Python で `setup.py %*` を実行します（`START-HERE.bat:44-54`）。

## 値と既定値

値は不要です。`--browser` と `--no-browser` を両方指定した場合、parser は同一の宛先を引数順に更新するため、後に現れた方の値になります（定義: `setup.py:8476-8480`）。値を付けて呼ぶ構文ではありません。

引数を省略すると `browser` は未指定のままです。既存モデルの通常起動では未指定値では保存済み設定を書き換えず、設定が `open_browser=false` でなければブラウザを開きます。新規・再構成時も、明示値がない場合は既存の `open_browser` 設定が引き継がれ、設定キーがない新規構成ではブラウザを開く側に動きます（`setup.py:6177-6188, 6326-6340, 9675-9676, 6844-6846`）。

## 実行時の動作

既存モデルの起動経路では `--browser` が明示された場合、その値を `start()` の `keep` に渡します（`setup.py:8674-8692`）。`_start()` は既存の JSON 設定を読み、値が変わると `open_browser` を更新して設定ファイルへ保存します（`setup.py:6745-6771`）。その後、起動コマンドに `serve/server.py` を組み立て、ブラウザを開く条件を満たすと `--open` を追加します（`setup.py:6775-6776, 6844-6846`）。

インストール・再設定経路では明示値をモデルの設定 JSON に書き、`write_run_script()` が生成する `run-<model>.sh` / `.bat` にも `--open` を含めます（例: `setup.py:7689-7690, 7717-7719, 7260-7272`）。`--no-start` でセットアップだけを行う場合は、その場ではモデルを起動しません（`setup.py:9759-9766`）。次回以降の起動設定には値が残ります。再セットアップで明示指定しない場合も `open_browser` は setup が書き換えないキーとして引き継がれます（`setup.py:6162-6167, 6177-6188`）。

server は `--open` があり、かつ設定 JSON の `open_browser` が `false` でない場合に限り、準備完了後に `webbrowser.open()` を daemon thread で呼び出します。URL は localhost 側のモデルページで、起動関数の戻り値は確認していません（`serve/server.py:8639-8644`）。従って保存設定の `false` は、古い起動スクリプトが `--open` を含んでいても優先されます。

## 適用条件と副作用

- この option は `setup.py` の共通 parser が使われる Windows / Linux および Control mode の構成経路で有効です。Apple Silicon の standalone 経路は `setup.py` から `metal/setup_mac.py` に parser 前に委譲されます（`setup.py:8412-8420`）。その parser には `--no-browser` はありますが `--browser` はなく、未知引数は警告付きで無視されるため、standalone Mac ではこの文書の `--browser` は有効化指定になりません（`metal/setup_mac.py:327-359`）。
- Intel SYCL 経路では共通 parser の後に `sycl_setup()` が別スクリプトを呼びます。委譲側で `--browser` をどう扱うかはこの調査では確認できず、SYCL での保存・起動効果は断定しません（`setup.py:8561-8564, 7321-7344`）。
- 設定変更時はモデル別 JSON が書き換わります。既存ファイルとの差分がある再セットアップでは `.bak` を作ろうとします（`setup.py:6333-6340`）。生成される起動スクリプトも更新されます（`setup.py:7260-7272`）。
- ブラウザ起動はモデルの server 起動後、準備完了の経路で非同期に試みます。ブラウザが利用できない場合の具体的な挙動や OS ごとの launcher 差は、このソース確認だけでは確定できません。`webbrowser.open()` の戻り値を Strata は検査していません（`serve/server.py:8639-8644`）。

## 出力とエラー

このオプション専用の値検証やエラー処理はありません。値を要しない boolean flag として定義されています（`setup.py:8476-8480`）。セットアップ時の設定保存や backup 作成に失敗した場合は共通の書き込み・警告経路に従い、ブラウザ launcher の成否は待機・終了コードへ反映されません（`setup.py:6333-6340, 6872-6878`; `serve/server.py:8639-8644`）。

## 根拠

- parser と説明文: `setup.py:8476-8480`
- 既存モデル起動時の明示値保存と起動コマンド生成: `setup.py:6745-6776, 6844-6846, 8674-8692`
- モデル設定の引き継ぎ・保存・backup: `setup.py:6162-6188, 6312-6340, 9675-9676`
- セットアップ後の起動スクリプトと `--no-start`: `setup.py:7260-7272, 7689-7719, 9759-9766`
- server でのブラウザ起動: `serve/server.py:8175-8177, 8639-8644`
- wrapper の引数転送: `setup.sh:76`, `START-HERE.bat:44-54`
- standalone Mac の別 parser: `setup.py:8412-8420`, `metal/setup_mac.py:327-359`
- SYCL 委譲: `setup.py:7321-7344, 8561-8564`
