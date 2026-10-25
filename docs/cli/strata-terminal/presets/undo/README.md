# `strata presets undo`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets undo` |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py` |
| 引数 | `preset`（必須。preset 名・ID/ID prefix または slot key。`--config` 使用時も構文上必須） |

## 役割

指定した tuning preset の slot について、直前に有効だった preset に戻します。履歴に戻り先がなく現在の preset だけが有効なら、その slot を標準設定に戻します。preset 自体を削除する操作ではありません。

この操作は有効 preset の記録を切り替えるもので、実行中のモデルやエンジンを再起動しません。保存済みの有効 preset は、対応する設定でモデルを次回起動するときに適用されます。

## 使い方

```sh
# 指定 preset が属する slot の有効状態を一つ前へ戻す
strata presets undo <PRESET-NAME-OR-ID>

# profile または run configuration から対象 slot を決める
strata presets undo <REQUIRED-POSITIONAL-ARG> --config <PROFILE>

# JSON 形式で結果を受け取る
strata presets undo <PRESET-NAME-OR-ID> --output json
```

`preset` は parser で必須です。`--config` を指定した場合、実装はその profile/configuration から選択肢とモデル識別子で slot を計算し、位置引数の値を slot 決定に使いません。`--config` を省略した場合は位置引数を slot key または preset 参照として解決します。preset 参照は完全 ID、4文字以上の ID prefix、または大文字小文字を区別しない完全一致名を受け付けます。曖昧な参照は拒否されます。

## 主な動作と副作用

- preset の ID/name から slot を特定した後、その slot の `active.json` の履歴を末尾から一件取り出し、以前の preset が存在すれば再び active にします。履歴が空で active preset がある場合は active を `null` にし、標準設定へ戻します。
- 履歴から参照された preset ファイルが既にない場合も active は `null` になります。プリセット JSON 自体を削除せず、状態 index (`active.json`) を更新します。
- preset の有効状態はモデル起動時に読み込まれます。このコマンド単体では engine 起動、測定、profile の run config 書き換えは行いません。
- `--config` の対象は `_load_target()` で profile 名または run configuration として解決・読み込みされ、その設定から slot key が作られます。
- 対象 slot に履歴も active preset もない場合は「there is nothing to undo」で失敗します。

## 出力とエラー

既定の human 出力では成功時に `Back to '<名前>'.` または `Back to the standard settings.` を標準出力へ表示し、終了コード 0 を返します。`--output json` では `active` を含む `schema_version: 1`, `ok: true` の JSON を出力します。

preset 解決エラーや undo 可能な状態がない場合、human 出力は `strata: <理由>` を標準エラーへ出して終了コード 5 を返します。JSON 出力では `ok: false` とエラー情報を含む JSON を出します。`--config` の profile/config 読み込み時に起きる `OSError` や `ValueError` は、通常は終了コード 2 のエラーとして処理されます。

## 関連文書

- [`strata presets` の概要](../README.md)
- [`strata presets apply`](../apply/README.md)
- [`strata presets status`](../status/README.md)
- [CLI 索引](../../../README.md)（このコマンドの `--config`、`--output`、`--help` 文書を含む）

## 根拠

- `strata_cli/tune_commands.py:49-72` — `presets undo` parser、必須位置引数、`--config` と共通 `--output` の定義。
- `strata_cli/tune_commands.py:95-114,289-295,321-348` — human/JSON 成功・失敗出力、対象設定の読み込み、slot 決定、undo 呼び出しと例外処理。
- `strata_control/presets.py:202-208,218-230,310-326,339-358` — index の保存、preset 参照の規則、有効化時の履歴記録、undo 時の履歴復元と標準設定への復帰。
- `strata_control/presets.py:432-482` — active preset は設定に overlay される起動経路で読み込まれ、hard stale 等の条件では適用されないこと。
- `strata_cli/cli.py:486-488,2151-2155` — `presets` parser の登録と実行 dispatch。
- `docs/cli/README.md:875-881` — このコマンドの索引上の階層と option scope。
