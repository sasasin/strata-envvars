# `--components-dir`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント保存先ディレクトリのパス（文字列） |

## 役割

エンジン package のインストール先となる Strata コンポーネントのルートディレクトリを指定します。指定しない場合は、`STRATA_COMPONENTS_DIR` またはプラットフォーム別のユーザー領域が使われます。

## 使い方

```sh
strata components install-file ./strata-engine.tar.gz --components-dir /srv/strata/components
```

`install-file` は位置引数 `file` でローカル package を受け取ります。`--components-dir` はそのファイルの場所ではなく、インストール先のルートを指定します。

## 値と既定値

parser は値を文字列として受け取り、`default=None` です。パスの存在・絶対パス性・書き込み権限を parser 段階では検証しません。相対パスも parser では拒否されず、後続の `Path` 操作でプロセスの作業ディレクトリを基準に扱われます。明示値が空文字列の場合も `if a.components_dir` の判定を通らないため、未指定と同じ既定ルートになります。

明示値を省略すると `engine_component.components_dir()` が使われます。環境変数 `STRATA_COMPONENTS_DIR` が空でない場合はその値が優先されます。そうでなければ Windows は `%LOCALAPPDATA%\Strata\components`（`LOCALAPPDATA` がなければホーム以下）、その他の OS は `$XDG_DATA_HOME/strata/components`（未設定なら `~/.local/share/strata/components`）です。

## 実行時の動作

`run()` は明示値を `Path` に変換して updater context の `components` に設定し、その context を `install_engine_file()` に渡します。この値の下に `.updates` の状態・排他 lock・一時 staging を置き、成功時は `engine/<version-platform-backend>/` 以下へ package を配置します。従って既存の別のコンポーネント領域を指定すると、そちらのエンジンや update state が対象になります。

インストール処理は package ファイルを展開し、署名と manifest 記載の全ファイルを検査し、この PC に適合するか確認してから test-start と切り替えを行います。前の engine は rollback 用に保持されます。入力 package 自体は削除されません。`--components-dir` は install-file 分岐で保存先 root として使われ、feed の選択には使われません。

同じ parser に共通 option として `--wait`、`--force`、`--model-config`、`--feed`、`--backend`、`--output` も登録されます。このコマンドでは `--feed` は install-file 分岐で参照されません。`--force` は既存 engine より古い package を拒否する比較を通過させます。`--backend` は hardware 判定値を上書きし、package 適合性判定に影響します。`--wait` は engine 使用中に待つ時間に関係し、`--model-config` は test-start に使う run config です。さらに CLI 共通処理が `--json` と `--quiet` をこの one-shot parser に追加します。

## 適用条件と副作用

保存先には `.updates/update.lock` を作成して同じコンポーネント領域への同時更新を防ぎます。領域が存在しなければ必要なディレクトリを作成します。インストールに失敗した場合も途中 staging は通常削除されます。package は展開・検証・test-start されるため、この操作は読み取り専用ではありません。

この option のパス検証は明示実装されていません。ディレクトリを作成できない、容量が足りない、lock を取れない場合などはインストールが失敗します。package は `.tar.gz`、`.tgz`、`.tar.xz`、`.zip` の拡張子を認識しますが、parser の位置引数ヘルプは `.tar.gz` または `.zip` とだけ説明しています。

## 出力とエラー

成功時は既定の human 出力で進捗・結果を stdout に表示します。`--output json` / `--json` では結果を JSON で出力し、`--output jsonl` はイベント出力モードですが、install-file の最終結果自体は JSON を出力します。失敗は既定で `strata: ...` を stderr に出し、機械可読出力時は JSON の error object を stdout に出します。

ソースで確認できる代表的な失敗は、指定ファイルがない・非対応形式・読めない package・署名またはファイル整合性エラー・この PC に適合しない package で終了コード 5、同じ領域の updater lock 競合で 7、test-start が失敗して旧 engine が維持される場合に 6 です。古い package は `--force` なしでは「現在の engine の方が新しい」として変更せず成功扱いになります。

## 根拠

- parser と共通 option: `strata_cli/update_cmd.py:30-39, 57-62`
- `--json` / `--quiet` の追加: `strata_cli/cli.py:508-516`
- option の値を root にする処理と install-file の呼び出し・出力: `strata_cli/update_cmd.py:174-217`
- option 未指定時の環境変数・OS 別既定パス: `strata_control/engine_component.py:176-190`
- `.updates` lock の作成と競合時の終了コード: `strata_control/updater.py:135-168`
- package 展開、検査、適合性判定、古い版の扱い、install finish: `strata_control/updater.py:1080-1148`
- test-start 後の切り替え、旧版保持、失敗時の復帰: `strata_control/updater.py:994-1077`
- コマンド dispatch: `strata_cli/cli.py:2135-2137`
