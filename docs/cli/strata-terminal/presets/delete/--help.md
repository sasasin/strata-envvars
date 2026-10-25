# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets delete` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata presets delete` の使い方と、そのサブコマンドで受理する引数・オプションを表示します。このスコープのヘルプはトップレベルや他の `presets` サブコマンドとは別です。

## 使い方

```sh
strata presets delete --help
```

`strata presets delete -h` も同じヘルプを表示します。

## 値と既定値

値は取りません。`strata_cli/tune_commands.py` では delete parser に個別の `--help` 定義がありませんが、`argparse` の `add_parser()` が既定で help を有効にします。delete parser は位置引数 `preset` と共通オプション `--output {human,json}` を持ちます。`preset` は通常実行時に必要ですが、help 表示時には不要です（`strata_cli/tune_commands.py:53-55,68-69`）。

## 実行時の動作

`strata_cli/cli.py` が `presets` parser を登録し（`strata_cli/cli.py:486-489`）、その登録処理で `delete` parser を作ります（`strata_cli/tune_commands.py:49-51,68-69`）。`main()` は parser を組み立ててから引数解析を行い、`--help` が指定されると通常のコマンド dispatch に進む前にヘルプ表示のため終了します（`strata_cli/cli.py:2217-2225`）。そのため、このフラグだけの呼び出しは preset の検索・削除を行わず、`presets_command()` の JSON／人間向け出力処理にも入りません（`strata_cli/tune_commands.py:289-295,317-320`）。

同じ parser には `--output {human,json}` も表示されますが、help 表示を JSON 形式に切り替える処理は定義されていません。実際の削除は `strata presets delete <preset>` の通常経路で行われ、`preset` の検索後に削除関数が呼ばれます（`strata_cli/tune_commands.py:317-320`）。

## 適用条件と副作用

このヘルプは `strata presets delete` の parser でのみ適用されます。help 表示処理自体は preset データを変更しません。

ただし CLI の `main()` は引数解析前に `private_files.adopt_user_defaults()` を呼びます。これは Windows ではプロセスの既定 owner／DACL を設定しようとし、他の OS では何もせず、失敗しても例外を送出しません。ファイルを作成・削除する処理ではありません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-358,372-389`）。

## 出力とエラー

同一 checkout で `python strata.py presets delete --help` を実行して確認した出力は、usage、位置引数 `preset`、`-h/--help`、`--output {human,json}` の一覧です。出力先は標準出力で、help action は成功終了します。これは `argparse` の標準 help 動作です。Strata 独自の validation や preset 不在時のエラー処理は、help 表示では実行されません。

未知の余分な引数が残った場合は、`parse_known_args()` の後にトップレベル parser の `error()` へ進みます（`strata_cli/cli.py:2223-2231`）。help と同時に指定した余分な引数の扱いなど、標準 parser の細部は Strata の個別分岐としては定義されていません。

## 根拠

- `strata_cli/tune_commands.py:49-55,68-69` — `presets`／`delete` parser、共通 `--output` と位置引数の定義。`--help` は暗黙の既定。
- `strata_cli/cli.py:40-45,486-489,2217-2231` — parser の生成・登録、引数解析と dispatch 前の help 処理位置。
- `strata_cli/tune_commands.py:289-320` — 通常実行時の出力形式と delete 処理。
- `strata_control/presets.py:218-231,374-387` — 通常削除経路での preset 解決と保存データ／active index の更新（help からは呼ばれない）。
- `strata_control/private_files.py:349-389` — CLI 起動時に先行するプロセス既定値設定。
- 補助確認: 同一 revision の `python strata.py presets delete --help`。配布 Release の CLI は調査していません。
