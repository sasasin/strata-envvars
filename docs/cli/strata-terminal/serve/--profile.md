# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--profile` |
| 別名 | `--config` |
| 値 | 必須。保存済みプロファイル名、または run config の JSON パス |

## 役割

serve が使うプロファイルまたは run config を選びます。parser 上の metavar は `CONFIG.json` ですが、保存済みプロファイル名も受け付けます。`--profile` と `--config` は同一引数（`config`）に格納され、いずれも必須です（`strata_cli/cli.py:46-47`）。

## 使い方

```sh
strata serve --profile default --plan
strata serve --config ./strata-model.json --plan
```

1つ目は `default` という保存済みプロファイル、2つ目は指定した JSON ファイルを選び、`--plan` で実効設定を確認します。`--plan` を外すと前景サーバーを起動します（`strata_cli/cli.py:63-64, 935-955`）。

## 値と既定値

- 値の省略はできず、オプション自体も省略できません（`strata_cli/cli.py:47`）。デフォルト値はありません。
- 値が `.json` 拡張子（大文字小文字を問わない）、絶対パス、または `/`・`\\` を含む場合はファイルパスとして扱います。それ以外は保存済みプロファイル名として読み込みます。ファイルパスは `~` を展開して解決されます（`strata_control/profiles.py:382-388`）。
- 保存名は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です。保存プロファイルは設定ディレクトリ内の `<name>.json` から読み込まれます（`strata_control/profiles.py:25, 38-55, 150-166`）。
- JSON パスを選んだ場合、ファイルには `args`（文字列配列）、`exe` と `tokenizer`（空でない文字列）が必要です（`strata_control/profiles.py:135-147`）。

## 実行時の動作

選んだ参照を `profiles.resolve()` に渡し、得られた run config を読み込みます。保存済みプロファイルの場合は参照先 run config に加え、保存された serving overrides と profile revision を読み込みます（`strata_cli/cli.py:545-547`; `strata_control/profiles.py:150-166, 382-388`）。

serve の実効値では、コマンドラインで指定された個別 serving option が最優先、次に保存プロファイルの override、run config、既定値の順です。`STRATA_BATCH_TELEMETRY` は run config に値がない場合に既定値より先に使われます。この優先順位は `--profile` の参照先を選ぶ機能そのものとは別で、`--profile` は他の serving option を上書きしません（`strata_cli/cli.py:745-779`）。

起動計画には選んだ source config、保存プロファイル ID・revision（保存名を指定した場合）、実効値、engine 引数が含まれます。`--plan` は計画を出力して終了します。通常実行では選択した run config のパスを server に渡し、server を前景で実行します（`strata_cli/cli.py:782-826, 935-955`）。このオプション単独でプロファイル設定を書き換える処理はありません。

## 適用条件と副作用

- 保存名として認識された値は既存の保存プロファイルでなければなりません。ファイル指定と判定された値が保存名へフォールバックすることはありません（`strata_control/profiles.py:382-388`）。
- 通常実行では推論 server を起動し、プラットフォームが POSIX または Windows の場合は runtime の共有 activity lease を取得して終了時に閉じます。`--plan` では server を起動せず、lease も取得しません（`strata_cli/cli.py:940-955`）。
- 保存プロファイルは設定ディレクトリから読みます。`STRATA_PROFILE_DIR` があればそれを優先し、なければ OS ごとの設定ディレクトリを使います（`strata_control/profiles.py:38-46`）。読み取り時に private-file 修復処理が呼ばれるため、アクセス権修復が必要な状態ではプロファイルファイルに修復が及ぶことがあります（`strata_control/profiles.py:150-166`）。

## 出力とエラー

- 保存名に対応するプロファイルがない場合は、`strata profile create` を案内する `ProfileError` になります。壊れた・不正なプロファイルや run config の読込にも失敗します（`strata_control/profiles.py:150-166`; `strata_control/profiles.py:135-147`）。
- 人間向け出力ではエラー文を stderr に `strata:` 付きで表示します。`--output json` では JSON エラーを出力しますが、この形式は `--plan` と組み合わせた場合のみ許可されます。`--output jsonl` は失敗イベントを出力します（`strata_cli/cli.py:527-533, 829-835, 915-941, 2165-2173`）。
- `--profile` / `--config` の値を省略すると argparse が usage とエラーを表示し、終了コード 2 になります。読み込み失敗の終了コードはエラー種別により異なり、保存プロファイル不在や run config 読込失敗はコード 5 です（`strata_cli/cli.py:47`; `strata_control/profiles.py:135-165`）。

## 根拠

- parser、必須指定、alias、metavar: `strata_cli/cli.py:46-47`
- 参照から config への解決: `strata_cli/cli.py:545-547`; `strata_control/profiles.py:382-388`
- 保存プロファイルの場所、検査、読込: `strata_control/profiles.py:25, 38-55, 150-166`
- JSON run config の形式とエラー: `strata_control/profiles.py:135-147`
- 実効値の優先順位と検証: `strata_cli/cli.py:745-779`
- 起動計画と server 実行: `strata_cli/cli.py:782-826, 915-955`
- エラー表示: `strata_cli/cli.py:527-533, 829-835, 2165-2173`
