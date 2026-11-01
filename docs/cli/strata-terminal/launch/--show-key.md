# `--show-key`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--show-key` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`、既定値は false） |

## 役割

launch または setup.py が保存したモデル設定から API key を読み出し、標準出力へそのまま表示します。稼働中の launch や preset に保存されたキーを確認する用途にも使えます。設定やサーバーを変更せず、通常の launch 起動処理より前に表示して終了します。

## 使い方

```sh
strata launch --show-key
strata launch --show-key --preset "Office"
strata launch --show-key --model iq3_xxs
```

1つ目は指定のない稼働 launch を優先し、該当キーがなければ setup.py のモデル設定を検索します。2つ目は `Office` の稼働 launch または保存済み preset を指定します。3つ目の `--model` は setup.py のモデル設定を検索するときに候補を絞ります。出力は実際の秘密鍵なので、端末やコマンド出力を閲覧できる利用者に注意してください。

## 値と既定値

値は不要です。parser は `action="store_true"` で定義され、既定値は false です（`strata_cli/launch/cmd.py:153-154`）。同じフラグを複数回指定しても真偽値のままで、値の検証や鍵の形式検証はこのオプションについて行いません。

`--preset NAME` と併用すると、その名前に対応する稼働 launch の設定キーを先に確認し、設定キーがなければ保存 preset のキーを使います。`--preset` を省略した場合は稼働 launch の情報を先に調べます。そこにキーがなくても preset は自動選択されず、setup.py のモデル設定へ進みます（`strata_cli/launch/cmd.py:636-658, 728-745`）。

## 実行時の動作

`run_launch()` は `--list-presets`、`--delete-preset`、`--stop`、`--status` の処理後、通常の launch 設定・起動へ進む前に `--show-key` を処理します。したがってこの分岐ではモデルの起動、チューニング、server 起動を行いません（`strata_cli/launch/cmd.py:699-728`）。

キー検索の順序は次のとおりです。

1. `launch_info(--preset)` が稼働 launch と preset を検索します。名前を指定した場合は同名の稼働 launch の設定ファイルにある `api_key` を読み、値がなければ保存 preset の `api_key` を使います。名前なしの場合は検出された稼働 launch の先頭を使います。設定の `api_key` が空、または文字列 `none` の場合は preset 側のキーにフォールバックします（`strata_cli/launch/cmd.py:636-658`）。
2. そこでキーが見つからず、かつ `--preset` が指定されていない場合は、`strata_control.models.list_installed()` で見つけた setup.py のモデル設定ファイルを読みます。設定の `api_key` を前後空白除去して取得し、空文字と `none` は候補から除外します（`strata_cli/launch/cmd.py:661-683, 733-745`）。
3. `--model NAME` を指定したときは、モデル ID が NAME と大文字小文字を無視して一致するか、NAME で終わる候補に絞ります。これは setup.py 設定の検索にだけ使われます（`strata_cli/launch/cmd.py:661-675, 733-745`）。

候補が1件なら鍵を表示します。複数ならモデル ID の一覧を伴うエラーになり、`--model NAME` を指定するよう案内します（`strata_cli/launch/cmd.py:735-745`）。setup.py 設定の探索・読込 helper は設定を読み取り、モデル ID、設定ファイルのパス、鍵を返します（`strata_cli/launch/cmd.py:661-683`）。

同じ `--show-key` 文字列は `strata launch connect` にも別 parser action として存在しますが、別コマンドのスコープです。索引も [`strata connect --show-key`](../connect/--show-key.md) を別文書として扱います（`strata_cli/launch/cmd.py:156-173`）。

## 適用条件と副作用

- `--preset` で選んだ稼働 launch または保存 preset に API key がある場合は、それを出力します。`--preset` を指定した場合、そこにキーがなくても setup.py のモデル設定検索には進みません（`strata_cli/launch/cmd.py:652-658, 728-745`）。
- `--preset` がなく稼働 launch にキーがない場合、setup.py のモデル設定にあるキーが検索対象です。複数の設定にキーがあり `--model` で一つに絞れない場合は失敗します（`strata_cli/launch/cmd.py:661-683, 733-745`）。
- 成功時は API key 全体を stdout に1行で出力します。setup.py 設定からの成功では human 出力の場合に限り、モデル ID と設定ファイルのパスを stderr に補足表示します（`strata_cli/launch/cmd.py:728-740, 447-449`）。
- この分岐はファイルの読込とモデル設定の列挙を行います。ソース上、このオプション自体によるファイル書込、鍵の生成・ローテーション、ネットワーク通信、server 起動は確認できません（`strata_cli/launch/cmd.py:728-745`）。

## 出力とエラー

- キーが見つかった場合、キー文字列を stdout に出力し終了コード `0` を返します（`strata_cli/launch/cmd.py:728-740`）。
- キーがない場合は `There is no API key for that launch.` を表示し終了コード `5` を返します。preset 無指定時は preset または setup.py 設定を指定する案内が続きます（`strata_cli/launch/cmd.py:745`）。
- `--model` に一致する setup.py 設定がなく、キーも見つからない場合はその旨を出して終了コード `5` を返します（`strata_cli/launch/cmd.py:743-744`）。複数モデルにキーがある場合も候補名と `--model` の案内を出して終了コード `5` です（`strata_cli/launch/cmd.py:741-742`）。
- 失敗時は human 出力では `strata: ...` を stderr に出します。`--output json` の失敗は `ok: false` とエラー情報を含む JSON を stdout に出力します（`strata_cli/launch/cmd.py:690-697`）。一方、成功経路は `--output json` でも鍵を `_say()` でそのまま stdout に出すため、JSON 形式ではありません。setup.py 設定から成功した場合の補足 stderr は JSON 出力時には抑止されます（`strata_cli/launch/cmd.py:728-740, 447-449`）。

## 根拠

- parser 定義と別コマンドの同名 option: `strata_cli/launch/cmd.py:148-173`
- 稼働 launch / preset のキー選択: `strata_cli/launch/cmd.py:598-658`
- setup.py 設定の候補抽出とモデル名フィルター: `strata_cli/launch/cmd.py:661-683`
- オプションの分岐、出力、失敗条件: `strata_cli/launch/cmd.py:686-697, 728-745`
- `--output json` 時の成功キー出力と stderr 補足: `strata_cli/launch/cmd.py:447-449, 735-740`

調査範囲は上記 commit の Terminal CLI ソースです。実環境にある preset、稼働 launch、setup.py 設定の内容は調査していません。また、CLI の help は実行しておらず、parser 定義と処理コードを根拠にしています。
