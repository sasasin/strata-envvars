# `FAMILY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`FAMILY` は Docker コンテナの標準起動経路でモデルファミリーを指定する入力です。Strata の実行ファイルが環境変数 `FAMILY` を直接読む箇所は見つかりません。`tools/docker/entrypoint.sh` が値を `strata launch --family VALUE` に変換し、`strata launch` の CLI がモデルサイズの解決または保存済み preset のファミリー指定に使います。任意のコマンドをコンテナ引数で起動した場合は entrypoint の標準起動処理を通らず、この変換はありません（`tools/docker/entrypoint.sh:68-71, 184-185, 213-215`）。

## 値と判定

| 条件 | 未設定 | 有効になる値（例） | 無効・未適用の値（例） |
|---|---|---|---|
| Docker entrypoint の標準起動 | `FAMILY` が未設定または空文字なら `--family` を追加しない。ファミリー選択を指定しない状態で後続処理へ進む | 空白以外を含む文字列はそのまま `--family` の値として渡す。たとえば `qwen`、`qwen36`、`hy4-flash`、`inkling-2-mini` | 空白だけの値も非空なのでそのまま渡る。entrypoint は trim、大小文字変換、値の検証をしない（`tools/docker/entrypoint.sh:213-215`） |
| `strata launch` の CLI 解決 | `--family` がなければ、`--model` はカタログ上のファミリーから解決される。複数候補時は `qwen` があればそれを選び、なければ先頭候補 | カタログにあるファミリー名とモデルサイズの組み合わせ。`--model` と共に指定した場合、モデルサイズは大小文字を区別せず解決し、指定ファミリーがそのサイズを提供する必要がある | 知らないファミリー、またはそのファミリーが提供しないサイズは拒否される。空白や大文字小文字を自動補正しない（`terminal/strata_cli/launch/catalog.py:550-572`） |

`FAMILY` の判定自体は文字列全体の比較や数値変換ではなく、entrypoint の `[ -n ... ]` による空文字判定です。未設定と空文字は同じく省略されます。値に trim や大小文字変換はありません。受理されるファミリー名はモデルカタログにより決まり、固定の環境変数専用リストではありません（`tools/docker/entrypoint.sh:213-215`, `terminal/strata_cli/launch/catalog.py:550-572`）。

## 有効になる条件

- Docker の標準起動経路であること。`docker run IMAGE strata ...`、`docker run IMAGE sh` など任意コマンド経路では entrypoint は `exec` で抜けるため、`FAMILY` を CLI 引数へ変換しません（`tools/docker/entrypoint.sh:68-71`）。
- `FAMILY` が空でないこと。未設定・空文字では CLI オプションを付加しません（`tools/docker/entrypoint.sh:213-215`）。
- ファミリー名が CLI のモデルカタログに存在し、指定した `MODEL` がある場合はそのファミリーで提供されていること（`terminal/strata_cli/launch/catalog.py:550-569`）。
- 新規の非対話 Docker 起動では、ファミリーだけを指定してもモデル選択には足りません。entrypoint は `MODEL` も preset もなく `--no-tui` で起動するため、CLI は `--family` を「選択あり」と数えず失敗します（`terminal/strata_cli/launch/cmd.py:849-862`）。
- 保存済み `PRESET` を指定する起動では preset が基礎設定となり、コマンドライン指定が上書きします。`FAMILY` があり `MODEL` がない場合、既存 preset にモデルがあればファミリーだけを置き換えます。サイズとファミリーの不一致は後続のモデル状態確認でエラーになります（`terminal/strata_cli/launch/cmd.py:215-239`; `tools/docker/entrypoint.sh:268-275`）。

## 実行時の詳細

entrypoint は標準起動時に `FAMILY` を一度シェル展開し、空でなければ `--family` と値を別々の引数として追加します。値をプロセス内キャッシュする処理や、実行中に再読込する処理はありません。変更は次のコンテナ起動時に反映されます。環境値は `strata launch` の子プロセスへ環境変数のまま渡すのではなく、CLI 引数として渡されます（`tools/docker/entrypoint.sh:184-185, 213-215, 295-308`）。

CLI は preset の値を読み込んだ後、`--model` があれば指定ファミリーと合わせてカタログで解決します。`--model` がなく、既存 preset にモデルがある場合は `--family` で preset のファミリーを上書きします。新規起動で `FAMILY` だけを渡した場合、`settings_from_args` はファミリーだけの設定を作らず、`--no-tui` かつ非対話のため「何を起動するか指定されていない」として終了します（`terminal/strata_cli/launch/cmd.py:215-239, 849-862`）。

ファミリーとサイズが解決されると、カタログのモデル行・モデル名・モデルフォルダーの選択に用いられ、Runner がその組み合わせを使ってモデル状態を確認しセットアップ／起動を進めます（`terminal/strata_cli/launch/catalog.py:550-584`; `terminal/strata_cli/launch/runner.py:1571-1585, 1666-1695`）。

## ログと測定値

entrypoint は `MODEL` が非空なら `Starting Strata: [FAMILY/]MODEL ...` を出力します。`MODEL` が空で model path もない場合は `Starting Strata: the recommended model ...` と表示し、FAMILY 名をこの行に含めません（`tools/docker/entrypoint.sh:299-303`）。

`--model` と一緒に指定された無効なファミリー名や、サイズとの不一致は `Catalog.resolve` が `ValueError` にします。未知の名前では `There is no model family called '...'.`、組み合わせ違いでは `... has no size ...` のエラー文になります。CLI はこのエラーを stderr に `strata: ...` と出して終了コード 2 で返します（`terminal/strata_cli/launch/catalog.py:560-568`; `terminal/strata_cli/launch/cmd.py:753-764, 1011-1012`）。Docker entrypoint は `strata launch` が非ゼロ終了すると `strata launch stopped with code ...` を stderr に出してコンテナを終了します（`tools/docker/entrypoint.sh:310-316`）。

## 根拠

- `tools/docker/entrypoint.sh:68-71` — 標準起動以外のコマンド処理。
- `tools/docker/entrypoint.sh:184-215` — 起動引数の作成と `FAMILY` の読み取り・転送。
- `tools/docker/entrypoint.sh:268-275, 299-316` — preset の指定、開始表示、終了経路。
- `terminal/strata_cli/launch/cmd.py:215-239, 838-862` — preset と引数の合成、新規非対話起動の判定。
- `terminal/strata_cli/launch/catalog.py:550-572` — ファミリーとモデルサイズの検証・解決。
- `terminal/strata_cli/launch/runner.py:1571-1585, 1666-1695` — 解決したファミリー・サイズによるモデル状態確認と準備。
