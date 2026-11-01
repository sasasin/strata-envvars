# `MODEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 本体の C++/CUDA/HIP/SYCL エンジンが直接読む環境変数ではありません。Strata の Docker entrypoint がコンテナ起動時に値を `strata launch --model <値>` に変換し、起動するモデルサイズを指定します。NVIDIA / Intel / AMD の各 Compose 定義がホストの `MODEL` をコンテナへ渡します。また、host アプリのブラウザー操作用スクリプトでは、モデル選択メニューから選ぶ表示名の指定に使われます。

## 値と判定

| 経路 | 未設定・空文字 | 値がある場合 | 無効な値 |
|---|---|---|---|
| Docker entrypoint | 未設定と空文字は同じ扱い。`--model` を付けず、モデルも `MODEL_PATH` も指定されていなければ、Strata CLI がこのコンピューター向けの推奨モデルを選ぶ。保存済み preset があればその設定が使われる | 値全体を `--model` の引数として渡す。小文字・大文字を区別しないカタログ上のモデル名が受け付けられる | カタログにない名前は CLI が拒否する。`MODEL` 自体に trim、部分一致、真偽値化、fallback はない |
| host のブラウザー操作スクリプト | JS の `??` により未設定時だけスクリプトごとの既定表示名を使う。明示した空文字は空文字のまま | 値を `new RegExp(MODEL)` に渡し、最初に一致するモデル選択メニュー項目をクリックする | 事前検証や空文字 fallback はない。一致項目がない場合は UI 操作が成立せず、スクリプト実行が失敗する |

Docker 経路では `MODEL=0` も Boolean の false ではなく、文字列 `0` のモデル名として検索されます。先頭文字・数値・大文字小文字を使った特別な判定はありません。モデルサイズが複数の family に存在する場合は、別変数 `FAMILY` が選択を補います。Compose の `${MODEL:-}` は未設定または空値を空値としてコンテナへ渡します。

## 有効になる条件

- Docker 経路は entrypoint を通常起動した場合に有効です。コンテナへ `strata ...`、`sh` などのコマンドを指定すると entrypoint は直接そのコマンドを実行し、設定変数からの `strata launch` 組み立てには入りません。
- NVIDIA / Intel / AMD 各 Compose 定義で `MODEL` をコンテナ環境に転送します。モデル名の解決は起動した Strata CLI のモデルカタログに依存します。
- CLI の `--preset` は preset を読み込んだ後に引数を重ねます。非空の `MODEL` から作られた `--model` は preset のモデル選択を上書きします。空の `MODEL` は `--model` を作らないため、preset の既存モデル選択を保ちます。preset にモデルがなく、`MODEL_PATH` もない場合に推奨モデル選択へ進みます。
- host アプリの読み取りは `apps/host/scripts/agent-flow.mjs`、`agent-flow-s4b.mjs`、`agent2-flow.mjs`、`agent2-tools-flow.mjs`、`mode-flow-s4b.mjs` の UI 自動操作専用です。Strata サーバーや推論エンジンの設定には転送されません。

## 実行時の詳細

Docker entrypoint は起動時に `MODEL` の非空判定を行い、値があれば引数配列へ `--model "$MODEL"` を追加します。値を追加したことは「設定あり」として記録され、preset の起動に使われます。開始ログは設定値があれば `Starting Strata: <MODEL> ...`、なければ model path または推奨モデルの文言になります。値が空で preset もなく model path もないときは `No MODEL was set, so Strata picks the model it recommends for this card...` を stderr に出します。Compose と entrypoint のこの判定はコンテナ起動時の処理で、稼働中に環境変数を書き換えても再評価されません。

CLI は `--model` を preset に重ねて設定へ反映し、カタログ上のモデル名と大文字小文字を無視して照合します。名前が見つからない場合は `There is no model called '<値>'.`（近い候補があれば提案を追加）を `strata:` エラーとして stderr に出し、終了コード 2 を返します。Docker entrypoint は `strata launch` の非ゼロ終了を `strata launch stopped with code <終了コード> (the lines above say why). The container ends.` と報告し、コンテナを終了します。モデルがカタログ上で有効でも、ハードウェア適合性の警告など別の起動条件は CLI が別途判定します。

ブラウザー操作スクリプトはプロセス開始時に `process.env.MODEL` を定数へ読み込み、モデルメニューを開いた後にその正規表現へ最初に一致する項目を選びます。通常の環境変数の再設定を監視する処理はありません。

## 根拠

- Docker entrypoint の起動コマンド分岐と環境読み取り: `docker/entrypoint.sh:53-56,169-194,242-250,273-290`。
- NVIDIA / Intel / AMD Compose からの転送: `docker/compose/docker-compose.nvidia.yml:16-19`, `docker/compose/docker-compose.intel.yml:15-18`, `docker/compose/docker-compose.amd.yml:15-18`。
- CLI の `--model` 定義と preset への上書き: `strata_cli/launch/cmd.py:83-89`, `strata_cli/launch/cmd.py:205-224`。
- モデル名の大文字小文字を無視した完全一致、無効名エラー: `strata_cli/launch/catalog.py:373-401`。CLI のエラー出力・終了コード: `strata_cli/launch/cmd.py:692-697,913-916`。
- 未指定時の推奨選択と通知: `strata_cli/launch/cmd.py:321-333`。
- Docker entrypoint が CLI の失敗を受けてコンテナを終了: `docker/entrypoint.sh:283-290`。
- ブラウザー操作スクリプトでの既定値とメニュー選択: `apps/host/scripts/agent-flow.mjs:27-33,63-70`, `apps/host/scripts/agent-flow-s4b.mjs:20-30,86-92`, `apps/host/scripts/agent2-flow.mjs:19-26,65-70`, `apps/host/scripts/agent2-tools-flow.mjs:18-24,64-71`, `apps/host/scripts/mode-flow-s4b.mjs:8-12,21-26`。
