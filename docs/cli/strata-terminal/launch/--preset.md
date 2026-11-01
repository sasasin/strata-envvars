# `--preset`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--preset` |
| 別名 | なし |
| 値 | 保存済み launch preset の名前（`NAME`） |

## 役割

保存済みの起動設定を読み込み、その設定でモデルの serving を開始します。モデル、context、接続方法などを毎回指定せず再利用できます。preset と同時に他の起動オプションを渡すと、その実行に限り読み込んだ設定を上書きできます（例: `strata launch --preset Office --set prefill=65536 --no-tui`）。`--preset` は `strata connect --preset` にもありますが、そちらは別 parser・別用途です。

## 使い方

```sh
strata launch --preset "IQ3_XXS 128K"
strata launch --preset Office --set prefill=65536 --no-tui
strata launch --plan --preset Office
```

名前に空白があるときは引用符で囲みます。対話端末で起動条件を指定した場合は通常 monitor が開き、`--no-tui` を付けると画面を出さず、起動結果のアドレスを表示して戻ります。`--plan` は実行計画を表示して終了します。

## 値と既定値

- 値を1個取ります。parser に `type`、`choices`、既定値、名前の形式検証はなく、省略時の値は `None` です。短縮別名もありません。
- 渡された名前は小文字化され、英小文字・数字・`-`・`_` 以外の連続部分を `-` に置き換えた slug から JSON ファイル名を作ります。したがって大文字小文字や記号の違いが同じファイルを指す場合があります。名前は最大48文字に切られます。
- ファイルがない場合は「その名前の保存済み preset はない」として失敗します。読み込み不能または JSON 不正なら再保存を案内し、JSON が object でなければ破損として失敗します。空文字を含む名前の個別検証は parser にありません。
- 同じオプションの複数回指定時の専用処理はありません（通常の `argparse` 引数として解析されます）。

## 実行時の動作

preset の JSON を `LaunchSettings` に読み込み、引数で明示された値をその上に反映します。たとえば `--model`、`--context`、`--access`、`--port`、API key、`--set` は preset の対応設定を更新します。`--no-api-key` だけを指定した場合は保存済み API key も外します。`--save-preset NAME` を併用すると設定名がその名前に変わり、runner が例外なく戻った後にその名前で保存（同名 preset は置換）します。これらの更新は、`--save-preset` を使わない限り元の preset ファイルに保存されません。

起動前の `--plan` は同じ preset を読み込んで計画を作りますが、serve や preset の最終使用時刻更新には進みません。通常の起動では runner が例外なく戻った後（serving しなかった結果を含む）に `last_used` が更新されます。preset はモデルファイルや tuning 結果そのものを複製するのではなく、起動設定を保存するものです。tuning 結果は共有 store の参照として扱われます。

## 適用条件と副作用

- `--preset` があると「起動対象が指定された」と判定され、引数なしの対話セットアップ画面を開く経路には入りません。preset を読む後、model catalog の利用可否、設定 validation、engine・モデルの準備を経て起動します。
- 保存先は既定で profiles ディレクトリの隣にある `launch-presets/` です。`STRATA_LAUNCH_PRESET_DIR` が設定されていれば、そのディレクトリが使われます。preset は API key を含む場合があるため、Strata は保存ファイルを private 扱いで書き込みます。
- `--preset` に他の設定変更を添えても起動時だけの変更です。恒久化するには `--save-preset` を指定します。`--plan` は何も変更しない経路として実装されています。
- `strata launch --stop --preset NAME` では、起動設定を実行する代わりに、その名前を profile slug にして該当 launch を停止する対象に指定します。

## 出力とエラー

- preset が見つからない、読み取れない、JSON が壊れている場合は `PresetError` を捕捉し、通常出力では `strata: ...` を stderr に出して終了コード 2 を返します。`--output json` では `ok: false` とエラー内容を JSON で stdout に出します。
- 適用した設定が不正、または起動処理で失敗した場合も、設定エラーは終了コード 2、`LaunchError` はそのエラーに付属するコードで報告されます。モデル・server の起動時は進捗や警告が表示されます。
- `--plan` は計画と警告を表示して終了コード 0 を返します。通常の起動で server が serving 状態になれば接続 URL が表示され、保存 preset 由来の API key があればマスクした値と確認方法が案内されます。

## 根拠

- parser と利用者向け例: `strata_cli/launch/cmd.py:16-29`, `strata_cli/launch/cmd.py:75-85`
- preset の読込・引数による上書き: `strata_cli/launch/cmd.py:205-211`, `strata_cli/launch/cmd.py:214-300`
- 起動経路・plan・使用時刻更新: `strata_cli/launch/cmd.py:753-784`, `strata_cli/launch/cmd.py:797-830`, `strata_cli/launch/cmd.py:854-863`
- エラー処理と出力: `strata_cli/launch/cmd.py:686-697`, `strata_cli/launch/cmd.py:913-918`, `strata_cli/launch/cmd.py:871-910`
- 保存場所・ファイル形式・読み込み失敗・private 書込み: `strata_cli/launch/store.py:1-7`, `strata_cli/launch/store.py:27-60`, `strata_cli/launch/store.py:88-103`
- slug の生成規則: `strata_cli/launch/settings.py:355-360`
- preset が保持する項目と `from_dict`: `strata_cli/launch/settings.py:97-149`
