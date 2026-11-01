# `--preset`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。調査時の `git status --short --branch` は `## main...origin/main`。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--preset NAME` |
| 別名 | なし |
| 値 | 保存済み launch preset の名前（文字列） |

## 役割

保存済み launch preset、または同名の実行中 launch から接続先情報を選びます。`strata connect <app>` がアプリ用の設定を表示するときに、URL・API key などの既定値を得るために使います。

## 使い方

```sh
strata connect opencode --preset Office
```

アプリ ID を省略するとアプリ一覧を表示します。この経路では `--preset` は接続設定の生成に使われません。`--url`、`--key`、`--key-env`、`--model`、`--context` を指定すると、対応する preset / 実行中 launch 由来の値より優先されます。

## 値と既定値

- 値は `NAME` 文字列です。parser は `metavar="NAME"` のみを指定し、名前の形式や空文字列を独自に検証しません。値を省略すると argparse が usage とエラーを表示します（parser 定義: `strata_cli/launch/cmd.py:156-173`）。
- 指定名は preset ファイル名に使う際、小文字化・許可文字への変換などの slug 化を受けます（`strata_cli/launch/settings.py:355-360`）。
- preset が存在しなければエラーにはせず、`--preset` からの情報は得られません。preset ファイルが読み取れない、または破損している場合は `PresetError`（`ValueError`）となり、トップレベルのエラー処理で失敗します（`strata_cli/launch/store.py:88-103`、`strata_cli/cli.py:2166-2173`）。
- URL の最終的な既定値は、該当する実行中 launch の URL、保存 preset の port を使う localhost URL、いずれもなければ `http://127.0.0.1:8080` です。port の既定値は `strata_cli/launch/settings.py:50` にあります。

## 実行時の動作

1. `connect` は `launch_info(NAME)` を呼びます。これは稼働中 launch を slug 化した名前で探し、保存 preset も `missing_ok=True` で読みます（`strata_cli/launch/cmd.py:636-658`）。
2. 同名の実行中 launch があれば、その URL が preset の port より優先されます。実行中 launch がなく preset があれば、preset の `port` を localhost の URL に使います（同 `cmd.py:641-658`）。
3. 各値の選択順は次のとおりです（同 `cmd.py:945-950`）。

   | 接続情報 | 選択順 |
   | --- | --- |
   | URL | `--url` → 選ばれた launch/preset の URL → `http://127.0.0.1:8080` |
   | API key | `--key` → `--key-env NAME` で指定した環境変数の値 → launch の設定または preset の key → 空文字列（後段で harness 用 placeholder に置換） |
   | model | `--model` → 実行中設定の `model_name` → `strata` |
   | context | `--context` → 実行中設定の `--max-context` → 32,768 tokens |

保存 preset のモデル名と context は `launch_info()` の戻り値に含まれず、`connect` の model/context の既定値にはなりません。parser の help は `--preset` を「address, key and model」を得るものと説明しますが（`strata_cli/launch/cmd.py:167`）、現行コードでは preset 由来の model は接続先に渡されず、実行中 config に model がない場合は `strata` になります。これは help と実装の差として確認した点です。

`connect` は preset を読み取るだけで、`last_used` を更新しません。利用履歴を更新する `store.touch_used()` は `strata launch` の実行経路にあります（`strata_cli/launch/cmd.py:858-863`、`strata_cli/launch/store.py:139-144`）。設定ファイルへの書き込みは別オプション `--write` によって行われます。

## 適用条件と副作用

- `--preset` の値は `strata connect` にアプリ名（位置引数 `harness`）も指定した場合の接続情報選択に適用されます。アプリ名なしの場合は一覧を出して終了します（`strata_cli/launch/cmd.py:923-937`）。
- 指定 preset と同名の launch が稼働していれば、その実行 URL と設定内の API key が利用されます。稼働していなくても保存 preset があれば port と key を利用できます。どちらもない場合は通常の既定値へフォールバックします（`strata_cli/launch/cmd.py:636-658, 945-950`）。
- このオプション単独ではネットワーク接続や設定ファイル書き込みを行いません。アプリ設定への書き込みは `--write`、server への確認リクエストは `--check` の処理です（`strata_cli/launch/cmd.py:961-977, 1003-1028`）。
- API key は既定でマスクして表示されます。`--show-key` を併用すると実値が表示されるため、端末出力やログの取り扱いに注意してください（同 `cmd.py:951-955, 978-991`）。

## 出力とエラー

- 指定した preset が見つからないだけなら、`--preset` 自体のエラーにはならず既定の URL、key の placeholder、`strata` model、32K context を使って設定を生成します。key は `run_connect` 内では空文字列となり、`harness.target()` が placeholder に置き換えます（`strata_cli/launch/cmd.py:652-658, 945-950`、`strata_cli/launch/harness.py:272-273`）。
- preset の JSON が読めない、または構造が壊れている場合は `PresetError` が `ValueError` として CLI 共通処理に渡ります。人間向けでは `strata: ...` のエラーを stderr に出し、既定の終了コード 2 で終了します（`strata_cli/launch/store.py:88-103`、`strata_cli/cli.py:2166-2173`、`strata_cli/cli.py:527-530`）。
- `--output json` では通常の接続情報を JSON で stdout に出します。key は JSON の設定本文を含めマスクされます。`--show-key` は JSON 経路の表示を解除しません（`strata_cli/launch/cmd.py:951-960`）。

## 根拠

- parser と help: `strata_cli/launch/cmd.py:156-173`
- preset / 稼働 launch の検索と接続情報生成: `strata_cli/launch/cmd.py:636-658`
- 接続先の値の優先順位、描画、JSON 出力: `strata_cli/launch/cmd.py:945-977`
- 人間向け表示、`--check`・`--write` の別動作: `strata_cli/launch/cmd.py:978-1028`
- preset 読み込み、欠落・破損時の挙動: `strata_cli/launch/store.py:88-103`
- preset slug 化と既定 port: `strata_cli/launch/settings.py:50, 355-360`
- harness の key placeholder と context 既定値: `strata_cli/launch/harness.py:272-273`
- CLI 共通エラー処理: `strata_cli/cli.py:2166-2173, 527-530`
