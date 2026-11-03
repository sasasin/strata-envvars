# `--quiet`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない flag |

## 役割

人向け出力のうち stdout に出る情報メッセージを抑制します。エンジン削除自体の実行可否や削除内容は変えません。

## 使い方

```sh
strata components remove VERSION_OR_FOLDER --quiet
```

`VERSION_OR_FOLDER` はインストール済みエンジンのバージョンまたはフォルダー名に置き換えます。このコマンドは対象エンジンを削除します。誤削除を避けるため、実行前に `strata components engines` で対象を確認してください。

## 値と既定値

`--quiet` は `store_true` の引数で値を取りません。省略時は false 相当、指定時は true です。短縮 alias はありません。`remove` の位置引数 `engine` は必須で、`--family` は `qwen` または `deepseek` を受け付け、省略時はどちらの family も候補になります（`strata_cli/update_cmd.py:88-91`）。

## 実行時の動作

`remove` parser に `_common` を適用した後、`cli.py` は `update_cmd.add_parsers` が返す parser 群に `--quiet` を追加します。したがって、このフラグは `components remove` で有効です（`strata_cli/update_cmd.py:88-95`、`strata_cli/cli.py:139-140,508-515`）。

通常の人向け出力（`--output human`）で `--quiet` を指定すると、CLI は `_run` の stdout を一時バッファへ取り込み、正常終了時には表示しません。削除成功時に出す「削除したバージョン・解放容量」のメッセージが抑制対象です（`strata_cli/cli.py:2253-2265`、`strata_cli/update_cmd.py:395-400`）。

削除処理は通常どおり実行されます。対象の一覧から一致するエンジンを特定し、`delete_engine` がコンポーネントフォルダーを `.deleting-*` へ rename してから再帰削除を試みます。Qwen engine では前バージョン・pin・該当 version の失敗記録を状態ファイルから整理し、削除履歴を保存します。モデルと設定、別 family の engine は削除対象外です（`strata_cli/update_cmd.py:378,395-400`、`strata_control/engine_library.py:294-334`）。

`--output json` または `--output jsonl` と併用した場合、CLI は quiet 用 stdout 捕捉に入らず通常の処理へ進みます。remove の成功応答は JSON 1 行で出力されるため、`--quiet` はこの機械可読出力を消しません（`strata_cli/cli.py:2253-2254`、`strata_cli/update_cmd.py:395-399`）。

## 適用条件と副作用

`--quiet` は人向け stdout の表示制御です。標準エラーは捕捉対象ではありません。また、remove が失敗して `_run` が非ゼロを返した場合、quiet 処理は捕捉済み stdout があれば stderr に戻します。削除可否を示す診断は `update_cmd` 側から stderr に出るため、quiet でもエラーを確認できます（`strata_cli/cli.py:2258-2265`、`strata_cli/update_cmd.py:237-242`）。

現在使用中の engine、または実行中プログラムが使用している engine は削除できません。削除関数はこの条件で終了コード 2 の `UpdateError` を発生させます。対象がインストール済みでない場合も終了コード 2 です。フォルダーを `.deleting-*` に rename できない場合は、何も変更しなかった旨と再試行の案内を含むエラーになり、終了コード 6 です（`strata_control/engine_library.py:167-176,294-316`）。

## 出力とエラー

- human 出力で削除成功: stdout の完了メッセージは `--quiet` により抑制されます。
- JSON/JSONL 出力: 成功時は `schema_version`、`ok: true`、削除結果を含む JSON が stdout に残ります。
- 失敗: `--quiet` は stderr の診断を抑制しません。human 出力時の `UpdateError` は `strata: <message>` として stderr に表示され、エラーコードは例として未インストール・削除禁止が 2、rename 失敗が 6 です（`strata_cli/update_cmd.py:237-242`、`strata_control/engine_library.py:305-316`）。

## 根拠

- parser と共通 flag の登録: `strata_cli/update_cmd.py:88-95`、`strata_cli/cli.py:139-140,508-515`
- quiet の stdout 捕捉と非ゼロ時の stderr 再出力: `strata_cli/cli.py:2253-2265`
- `remove` の選択、成功出力、機械可読出力: `strata_cli/update_cmd.py:378,395-400`
- 削除拒否条件、rename・削除、状態記録: `strata_control/engine_library.py:167-176,294-334`

