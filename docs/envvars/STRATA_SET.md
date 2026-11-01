# `STRATA_SET`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Docker イメージの標準 entrypoint が読む環境変数です。値を空白区切りの `KEY=VALUE` 項目に分け、各項目を `strata launch --set KEY=VALUE` として渡します。`STRATA_SET` 自体を engine が読む実装は見つかりませんでした。通常の `strata launch` もこの名前を直接読みません。Docker entrypoint 経由で使う設定です。

## 値と判定

| 値 | entrypoint の扱い |
|---|---|
| 未設定または空文字 | `-n "${STRATA_SET:-}"` が偽になり、`--set` を追加しない。 |
| 空白だけ | 条件は真になるが、シェルの word splitting で項目ができない。`--set` は追加されないが、`have=1` となり既存 preset を保存する分岐に入る。 |
| 非空 | シェルの既定 `IFS` による word splitting 後、各項目に `--set` を一つずつ追加する。シェルの pathname expansion も適用される。値に空白を含めて一つの項目にする quoting や escape 処理はない。 |

各項目は CLI の `split_setting()` で最初の `=` だけを区切りとして分け、キーと値の前後空白を除きます。`=` がない項目も値が空の項目として受理されます。大文字を含む環境変数形式の名前（例: `STRATA_PIN_BY_NEED=1`）は環境設定として扱います。小文字の名前（例: `prefill=65536`）は CLI オプションとして扱い、アンダースコアはハイフンに変換します。空のキーや形式に合わない名前は無効です。数値や値域の検査は `STRATA_SET` 自体にも共通 parser にもなく、個々の設定先に委ねられます。

同じキーを複数回渡すと、`settings_from_pairs()` は後の値で前の値を置き換えます。Docker の値は空白分割されるため、たとえば `STRATA_SET='STRATA_X=1 STRATA_X=2'` は `STRATA_X=2` を残します。

## 有効になる条件

- `docker/entrypoint.sh` の標準サーバー起動経路で、engine の利用可否とデバイスを確認した後に読みます。`strata` など標準起動以外のコマンドを entrypoint に渡すと直接実行して終了するため、この変数は `--set` 化しません。
- この変数に固有の OS / GPU backend / build macro 条件はありません。entrypoint は利用可能な engine を確認し、その backend に応じたデバイス確認の後に同じ展開処理を通ります。個々の設定が有効かどうかは、この文書の対象外である各設定先の実装によります。
- 既存 preset がある場合、Docker は `--preset` を付け、何らかの設定入力があるときは `--save-preset` も付けます。CLI は preset を読み込んだ後に `--set` の値を `extra` にマージするため、同じキーは今回の `STRATA_SET` の値が preset の値を上書きします。複数の `--set` では後の項目が勝ちます。
- Docker の `MODEL`、`CONTEXT` などは別々の CLI 引数になり、`STRATA_SET` のキーと重なる設定についてコード上の一般的な優先順位は定義されていません。engine の具体的な引数・環境への反映は個別設定の処理によります。

## 実行時の詳細

entrypoint は起動するシェル内で `STRATA_SET` を参照します。プロセス内 cache はなく、起動時に一度展開して CLI 引数列を構成します。値が空でなければ、その設定入力があったことを示す `have=1` も設定します。最終的な起動コマンドは `launch --no-tui --access lan --port ... --data-dir ...` に追加引数を加えたものです。

CLI は `--set` を繰り返し受け付けます。大文字を含む環境名は `LaunchSettings.extra` に保存され、通常起動の設定組み立てでは `cfg["env"]` にマージされます。`off`、`unset`、`none`（大小文字を区別しない）は設定環境からそのキーを削除する指示として扱い、それ以外は文字列値として設定します。CLI で指定された extra は preset の extra より優先されます。`STRATA_SET` 自身を子プロセスへ転送する処理ではなく、分解後の項目が run 設定へ反映されます。

空の `STRATA_SET` は引数も `have` も作らないので、preset があればそのまま再利用します。非空だが空白だけの値は `have=1` によって preset 保存分岐に入りますが、`--set` 項目は作りません。

キー名の形式エラーなど CLI の `ValueError` は `strata: <理由>` として stderr に出て終了コード 2 になります。entrypoint は launch が非ゼロで終了すると phase を `failed` にし、`[X] strata launch stopped with code <終了コード> (the lines above say why). The container ends. Fix that and start it again: finished steps are not repeated, and an interrupted download continues where it stopped.` を stderr に出してコンテナを終了します。設定先が受け付けるかどうかの実行時エラーは、設定先のコードを個別に調べない限りここでは断定できません。

## 根拠

- 候補一覧に名前があること: `docs/envvars/000_envvers.md:1454-1455`（一覧は調査対象外の作業リポジトリ）。
- Docker entrypoint の説明、別コマンドを実行する分岐、値の存在判定、分割と `--set` 引数化: `docker/entrypoint.sh:24-26,53-56,169-171,225-226`。
- Docker 側の preset と追加設定時の保存指定、launch 起動・失敗処理: `docker/entrypoint.sh:242-250,273-290`。
- Docker 文書の値例と保存説明: `docs/DOCKER.md:108-134`。
- CLI の `--set` 定義、preset 読み込み、引数適用順、`extra` マージ: `strata_cli/launch/cmd.py:120-121,205-211,284-285,753-754`。
- キー・値の分割、形式検査、重複キーの後勝ち、環境設定値の扱い: `strata_cli/launch/settings.py:253-277,286-310`。
- CLI が環境設定を run config に反映する箇所: `strata_cli/launch/runner.py:557-563`; env の上書き・削除: `strata_control/tune_knobs.py:519-526`。
- 構文エラーの stderr と終了コード: `strata_cli/launch/cmd.py:692-697,913-916`。
- `STRATA_SET` の全参照を検索し、実装上の読み取りは `docker/entrypoint.sh:225` のみと確認。`docs/DOCKER.md` とテストコードには説明・fixture 参照があるが、追加の読み取り実装ではない。
