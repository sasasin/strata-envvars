# `strata doctor --components`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--components` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`argparse` の `store_true`） |

## 役割

help は「コンポーネント一覧を含める（既定）」と説明します。ただし、この revision の実装では `--components` の有無にかかわらずコンポーネント一覧を調査・出力します。明示しても追加の動作はなく、省略して一覧を無効にする方法もありません。

## 使い方

```sh
strata doctor --components
strata doctor --profile my-profile --components --output json
```

`--profile` は任意で、保存済みプロファイル名または run config JSON のパスを受け取ります。`--components` はプロファイル指定の有無で意味を変えません。

## 値と既定値

- 値引数はありません。`--components=true` のような指定はこのフラグの値として定義されていません。
- parser は `action="store_true"` を指定し、省略時の namespace 値は `False` です。
- しかし実行側はこの値を参照していません。`_doctor` は毎回コンポーネント診断関数を呼び、その結果を human または JSON で出力します。したがって表示上の既定動作は一覧を含みます。
- 同じフラグを複数回指定しても真偽値は `True` のままで、別の処理は起きません。

## 実行時の動作

`strata doctor` は `_doctor` を経由して `strata_control.doctor.inspect` を呼びます。`--components` 自体は呼び出しに渡されず、診断結果の `components` 配列は常に作られます。

- `--profile` を省略すると、プロファイル固有のファイル検査は行わず、`terminal_cli` と任意の `monitor_tui` の項目、およびプロファイル選択を促す情報 issue を返します。
- プロファイルを指定すると、run config からエンジン、tokenizer、関連ファイル等を確認します。必須項目の欠落・無効状態は error issue になります。
- `--live` は別オプションです。指定するとホスト GPU の照会も行います。`--components` は live probe を有効にしません。
- `--output human`（既定）は項目ごとの状態・名前・詳細と issue を表示します。`--output json` は `schema_version`、`ok`、診断全体を含む JSON を出力します。

## 適用条件と副作用

診断処理はインストールを実行せず、対象コンポーネントの存在・状態を読む処理です。ただし CLI 共通の起動処理として、Windows では parser の実行前にユーザー token の既定 owner/DACL を設定しようとします（失敗しても続行）。保存済み profile の読み込みでアクセス拒否が起きた場合は、profile reader が Strata 管理下ファイルのアクセス修復を試みて再読込する経路があります。これらは `--components` 固有の作用ではありません。

## 出力と失敗

- 診断結果が正常なら終了コード `0`、`report["ok"]` が false なら `5` です。
- profile/config の読み込みなどで例外が発生すると共通エラーハンドラーに入り、human 出力では `strata: ...` を stderr に、JSON 出力では `ok: false` と code/message を出力します。未知の引数は argparse の usage/error 経路で終了コード `2` になります。
- `--components` 単独では、診断の成否・終了コード・出力を変えません。

## 根拠

- parser と help 文言: `strata_cli/cli.py:109-113`。
- doctor dispatch と出力形式・終了コード: `strata_cli/cli.py:1023-1045`, `strata_cli/cli.py:2138-2139`。
- `inspect` の呼び出しに `components` フラグを渡さない点: `strata_cli/cli.py:1025-1028`。
- profile 未指定時にも component 項目を追加する処理: `strata_control/doctor.py:146-160`。
- profile 指定時の component 検査と issue 判定: `strata_control/doctor.py:162-235`。
- 例外出力と終了コードの共通処理: `strata_cli/cli.py:527-532`, `strata_cli/cli.py:2166-2188`, `strata_cli/cli.py:2223-2231`。
- Windows の共通起動時処理: `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389`。
- 保存済み profile の読み込み時に行うアクセス修復: `strata_control/profiles.py:150-166`, `strata_control/private_files.py:476-484`。

調査範囲は上記 commit の checkout 内の Terminal CLI と関連診断実装です。別 revision の配布バイナリや全 OS での実行結果は照合していません。
