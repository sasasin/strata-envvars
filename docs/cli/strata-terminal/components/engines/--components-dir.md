# `--components-dir`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネントフォルダのパス（文字列、必須） |

## 役割

エンジン一覧コマンドが Qwen 系エンジンを探すコンポーネントフォルダを指定します。指定したフォルダの `engine/` が走査対象です。既定では `STRATA_COMPONENTS_DIR` または OS ごとの per-user フォルダを使います。

## 使い方

```sh
strata components engines --components-dir /srv/strata/components
```

## 値と既定値

- 値は `argparse` の通常の文字列引数です。parser に型変換、選択肢、空文字・存在確認などの独自 validation はありません。省略時の parser 値は `None` です（`strata_cli/update_cmd.py:47-56`）。
- 実行時に値が truthy なら `Path(value)` を使います。省略時、または空文字の場合は `engine_component.components_dir()` に委ねられます（`strata_cli/update_cmd.py:233-245`）。
- 既定ルートは、環境変数 `STRATA_COMPONENTS_DIR` が空でなければその値です。そうでなければ Windows は `%LOCALAPPDATA%\Strata\components`（`LOCALAPPDATA` がなければホーム配下）、その他の OS は `$XDG_DATA_HOME/strata/components`（未設定時は `~/.local/share/strata/components`）です（`strata_control/engine_component.py:176-186`）。

## 実行時の動作

`strata components engines` の parser は共通 option 群を登録し、その中にこの option があります（`strata_cli/update_cmd.py:47-56,82-83`）。CLI の dispatcher は `engines` を `update_cmd.run()` に渡し、同処理がコンポーネントルートを決めて `updater.Context(components=root, ...)` を作成します（`strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:233-255`）。

Qwen 系は指定ルート直下の `engine/` を走査し、各パッケージを一覧化します（`strata_control/engine_component.py:189-190,933-946`、`strata_control/engine_library.py:91-123`）。DeepSeek 系は同じフォルダに限定されません。保存済み run config が指す場所、`STRATA_INSTALL_DIR` の `engine-dsv41/`、および指定ルートの親にある `engine-dsv41/` も列挙候補です（`strata_control/updater.py:1444-1455`、`strata_control/engine_library.py:128-162`）。したがってこの option は Qwen の走査先を指定しますが、DeepSeek の全走査先を一括で固定する指定ではありません。

このコマンドは一覧を人間向け表示または JSON で出力します。JSON は `--output json` / `--json`、JSON Lines は `--output jsonl` で選べます。`--json` と `--quiet` は CLI が one-shot parser に後付けします（`strata_cli/cli.py:508-515`）。一覧にはバージョン、容量、backend、現在使用中か、当該 PC で動作可能か等が含まれます（`strata_cli/update_cmd.py:358-377`）。

## 適用条件と副作用

- 明示したパスはコンポーネントルートとして使われ、一覧の結果に反映されます。ファミリー判定や GPU 適合性の判定は別途行われます（`strata_cli/update_cmd.py:244-255`、`strata_control/engine_library.py:91-123,136-162`）。
- 一覧処理はエンジンをダウンロード、切り替え、削除せず、ファイルを読むだけです（`strata_control/engine_library.py:180-195`）。一方、一覧用の付加情報として serving 状態と各エンジンを使用中のプロセスがあるかを確認します（`strata_control/engine_library.py:84-88,167-178,183-190`）。
- Qwen の `engine/` が存在しない、または読み取れない場合、走査関数は空の結果を返します。各ファイルの破損等は問題項目として一覧に含まれる場合があります（`strata_control/engine_component.py:933-946`）。DeepSeek の候補ルート探索で例外が起きた場合はその候補を空として扱います（`strata_control/engine_library.py:128-133`）。

## 出力とエラー

値が欠落した場合は argparse の構文エラーになり、未認識の引数は CLI が `ap.error()` に渡します（`strata_cli/cli.py:2246-2248`）。値のパスに対する専用の検証エラーはありません。Qwen の走査先を列挙できなければ空一覧として処理され、通常の一覧出力は終了コード 0 で完了します（`strata_cli/update_cmd.py:358-377`、`strata_control/engine_component.py:933-946`）。

## 根拠

- parser と既定値: `strata_cli/update_cmd.py:47-56,82-83`
- dispatcher、引数値からルートへの変換、実行 context: `strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:233-255`
- 既定コンポーネントディレクトリ: `strata_control/engine_component.py:176-186`
- Qwen の走査先と一覧データ: `strata_control/engine_component.py:189-190,933-946`、`strata_control/engine_library.py:91-123`
- DeepSeek の追加走査ルート: `strata_control/updater.py:1444-1455`、`strata_control/engine_library.py:128-162`
- 一覧処理・人間向け出力・読取専用の説明: `strata_control/engine_library.py:167-195`、`strata_cli/update_cmd.py:358-377`
