# `--engine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--engine` |
| 別名 | なし |
| 値 | 必須の文字列。エンジン実行ファイルのパス、または `component:strata-engine` |

## 役割

プランを作る対象エンジンを指定します。`strata tune plan` は指定先の実行可能性を調べ、ヘルプ出力からフラグを読み取れた場合は、バックエンド別の探索候補がそのエンジンで受理されるか絞り込みます。ここで行うのは探索計画の作成で、ベンチマーク測定やプロファイル変更ではありません。

## 使い方

```sh
strata tune plan --engine /path/to/strata-engine --backend cuda --model example-model
```

インストール済みエンジンコンポーネントを選ぶ場合は、次のように指定できます。

```sh
strata tune plan --engine component:strata-engine --backend cuda --model example-model
```

`--engine`、`--backend`、`--model` はこのサブコマンドで必須です（`strata_cli/cli.py:398-402`）。

## 値と既定値

- 値は必須です。既定値はなく、指定しないと `argparse` の必須引数エラーになります（`strata_cli/cli.py:398-399`）。
- 通常の文字列は `Path` に変換されます。相対パスは CLI を起動した作業ディレクトリを基準に使われ、存在・実行権限の事前検証はありません（`strata_cli/cli.py:1621-1629`）。
- `component:` で始まる値はコンポーネント参照として扱われます。`component:strata-engine` は `--backend` を渡して、この PC 用のエンジンを解決します。未知の component 名や利用可能なエンジンがない場合は解決エラーです（`strata_control/engine_component.py:950-966`, `strata_cli/cli.py:1621-1628`）。
- 空文字列を含む通常の値も parser 段階では拒否されません。数値範囲など `--engine` 固有の追加 validation はありません。

## 実行時の動作

値は `_engine_arg` を通って `tuning.plan_tuning` に渡されます（`strata_cli/cli.py:1715-1721`）。プラン作成時、CLI は対象を `--help` 付きで最大20秒実行し、stdout と stderr の両方から `--` で始まる小文字英数字・ハイフンのフラグ名を収集します。`.py` で終わる値は現在の Python インタープリターで起動し、それ以外は指定パスを直接起動します。隣に `engine-component.json` がある場合、パッケージ同梱ライブラリ用の検索パスも加えます（`strata_control/tuning.py:177-202`, `205-224`）。

取得できたフラグ一覧に探索 dimension が使うフラグが欠けていれば、その dimension は除外理由付きで計画に記録されます。フラグを取得できなかった場合は `engine_flags_known` が false となり、静的なバックエンド表で計画を作ります。存在しないパスでは通常この fallback で計画を作れます。一方、ファイル同一性の読取など別のファイル操作で OS エラーになった場合は CLI エラーになり得ます（`strata_control/tuning.py:151-174`, `205-224`, `723-768`; `strata_control/tune_history.py:48-80`）。

人間向け出力には選択されたエンジン、フラグの読取状態、探索・除外 dimension、試行数と時間の上限が表示されます。`--output json` では同じ計画が JSON で返ります（`strata_cli/cli.py:1715-1739`）。同じ表記の `--engine` は `strata tune run` にもありますが、別のコマンドスコープであり、この文書の対象ではありません（`strata_cli/cli.py:414-416`）。

## 適用条件と副作用

- パス指定では、計画作成時に対象エンジンの `--help` が実行されます。通常の推論・測定はこの `plan` 経路では実行しません。
- component 参照は、`--backend` に合うインストール済みエンジンを解決できる環境でのみ使えます。
- ヘルプ出力を読み取れない場合の fallback は計画作成を妨げませんが、実エンジンの受理フラグとの照合はできません。backend と実体が食い違うときは、計画に全 dimension 除外の理由が示される場合があります（`strata_control/tuning.py:734-751`）。
- `plan_tuning` はファイル同一性を計画データへ含めますが、このコマンドは探索状態やアクティブ profile を更新しません（`strata_control/tuning.py:753-768`, `strata_cli/cli.py:1738`）。

## 出力とエラー

- `component:` 参照の解決失敗は `ProfileError`（終了コード 5）に変換されます。人間向けでは `strata: ...` を stderr に、JSON 出力時は `ok: false` とエラー情報を出力します（`strata_cli/cli.py:1624-1628`, `527-532`, `2166-2188`）。
- パス指定の `--help` 起動が OS エラーや timeout になった場合は、フラグ未取得として静的表に fallback します（`strata_control/tuning.py:205-224`）。
- 未指定の必須値、未知の backend など parser エラーの終了動作は `argparse` によります。`--engine` による出力ファイル作成や既存ファイル上書きは確認できません。

## 根拠

- parser 定義と必須性: `strata_cli/cli.py:395-412`
- 値の変換・component 解決: `strata_cli/cli.py:1621-1629`, `strata_control/engine_component.py:950-966`
- エンジン起動方法、環境、help フラグ読取: `strata_control/tuning.py:177-224`
- backend・実フラグによる探索候補検証と plan 作成: `strata_control/tuning.py:151-174`, `723-768`
- CLI からの呼び出し、表示・JSON 結果: `strata_cli/cli.py:1715-1739`
- 共通エラー形式: `strata_cli/cli.py:527-532`, `2166-2188`

同一 revision の CLI `--help` は実行していません。説明は checkout 内の parser と実処理のソースに基づきます。リリース配布物や全 OS/backend での実行確認は調査範囲に含めていません。
