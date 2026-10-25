# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。調査時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 取らないフラグ。未指定時は無効 |

## 役割

成功したときの human 向け案内を表示しないためのフラグです。再起動処理の実行内容、待ち時間、検証条件は変えません。`strata runtime restart` 自体は、所有状態を確認した実行中 runtime を停止・再起動し、保存済み profile で再度実行します（実処理は `strata_control/runtime.py` の `restart()` に委譲されます）。

## 使い方

```sh
strata runtime restart --profile work --quiet
```

JSON を利用する場合は `--json` または `--output json` を指定できます。この場合 `--quiet` より JSON 出力が優先されます。

```sh
strata runtime restart --profile work --quiet --json
```

## 値、既定値、validation

`--quiet` は `action="store_true"` のフラグで、値を取りません。`runtime_restart` を含む one-shot parser 群に共通ループから追加され、parser の default は `argparse.SUPPRESS` です。未指定時は属性自体が設定されませんが、CLI は `getattr(a, "quiet", False)` で扱うため実効既定値は無効（false）です。`--quiet` 固有の値変換・範囲 validation はありません。別名も定義されていません。

## 実行時の動作と相互作用

`--quiet` を指定し、出力形式が human の場合、CLI は `_run()` 中の stdout を最大 64 KiB のバッファに捕捉します。終了コード 0 なら捕捉した内容を表示しません。`runtime restart` が返す profile の状態・instance ID・API URL・検証状態などの human 行も、この成功時抑制の対象です。restart の実行自体は通常どおり行われるため、停止・再起動や profile/runtime の検証を省略する機能ではありません。

`--json` は `--output json` と同じ扱いで、`main()` が `a.output` を `json` に設定します。JSON/JSONL 出力形式の場合は quiet 捕捉を行わず、その機械可読出力を抑制しません。`runtime restart` の parser で有効な形式は `human` と `json` です。

## 出力と失敗経路

- human 出力で成功した場合、stdout への human 案内は抑制されます。stderr は捕捉対象外です。
- `_runtime()` が失敗結果を返した場合、human 結果行は stdout から捕捉されます。終了コードが非 0 なら、その捕捉内容を stderr に移して表示します。64 KiB を超えて切り詰められた場合は、省略を示すメッセージも stderr に出ます。エンジンログのヒントは `_runtime()` が直接 stderr に書くため、そのまま表示されます。
- `_run()` が扱う `ValueError`、`OSError`、`ClientError`、割り込み等のエラーも通常のエラー経路に従い、quiet はエラー表示や終了コードを無効化しません。JSON 指定時はエラー JSON が stdout に出ます。
- argparse の未知引数・不正な引数による parser エラーは `_run()` より前に処理されるため、quiet 捕捉の対象外です。

## 副作用と適用条件

このフラグは `strata runtime restart` の one-shot parser に限って追加されます。restart の副作用は `--quiet` の有無で変わりません。具体的な restart 実行は `runtime_action()` から `runtime.restart()` に渡され、journal に `runtime.restart` 操作として記録されます。`--plan` を指定した場合は runtime を drain せず計画を返す動作ですが、quiet はその human 計画出力にも同じ抑制規則で作用します。

## 根拠

- `strata_cli/cli.py:238-254` — `runtime_restart` parser、`--profile` 必須、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — one-shot parser 群への `--json` と `--quiet` の追加、`--quiet` は値なしで default `argparse.SUPPRESS`。
- `strata_cli/cli.py:1331-1373` — runtime 結果を human/JSON で出力し、失敗時に engine log hint を stderr へ出す処理。
- `strata_cli/cli.py:527-542`, `2119-2193` — CLI の成功・エラー出力、`_run()` の例外処理。
- `strata_cli/cli.py:2196-2214`, `2217-2248` — stdout 捕捉の上限、quiet の実効既定値、成功時の抑制、失敗時の stderr への退避、JSON 時に抑制しない条件。
- `strata_control/management.py:188-201`, `292-336` — runtime action の検証、restart の計画/実行分岐、journal 操作と `runtime.restart()` への引き渡し。
- `strata_control/runtime.py:702-731` — restart 引数の検証と runtime host への restart 要求。

調査は上記 commit の checkout 内の parser・実装を対象としました。同一 revision の CLI help と Release 配布物は照合していません。
