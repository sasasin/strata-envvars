# `MODEL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Docker entrypoint が起動時のモデルサイズを受け取り、値が空でなければ `strata launch --model <値>` に渡す。モデル選択を実行するのは Terminal CLI であり、エンジンが `MODEL` 環境変数を直接読む実装は確認できない。通常のコンテナ起動（引数なし、`run` または `serve`）で使う。`strata` や `sh` など別コマンドを指定すると entrypoint はそのコマンドを直接実行するため、`MODEL` は適用されない。`tools/docker/entrypoint.sh:1-7,68-71,184-210`

## 値と判定

entrypoint は `[ -n "${MODEL:-}" ]` で未設定・空文字を同じく「モデル指定なし」と判定する。非空なら文字列をそのまま一つの `--model` 引数にする。entrypoint 自体は数値化・小文字化・空白除去・値域検査をしない。`tools/docker/entrypoint.sh:209`

| `MODEL` の値 | entrypoint の処理 | CLI 側の結果 |
| --- | --- | --- |
| 未設定、空文字 | `--model` を付けない | `MODEL_PATH` も未指定なら、preset がある場合はそのモデルを使う。preset がなくても `MODEL_PATH` がなければハードウェア向け推奨モデルを選ぶ。`MODEL_PATH` が指定されれば preset のモデルをクリアして自前ファイルを使う。`tools/docker/entrypoint.sh:191,209,264-271`; `terminal/strata_cli/launch/cmd.py:219-238,344-356` |
| `IQ3_XXS`、`iq3_xxs` などカタログ上のサイズ名 | そのまま `--model` に渡す | カタログ名との大文字小文字を区別しない完全一致で解決する。`terminal/strata_cli/launch/catalog.py:550-572` |
| `0`、`1`、`true`、`false`、`0anything` など | すべて非空なので `--model` に渡す | 真偽値や数値としては解釈せず、モデル名として解決する。カタログにない名前は無効。`terminal/strata_cli/launch/catalog.py:550-559` |
| 前後に空白を含む名前 | 空白を含めたまま渡す | CLI の名前照合でも trim はなく、照合対象名と一致しなければ無効。`terminal/strata_cli/launch/catalog.py:550-559` |

`--model` が使える名前は、実行時のモデルカタログと既存モデルのサイズ名による。未知名は CLI が `There is no model called '<値>'.`（候補があれば `Did you mean ...?` と一覧も付く）で失敗する。`FAMILY` が同時に指定されればその family 内でサイズを照合し、該当サイズがなければ別のエラーになる。family が省略され同じサイズが複数 family にあれば `qwen` を優先し、それ以外は最初の候補を使う。`terminal/strata_cli/launch/catalog.py:550-572`; Docker からの `FAMILY` 転送は `tools/docker/entrypoint.sh:209-211`。

## 有効になる条件

- Docker の通常起動経路であること。entrypoint に `strata …`、`sh` など別コマンドを渡すと直接 `exec` し、`MODEL` を `--model` に変換しない。`tools/docker/entrypoint.sh:68-71,209`
- `MODEL` の非空値が、起動時の Terminal カタログで解決できるモデルサイズであること。サイズが複数 family に属する場合は `FAMILY` で絞れる。`terminal/strata_cli/launch/catalog.py:550-572`
- モデルの取得・準備・起動が完了するには、選択モデルに合うカタログ、モデルファイル、engine/backend 等が必要。`MODEL` 自体に OS / backend 判定はない。解決後は通常の `Runner` が engine 確保、モデル確保、設定保存、serve 起動へ進む。`terminal/strata_cli/launch/cmd.py:876-902`; `terminal/strata_cli/launch/runner.py:3141-3187`
- `PRESET` が既に存在し `MODEL` が未設定なら、entrypoint は `--preset` を渡すため、preset に保存されたモデルが使われる。`MODEL` が非空なら同じ preset を読み込んだ後に `--model` の指定が適用され、`--save-preset` も渡される場合は更新後の選択が保存される。`tools/docker/entrypoint.sh:264-268`; `terminal/strata_cli/launch/cmd.py:215-238`
- `MODEL_PATH` は別設定で、未設定の `MODEL` の代替として使える。`MODEL_PATH` があるときは自前ファイルのモデルを使い、未設定のサイズを推奨モデルで埋めない。両方指定したときはモデルサイズとパスの両方が CLI に渡る。`tools/docker/entrypoint.sh:191-211`; `terminal/strata_cli/launch/cmd.py:222-238,344-356`

## 実行時の詳細

entrypoint は子プロセスを起動する前に環境値を参照し、argv の組み立てと開始ログの作成で展開する。環境値を cache する実装はなく、CLI が受け取った後は `--model` 引数で処理される。親プロセス側の値を変えても起動済みコンテナの環境は変化しないため、変更はコンテナ再起動後に反映される。選択値がある開始ログは `Starting Strata: $what (preset '$PRESET').`（`$what` は `FAMILY/MODEL`、必要なら ` from MODEL_PATH` 付き）。`tools/docker/entrypoint.sh:209,293-306`

`--model` を受けた CLI は preset を初期設定として読み込んだあと、`catalog.resolve()` でモデル名と任意の `FAMILY` を解決して設定を上書きする。選択結果は `Runner` のモデル準備・設定保存・サーバー起動に使われる。モデル名が無効なら `run_launch()` がエラー文字列を stderr に出して終了コード `2` を返し、Docker entrypoint は `strata launch stopped with code 2 (the lines above say why). The container ends...` として失敗終了する。`terminal/strata_cli/launch/cmd.py:215-238,753-764,876-902,1009-1014`; `terminal/strata_cli/launch/catalog.py:550-572`; `tools/docker/entrypoint.sh:300-312`

未設定時、preset がなく `MODEL_PATH` もなければ CLI の `apply_defaults()` はハードウェア向け推奨モデルを設定する。推奨できない場合はエラー notice を返す。`MODEL_PATH` の有無や preset の内容により未設定時のモデル選択が変わるため、「未設定なら常に推奨モデル」とはならない。`terminal/strata_cli/launch/cmd.py:219-238,344-356`

Compose の NVIDIA / AMD / Intel 定義はいずれも `${MODEL:-}` をコンテナの `MODEL` に設定するため、Compose ホストで未設定なら空値となる。これは受け渡しであり、各 backend ごとの別の `MODEL` 判定はない。`tools/docker/compose/docker-compose.nvidia.yml:16-19`; `tools/docker/compose/docker-compose.amd.yml:16-18`; `tools/docker/compose/docker-compose.intel.yml:16-18`

`app/host/scripts/agent-flow.mjs` などのブラウザフロー用スクリプトにも `process.env.MODEL` があるが、これは画面上のモデル picker を選ぶ自動操作の入力であり、Strata アプリのモデル設定を読む実装ではない。ソース全体の `MODEL` 参照を確認した範囲で、通常実行時の環境値読み取りは Docker entrypoint に限られ、engine や Terminal 側の env helper を介した別の `MODEL` 読み取りは確認できなかった。`app/host/scripts/agent-flow.mjs:15,31,68-70`

## ログと測定値

モデル値があれば entrypoint は `Starting Strata: $what (preset '$PRESET').` を stdout に出す。未設定で preset も entrypoint の選択設定もない場合、entrypoint は stderr に `[!] No MODEL was set, so Strata picks the model it recommends for this card. Set MODEL (for example MODEL=IQ3_XXS) to choose.` を出す。未設定時、CLI の推奨モデル通知文は `No model was named, so Strata picked {title} for this computer ({why}).`。`tools/docker/entrypoint.sh:52-54,270,295-300`; `terminal/strata_cli/launch/cmd.py:344-356`

無効なモデル名は CLI が `strata: There is no model called '<値>'.`（必要に応じて候補名と `Models: ...` が続く）を stderr に出して終了コード `2` を返す。entrypoint はその後 `strata launch stopped with code $rc (the lines above say why). The container ends. Fix that and start it again: finished steps are not repeated, and an interrupted download continues where it stopped.` を出して同じ終了コードで失敗する。`terminal/strata_cli/launch/cmd.py:753-764,1009-1014`; `terminal/strata_cli/launch/catalog.py:550-559`; `tools/docker/entrypoint.sh:300-312`

## 根拠

- `tools/docker/entrypoint.sh:1-7,68-71,184-210,264-312`
- `tools/docker/compose/docker-compose.nvidia.yml:16-19`; `tools/docker/compose/docker-compose.amd.yml:16-18`; `tools/docker/compose/docker-compose.intel.yml:16-18`
- `terminal/strata_cli/launch/cmd.py:215-238,344-356,753-764,876-902,1009-1014`
- `terminal/strata_cli/launch/catalog.py:550-572`
- `terminal/strata_cli/launch/runner.py:3141-3187`
