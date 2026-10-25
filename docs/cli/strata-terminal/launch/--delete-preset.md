# `--delete-preset`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--delete-preset` |
| 別名 | なし |
| 値 | 必須の preset 名 `NAME`。文字列として受け取り、保存先を決める際に slug 化される |

## 役割

保存済みの `strata launch` preset を1件削除します。モデルファイルや tuning の測定結果を削除する操作ではありません。preset は profiles と tuning presets と連携しますが、このオプションが直接削除するのは launch preset の JSON ファイルです（`strata_cli/launch/cmd.py:141-145,657-660`、`strata_cli/launch/store.py:1-7,132-137`）。

## 使い方

```sh
strata launch --delete-preset "Office"
```

削除する preset 名を `--delete-preset` の直後に指定します。preset の一覧は `strata launch --list-presets` で確認できます（`strata_cli/launch/cmd.py:28,141-145`）。

## 値と既定値

- `NAME` は必須です。省略すると `argparse` が引数不足として usage とエラーを表示し、終了コード 2 で終了します。値の型変換や専用 validation は parser にありません（`strata_cli/launch/cmd.py:141-145`、`strata_cli/cli.py:2217-2231`）。
- オプションを省略した場合の値は `None` で、削除分岐には入りません。繰り返し指定した場合は `argparse` の通常の `store` 動作で最後の値が使われます（`strata_cli/launch/cmd.py:143,657-660`）。
- 保存先ファイル名を作る際、名前は小文字化し、英小文字・数字・`-`・`_` 以外の連続部分を `-` に置換し、先頭末尾の `-` と `_` を除きます。空になった場合は `launch`、英字以外で始まる場合は先頭に `l` を付け、最大48文字にします。このため表記の異なる名前が同じ slug を指すことがあります（`strata_cli/launch/settings.py:310-315`、`strata_cli/launch/store.py:35-36`）。
- 空文字列 `""` は parser 上は受け取れますが、実行時に値が偽と判定されて削除分岐に入りません。通常の起動処理へ進むため、削除コマンドとしては使えません（`strata_cli/launch/cmd.py:657-660,679-700`）。空白だけの文字列は truthy なので削除分岐に入り、slug 化後のファイルを対象にします。

## 実行時の動作

`run_launch` は preset 一覧表示の後に `a.delete_preset` を確認し、真であれば `store.delete()` を呼びます。従って `--delete-preset NAME` はモデル起動や通常の launch 設定処理に進まず、削除に成功すると stdout に `Deleted the preset 'NAME'. Models and tuning results were not touched.` を出して 0 を返します（`strata_cli/launch/cmd.py:630-660`）。

`store.delete()` は `STRATA_LAUNCH_PRESET_DIR` が設定されていればそのディレクトリ、なければ profiles ディレクトリの隣にある `launch-presets/` を使います。名前を slug 化して `<slug>.json` を特定し、対象がファイルであることを確認してから `Path.unlink()` します。preset ディレクトリがまだ存在しない場合に作成する処理はありません（`strata_cli/launch/store.py:27-36,132-137`）。

この処理は launch preset ファイルだけを削除し、関連するモデルファイル、tuning preset、shared profile を削除しません。また、稼働中サーバーを停止する処理もありません。server 停止は別の `--stop` 分岐です（`strata_cli/launch/cmd.py:657-663`、`strata_cli/launch/store.py:132-137`）。

このオプションと他の管理オプションを同時に指定しても parser は排他にしません。処理順は `--list-presets`、`--delete-preset`、`--stop`、`--status`、`--show-key` です。たとえば `--list-presets --delete-preset NAME` は一覧表示だけを行い、削除分岐には到達しません（`strata_cli/launch/cmd.py:141-146,643-677`）。

## 適用条件と副作用

- 対象ファイルが存在しないか通常ファイルでない場合、削除せず `PresetError` になります。メッセージには入力名と、見つかれば近い preset 名が含まれます（`strata_cli/launch/store.py:106-112,132-135`）。
- preset ディレクトリは `STRATA_LAUNCH_PRESET_DIR` で変更できます。この環境変数は保存先ディレクトリを選ぶもので、オプション値自体の解釈は変えません（`strata_cli/launch/store.py:27-36`）。
- 既存ファイルを直接削除します。削除前の確認やバックアップ作成はありません（`strata_cli/launch/store.py:132-137`）。
- 実行中サーバーやモデルファイルには触れません。preset の保存ファイルを消しても、同じ名前のサーバーを止めることはありません（`strata_cli/launch/cmd.py:657-663`、`strata_cli/launch/store.py:132-137`）。

## 出力とエラー

- 成功時は stdout に削除結果を1行表示し、終了コード 0 です。`--output json` を同時に指定しても、この成功分岐は JSON ではなく人間向けのテキストを出します（`strata_cli/launch/cmd.py:634,657-660,416-418`）。
- 対象がない場合は `PresetError` を捕捉し、標準エラーに `strata: ...` を出して終了コード 2 を返します。`--output json` ならエラーオブジェクトを JSON で標準出力へ出します（`strata_cli/launch/cmd.py:636-641,832-835`）。
- ファイル削除時の `OSError` は `run_launch` 内では捕捉されません。CLI 上位層がローカルファイル操作のエラーとして処理し、通常は終了コード 6、`--output json` 指定時は JSON エラーを返します（`strata_cli/launch/store.py:132-137`、`strata_cli/cli.py:2176-2183`）。
- `--delete-preset` に値を付け忘れた場合は `argparse` の構文エラーとなり、終了コード 2 です（`strata_cli/launch/cmd.py:143`、`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/launch/cmd.py:141-146` — `launch` の管理用 parser 定義。
- `strata_cli/launch/cmd.py:630-660,832-835` — 削除分岐、成功出力、preset エラー処理。
- `strata_cli/launch/store.py:27-36,132-137` — 保存場所、名前からのパス生成、ファイル削除と不存在時のエラー。
- `strata_cli/launch/settings.py:310-315` — preset 名の slug 化規則。
- `strata_cli/cli.py:2217-2231,2176-2183` — parser エラーと `OSError` の上位処理。
