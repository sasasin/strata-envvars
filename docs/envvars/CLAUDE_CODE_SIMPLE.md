# `CLAUDE_CODE_SIMPLE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部アプリ自身の環境変数の解釈は対象外。

## 役割

Strata の `strata connect claude-code` が Claude Code 用の接続設定を生成するとき、サーバーの context が 40,960 以下なら、`CLAUDE_CODE_SIMPLE` を文字列 `"1"` として設定へ加えます。Strata の実行環境からこの名前の値を読むコードはなく、Strata のサーバーや推論 engine の動作を変えるスイッチではありません。

Claude Code 用の生成設定は `~/.claude/settings.json` の `env` オブジェクトに入ります。`strata connect claude-code` は値を画面または JSON 出力として提示し、`--write` は確認後にそのファイルを書きます。Monitor の Connect 画面でも同じ設定を表示・コピー・書き込みできます。

## 値と判定

Strata は値を parse せず、生成時に固定文字列 `"1"` を入れるか、キーを生成しないかを選びます。

| `strata connect` に渡る context | 生成される設定 | Strata 側の意味 |
|---|---|---|
| 40,960 以下 | `"CLAUDE_CODE_SIMPLE": "1"` | Claude Code 用設定へこの値を出力 |
| 40,960 より大きい | キーを出力しない | Strata による設定追加なし |

context は `--context`、起動情報、または既定値 32,768 の順で選ばれます（`--context` が truthy の場合に優先）。`harness.target()` は context を整数へ変換し、未指定または 0 の場合は 32,768 を使います。設定ファイルを `--write` で既存 JSON に merge する場合、40,960 以下なら新しい `"1"` が既存の同名値に優先します。40,960 より大きい場合は生成 JSON にキーが含まれず、merge は既存キーを削除しないため、既存 `settings.json` の値が残り得ます。

## 有効になる条件

この出力は `claude-code` harness を render したときにだけ作られます。通常の engine 起動、別 harness、Strata 自身のサーバーモードでは参照されません。context がちょうど 40,960 の場合も出力されます。

context は `strata connect` の `--context`、起動情報（プリセット等）、既定値 32,768 で決まります。`CLAUDE_CODE_SIMPLE` を Strata の親プロセス環境に設定しても、この生成条件には使われません。`--context` が指定されると起動情報より優先します。

## 実行時の詳細

`claude_env()` が URL、認証 token、model、context / output 上限などの環境設定を辞書として構成し、context が 40,960 以下ならこの辞書に `CLAUDE_CODE_SIMPLE="1"` を追加します。`claude_file()` はその辞書を `{"env": ...}` の JSON にします。render は辞書とファイル内容の両方を返し、CLI は環境設定を表示し、JSON mode では JSON payload の `env` に含めます。`--write` は `~/.claude/settings.json` へ書き込みます。

この値の判定は `claude_env()` を呼び出すたびに context から計算され、Strata 内で環境変数として cache されません。エラー・警告を出す専用経路は確認できません。`--write` 時に標準入力が TTY でない場合は `--yes` がなければ stderr に `strata: --write asks first; run it in a terminal or add --yes.` を出して終了コード 2 になりますが、これは書き込み確認の経路です。

## 根拠

- 値の追加条件と `claude-code` harness の設定先: `strata_cli/launch/harness.py:111-120,229-231`。
- context の取得元、既定値、render 結果への格納: `strata_cli/launch/cmd.py:945-951`, `strata_cli/launch/harness.py:266-280`。
- CLI の表示、JSON 出力、書き込み: `strata_cli/launch/cmd.py:953-960,978-991,1011-1028`。
- JSON merge では新しい値が優先され、生成にない既存 key は保持: `strata_cli/launch/harness.py:288-305,314-320`。
- Monitor の Connect 画面は同じ render 結果から設定を表示・コピー・書き込み: `strata_cli/launch/monitor_ext.py:136-178,303-328`。
- 候補名の完全一致検索では、本番コード上の参照は生成処理 `strata_cli/launch/harness.py:116` のみ。`strata_cli/launch/harness.py:185` は説明文、`tests/terminal/test_launch.py:1235,1239` は生成内容のテストであり、Strata が実行環境から値を読む箇所ではありません。
