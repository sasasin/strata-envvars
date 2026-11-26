# `strata connect --preset`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--preset` |
| 別名 | なし |
| 値 | 保存済み起動 preset の名前（`NAME`）。parser では文字列として受け取り、選択肢や名前形式の検証はしない |

## 役割

`strata connect <app>` が出力または生成するアプリ設定の接続先を、指定した起動 preset に対応する稼働中サーバー、または保存 preset から選びます。preset 名は起動インスタンスの選択にも使われます。`--url`、`--key`、`--key-env`、`--model`、`--context` を併用すると、それぞれの明示値が preset などから得た値より優先されます。

## 使い方

```sh
# Office preset に対応する接続設定を表示する（ファイルは書き換えない）
strata connect opencode --preset Office
```

## 値と既定値

- 値は必須の文字列 `NAME` で、`--preset` の短縮別名はありません。Strata 側に名前形式・重複指定の追加検査はありません（parser: `terminal/strata_cli/launch/cmd.py:163-183`）。
- 名前は `slug()` で小文字化し、英数字・`-`・`_` 以外を `-` に置き換え、最大48文字にして照合します（`terminal/strata_cli/launch/settings.py:462-468`）。
- 未指定時は特定の preset を選びません。接続先は稼働中の起動情報、明示オプション、既定値から解決されます（`terminal/strata_cli/launch/cmd.py:1074-1079`）。
- 指定名に対応する稼働中起動も保存 preset も見つからないとき、`launch_info()` は `None` を返し、`connect` は通常の既定接続情報へ進みます。存在しない名前だけを理由にエラーにはなりません（`terminal/strata_cli/launch/cmd.py:703-724, 1074-1079`; `terminal/strata_cli/launch/store.py:89-96`）。
- preset ファイルが読めない、または内容が壊れている場合は `PresetError`（`ValueError` の派生）が発生し、通常出力では stderr に `strata: ...`、終了コード2で失敗します。`--output json` では JSON エラーになります（`terminal/strata_cli/launch/store.py:24-25, 89-103`; `terminal/strata_cli/cli.py:2248-2255, 558-563`）。

## 実行時の動作

`launch_info(NAME)` はまず `slug(NAME)` と一致する稼働中起動を探し、その起動の実行設定ファイルが読めれば API キー・モデル名・コンテキストを取得します。さらに同名の保存 preset を読み、稼働中設定がない場合は preset のポートと API キーを接続情報に使います（`terminal/strata_cli/launch/cmd.py:703-725`; `terminal/strata_cli/launch/store.py:28-37, 89-104`）。

ただし、停止中の保存 preset だけを指定した場合、現在の実装が `launch_info()` から返すモデル名は preset 内のモデルではなく `strata`、コンテキストは未設定です。そのため `run_connect()` は `strata` と32kを使います。parser の説明は preset からアドレス・キー・モデルを取るとしていますが、停止中 preset のモデル・コンテキストが実際に引き継がれることはソース上で確認できません（説明: `terminal/strata_cli/launch/cmd.py:174`; 値の組み立て: 同 `703-725, 1074-1079`; context の補完: `terminal/strata_cli/launch/harness.py:339-340`）。

接続情報の優先順位は、URL が `--url` → 選択情報 → `http://127.0.0.1:<既定ポート>`、キーが `--key` → `--key-env` で指定した環境変数 → 選択情報 → 空、モデルが `--model` → 選択情報 → `strata`、コンテキストが `--context` → 選択情報 → 32768 です（`terminal/strata_cli/launch/cmd.py:1074-1079`; 既定ポート: `terminal/strata_cli/launch/settings.py:75`）。決定した値は対象アプリ用の設定内容へレンダリングされます（`terminal/strata_cli/launch/harness.py:339-347`）。

このオプション自体は preset を読み取って設定内容を選ぶだけで、ファイルを書き込みません。書き込みには別途 `--write` が必要です。表示・JSON出力では API キーを既定でマスクし、`--show-key` を指定した場合だけ表示内容に実キーを含めます（`terminal/strata_cli/launch/cmd.py:1080-1086, 1120-1136`）。

## 適用条件と副作用

- `strata connect` の parser に属し、`strata launch --preset` とは同じ文字列でも別のコマンド・別の動作です。索引でも `strata-terminal/connect/--preset.md` として登録されています（`docs/cli/README.md:886-901`; parser: `terminal/strata_cli/launch/cmd.py:163-183`）。
- preset の検索先は `STRATA_LAUNCH_PRESET_DIR` が設定されていればそのディレクトリ、そうでなければ profiles ディレクトリの隣の `launch-presets/` です（`terminal/strata_cli/launch/store.py:28-37`）。
- `--preset` 単独でファイルやネットワークを変更する処理はありません。`--check` を併用すれば対象サーバーへ確認リクエストを送り、`--write` を併用すれば接続設定ファイルを書き込みます（`terminal/strata_cli/launch/cmd.py:1087-1119, 1147-1167`）。

## 出力とエラー

成功時には、preset から解決した値を含むアプリ設定ファイルの内容を表示します。既定ではキーはマスクされ、`--show-key` を付けると実キーが表示されます（`terminal/strata_cli/launch/cmd.py:1080-1086, 1120-1136`）。存在しない preset 名は前述の通り接続情報の既定値へフォールバックします。保存 preset が破損している場合は `ValueError` 経路でエラー出力・終了コード2になります（`terminal/strata_cli/launch/store.py:97-103`; `terminal/strata_cli/cli.py:2248-2255, 558-563`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `connect` parser と `--preset NAME` の定義、および関連引数。
- `terminal/strata_cli/launch/cmd.py:703-725` — 稼働中起動・保存 preset から URL、キー、モデル、コンテキスト等を組み立てる処理。
- `terminal/strata_cli/launch/cmd.py:1052-1086` — preset 情報と明示オプションの優先順位、接続設定のレンダリング。
- `terminal/strata_cli/launch/cmd.py:1120-1136` — 人向け出力と API キーのマスク。
- `terminal/strata_cli/launch/store.py:24-37, 89-104` — preset ディレクトリ、slug によるファイル名、読込・未発見・破損時の扱い。
- `terminal/strata_cli/launch/settings.py:462-468` — preset 名の slug 化。
- `terminal/strata_cli/launch/harness.py:339-347` — レンダリング用接続値の既定補完と出力構成。
- `terminal/strata_cli/cli.py:2248-2255, 558-563` — 値エラーの捕捉、stderr/JSON エラーと終了コード。
- `docs/cli/README.md:886-901` — `strata connect` 階層とこの文書の索引リンク。
