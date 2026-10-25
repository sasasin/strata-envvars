# `--set-default-data-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査開始時の checkout は `main...origin/main` で、作業ツリーに未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新 wrapper からの委譲を含む） |
| オプション | `--set-default-data-dir` |
| 別名 | なし |
| 値 | 値を取らない `store_true` フラグ。既定値は `False` |

## 役割

`--data-dir` で新しい保存先を指定したとき、既存のモデルデータは元の場所に残しつつ、新しい場所を今後の既定データフォルダーとして記憶させます。`--move-data` のように既存データを移動する指定ではありません。

## 使い方

```sh
./setup.sh --setup --data-dir "$HOME/Strata-data-new" --set-default-data-dir
```

この例は新しい保存先を指定し、その場所を既定として記憶します。既存モデルが別の場所にあればそこに残り、新規ダウンロードは指定先に置かれます。Windows では `START-HERE.bat` に同じ引数を渡せます。

## 値と既定値

- Linux/Windows の `setup.py` parser では値なしの `action="store_true"` として定義されています。省略時は偽で、重複指定しても有効のままです（`setup.py:8486-8487`）。macOS の Metal 用 parser も同じ値なしフラグとして受け取ります（`metal/setup_mac.py:339-342`）。
- このフラグ単独では保存先を指定しません。保存先は `--data-dir DIR` で指定します。
- `--data-dir` の値は `expanduser()` と `resolve()` で解決され、フォルダー利用可否を検査します。指定先の検証に失敗すると理由と「何も変更・ダウンロードしていない」旨を表示して終了コード 1 で停止します（`setup.py:6051-6057,825-830`）。

## 実行時の動作

`data_folder_for()` は `--data-dir`、`--move-data`、`--yes`、`--set-default-data-dir` の値を共通の `data_folder()` に渡します（`setup.py:6136-6139`）。指定先が現在の記憶済みフォルダーと異なるとき、Strata はこのインストールや過去のインストール、記憶済みフォルダーなどにモデルデータがあるかを調べます（`setup.py:6067-6081`）。

移動対象のデータがあり、`--move-data` がない場合は、`--yes` なしの実行では keep/move を尋ねます。`--yes` がある場合や質問への回答が keep の場合、既存データは元の場所に残ります。通常この分岐では新しい保存先は記憶されませんが、このフラグを付けると `settings.json` の `data_dir` に指定先が保存されます（`setup.py:6082-6096`）。例えば次の形では、質問なしで既存データを残し、新しい場所を記憶します。

```sh
./setup.sh --setup --data-dir "$HOME/Strata-data-new" --set-default-data-dir --yes
```

このフラグなしでも、見つかったデータがなく移動元を失う心配がない場合は、通常処理が指定先を既定場所として保存します。移動を選んだ場合も、処理後に `data_dir` と Strata install 一覧を保存します（`setup.py:6097-6098,6105-6133`）。したがって、このフラグ固有の効果が必要なのは主に「既存データを残すが、指定先を次回以降の既定にする」場合です。

保存先を作れない場合は警告して `home()` を代わりに使います（`setup.py:6062-6066`）。設定ファイルは通常 POSIX では `$XDG_CONFIG_HOME/strata/settings.json`（未設定時 `~/.config/strata/settings.json`）、Windows では `%APPDATA%/Strata/settings.json` にあります。`STRATA_SETTINGS_FILE` が設定されている場合はそのパスが使われます（`setup.py:5900-5912`）。設定書き込みが失敗すると警告しますが、`save_settings()` は例外を再送出しません（`setup.py:5922-5929`）。

## 適用条件と副作用

- `--data-dir` を指定しない場合、`set_default` は `data_folder()` 内の「別の指定先を選んだ」分岐で参照されないため、このオプション単独では保存先を変更しません（`setup.py:6051-6053,6074-6096`）。
- 既存の別フォルダーを選んだ場合、既存モデルは移動されません。データを元の場所で使い続け、新しいダウンロード先を変える動作です（`setup.py:6091-6096`）。他のドライブにあるデータもその場所に残ります（`setup.py:6105-6109`）。
- 既存モデルがない場合や移動を選んだ場合は、通常の処理でも選択先が保存されるため、オプションがなくても記憶結果は同じです（`setup.py:6097-6098,6130-6133`）。
- 通常の既存モデル起動は `data_folder_in_place()` を使用し、設定を読むだけでフォルダー作成・移動・コピー・保存を行いません。`--data-dir` がある呼び出しはこの単純起動判定から外れて `data_folder_for()` を通ります（`setup.py:6142-6151,8602-8610`）。
- macOS の通常 setup は `setup.py` が Metal 用 `metal/setup_mac.py` に処理を委譲し、同 parser がこのフラグを受けて共通の `data_folder_for()` を呼びます（`setup.py:8412-8419; metal/setup_mac.py:339-365`）。
- `setup.sh` と `START-HERE.bat` は受け取った引数を `setup.py` に渡します。ラッパー固有の解釈はありません（`setup.sh:9-12,76; START-HERE.bat:44-54`）。

## 出力とエラー

- 既存データを残す場合、既存モデルが元の場所に留まり、新しいダウンロードが指定先に置かれる旨を表示します（`setup.py:6091-6095`）。
- 明示した保存先の検証に失敗すると `fail()` がメッセージを表示して終了コード 1 で停止します（`setup.py:6054-6057,825-830`）。
- 保存先ディレクトリーの作成に失敗すると警告して `home()` にフォールバックします。設定ファイルへの書き込みに失敗した場合も警告します（`setup.py:6062-6066,5922-5929`）。

## 根拠

- `setup.py:8481-8487` — `--data-dir`、`--move-data`、本オプションの parser 宣言。
- `setup.py:6042-6098` — 保存先選択、既存データの keep/move 判断、本オプションによる keep 時の保存。
- `setup.py:6105-6139` — データ処理、設定保存、CLI 値の共通処理への受け渡し。
- `setup.py:5900-5929` — 設定ファイルの選択と書き込み失敗時の警告。
- `setup.py:6142-6151,8602-8610` — 通常起動と setup 系経路の違い。
- `setup.py:8412-8419`; `metal/setup_mac.py:339-365` — macOS parser への委譲と共通処理呼び出し。
- `setup.sh:9-12,76`; `START-HERE.bat:44-54` — wrapper から `setup.py` への引数委譲。

調査は指定 revision の parser、使用箇所、設定保存処理と wrapper を対象にしました。CLI `--help` は実行していません。setup/update はデータ配置などの副作用を伴い得るため、help 実行でなくソースを根拠にしています。
