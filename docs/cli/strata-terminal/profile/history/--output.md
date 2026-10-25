# `strata profile history --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile history NAME` |
| オプション | `--output` |
| 別名 | なし（`--json` は one-shot 共通の別 parser action） |
| 値 | `human` または `json` |
| 既定値 | `human` |

## 役割

保存済み profile の現在 revision と、保存履歴にある過去 revision の一覧を標準出力へ表示します。`--output` は表示形式を選ぶもので、ファイルへの出力先は指定しません。履歴一覧をファイルへ書き出す処理はこのオプションにはありません。

## 使い方

```sh
strata profile history demo --output json
```

`NAME` は必須です。既定の人間向け表示は次のとおりです。

```sh
strata profile history demo
```

## 値と既定値

`strata_cli/cli.py` の `profile history` parser は `--output` の値を `human` または `json` に限定し、既定値を `human` とします。不正な値は argparse の引数エラーになります（`strata_cli/cli.py:99-101,2223-2231`）。

この parser は one-shot 共通の `--json` も受け取ります。`--json` を指定すると、通常処理の前に `output` が `json` に設定されます。したがって `--output human --json` では JSON が選ばれます。`--json` は `--output` の alias action ではなく、one-shot parser 群に追加される独立したフラグです（`strata_cli/cli.py:508-515,2232-2237`）。`--quiet` も同じ one-shot parser 群に追加されます。

## 実行時の動作

`history` 分岐は `profiles.history(NAME)` を呼び、返された一覧を `_success()` に渡します。human 表示では各行が `<revision>  current` または `<revision>  saved` になります。JSON 表示では `schema_version: 1`、`ok: true`、`profile`、`history` を含むオブジェクトが出力されます（`strata_cli/cli.py:1006-1010,535-542`）。

履歴 API は `${profile_dir}/.history/NAME` にある `*.json` のうち、拡張子を除く名前が小文字16桁の16進 revision で、通常ファイルかつシンボリックリンクでないものを列挙します。過去項目にはファイルの更新時刻を `saved_at` として含め、更新時刻の新しい順に並べます。現在 revision は先頭に必ず置かれ、過去側に同じ revision があれば重複を除きます。JSON では現在項目は `{"revision": ..., "current": true}`、過去項目は `{"revision": ..., "saved_at": ...}` の形です（`strata_control/profiles.py:312-323`）。履歴ファイルがない場合も、profile の現在 revision を読み込めれば現在項目は表示されます。

過去の履歴ファイルについて、この一覧処理はファイル名・通常ファイルかどうか・更新時刻を確認しますが、内容の JSON 構文や内容と revision の一致までは検証しません。内容の検証は `rollback` の読込処理で行われます（`strata_control/profiles.py:312-323,326-344`）。

## 適用条件と副作用

一覧作成時に現在 profile を `profiles.load()` で読み込み、名前・ファイル種別・ファイルサイズ・JSON・profile schema を検証します。profile が未保存または不正なら履歴一覧も失敗します（`strata_control/profiles.py:150-166,312-323`）。通常、履歴一覧処理自体は履歴ファイルや profile の値を更新しません。ただし `load()` は昇格実行によってアクセス権が変わった profile を一度修復して読み込む場合があります（`strata_control/profiles.py:150-166`）。また、読込中に権限エラーが発生すると CLI 共通処理が Strata 管理下の既知ディレクトリを修復してコマンドを再実行する場合があります（`strata_cli/cli.py:2085-2104,2166-2173`）。

human 出力は `--quiet` で標準出力から抑制されます。JSON 出力時は `main()` が通常の `_run()` 経路へ直接進むため、`--quiet` を併用しても JSON は抑制されません（`strata_cli/cli.py:2232-2248`）。

## 出力と失敗経路

成功時の終了コードは `0` です。既定の human 表示では履歴1件につき1行、JSON では前述の schema 付きオブジェクトを stdout に出します（`strata_cli/cli.py:535-542,1006-1010`）。

profile 名は小文字英字で始まり、小文字英数字・`_`・`-` のみを使える最大64文字です。不正名はエラーコード `2`、profile が未保存、通常ファイルでない、1 MiB 超過、読み取れない、または内容が無効の場合は主にコード `5` で失敗します（`strata_control/profiles.py:25,48-51,150-166`; エラーコードの定義は `:30-35`）。JSON モードでは失敗結果も stdout に `schema_version: 1`、`ok: false`、`error.code`、`error.message` を持つ JSON として出ます。human モードのエラーは `strata: ...` の形式で stderr に出ます（`strata_cli/cli.py:527-532,2166-2173`）。権限エラーは既知の保存領域を修復して再試行され、再試行後も失敗する場合はコード `5` のアクセスエラーになります（`strata_cli/cli.py:2085-2104`）。

`--output` に許可外の値を指定した場合や必須の `NAME` を省略した場合は、profile 処理に入る前に argparse が usage/error を stderr に出して終了コード `2` で終了します（`strata_cli/cli.py:99-101,2223-2231`）。

## 調査範囲

指定 commit の Terminal CLI parser、profile 分岐、profile 履歴 API、成功・エラー出力経路を確認しました。同 revision の CLI `--help` は補助実行していません。別の Release binary、各 OS での実際のファイル時刻精度、権限修復が成功する環境条件は実機確認していません。

## 根拠

- `strata_cli/cli.py:99-101` — `profile history` の parser、必須位置引数 `name`、`--output` の choices と既定値。
- `strata_cli/cli.py:508-515,2232-2237` — one-shot の `--json` / `--quiet` と `--json` から JSON 形式への切替。
- `strata_cli/cli.py:1006-1010,535-542` — 履歴呼出し、人間向け行、JSON 成功出力。
- `strata_cli/cli.py:527-532,2085-2104,2166-2173,2223-2231,2236-2248` — エラー形式・コード、権限修復再試行、parser エラー、quiet の適用。
- `strata_control/profiles.py:25,38-55` — profile 名規則と保存ディレクトリの決定。
- `strata_control/profiles.py:150-166` — 現在 profile の読込・検証、アクセス権修復。
- `strata_control/profiles.py:312-323` — 履歴ファイルの絞り込み、現在項目、時刻順ソート。
- `strata_control/profiles.py:326-344` — rollback 時に行う履歴内容と revision の検証（history 一覧では実行しない）。
