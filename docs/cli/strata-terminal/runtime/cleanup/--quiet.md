# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime cleanup` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる。 |

## 役割

cleanup が成功したときの人間向け要約を抑制します。cleanup の対象や停止処理そのものは変えません。

## 使い方

```sh
strata runtime cleanup --quiet
strata runtime cleanup --profile my-profile --quiet
```

`--profile` を指定すると、そのプロファイルに属する残存プロセスだけを処理します。

## 値と既定値

このフラグは `action="store_true"` で、明示しない場合は偽です。cleanup parser 自身は `--quiet` を宣言せず、one-shot parser 群へ共通オプションを追加するループに `runtime_cleanup` が含まれることで受理されます（`strata_cli/cli.py:233-237,508-515`）。値の引数、範囲、追加 validation はありません。

## 実行時の動作

`strata runtime cleanup` は `strata_control.runtime.cleanup(a.profile)` を実行します。成功時に人間向け出力を抑制するかは CLI 共通の `main` で処理され、`--quiet` があり出力形式が human の場合、`_run` の stdout を一時捕捉します。終了コードが 0 なら捕捉した要約は表示されません（`strata_cli/cli.py:1331-1344,2236-2247`）。

quiet は cleanup の処理結果を変更しません。cleanup は所有者が失われた Strata 管理下の残存サーバー・エンジンを処理し、実行中の所有インスタンスや Strata が記録したプロセスと一致しないプロセスには触れません。`--profile` がある場合は名前を検証して対象を限定し、該当する古い状態があれば stale state の回復も試みます（`strata_control/runtime.py:670-684`）。

## 適用条件と副作用

- `--quiet` は成功時の human 要約にだけ作用し、プロセスの終了、状態の回復、戻り値には影響しません（`strata_cli/cli.py:1334-1344`、`strata_control/runtime.py:670-684`）。
- `--output json` または `--json` と併用した場合、JSON 出力は quiet の対象外です。`main` は出力形式が `json` の場合は捕捉を行わず、cleanup は `schema_version` と処理結果を JSON として出力します（`strata_cli/cli.py:1337-1339,2232-2243`）。
- quiet 実行でも cleanup の失敗判定と終了コードは維持されます。`stuck` または `unverifiable` があれば結果は失敗、終了コード 6 です（`strata_control/runtime.py:682-684`）。失敗時は捕捉した stdout が stderr に転送され、stderr に直接書かれたエラーも抑制されません（`strata_cli/cli.py:2241-2248`）。

## 出力とエラー

通常の human 成功時は `ended N leftover process(es)` と、該当する場合に停止できなかったプロセス数・識別できず残したプロセス数を出します。`--quiet` はこの成功要約を隠します。失敗時には終了コード 6 となり、quiet によって隠れた human 出力があれば stderr に再掲されます（`strata_cli/cli.py:1337-1344,2241-2248`）。JSON モードでは結果レコードが出力され、quiet でも隠されません。

## 根拠

- parser と quiet の共通登録: `strata_cli/cli.py:233-237,508-515`
- cleanup の呼び出し、human/JSON 出力、終了コード: `strata_cli/cli.py:1331-1344`
- 成功時の捕捉と失敗時の stderr 転送: `strata_cli/cli.py:2236-2248`
- cleanup の対象、安全条件、結果判定: `strata_control/runtime.py:670-684`
- 関連する利用者向け説明: `docs/TERMINAL.md:226`（CLI 全体で quiet が human informational output を抑制し、JSON/JSONL は抑制しない旨）、`docs/CLOSING.md:55`（runtime cleanup の位置づけ）

調査範囲は指定 revision の checkout 内の Terminal CLI parser、dispatch、cleanup 実装、および同 checkout の関連文書です。Release 配布物や別 OS での実行確認は行っていません。
