# `--attempts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `## main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--attempts` |
| 別名 | なし |
| 値 | 整数 `N`。parser は整数変換のみを行い、下限未満は実行時に 0 へ補正します。 |

## 役割

基準版を checkpoint してチェックした後、改訂コマンドによる候補作成・チェック・判定を繰り返す最大回数を指定します。指定する回数は基準版のチェックを含まず、基準版の後に行う改訂の数です（`strata_cli/cli.py:356-358`, `strata_control/time_skip.py:430-459`）。

## 使い方

```sh
strata timeskip run --workspace ./project --prompt "改善内容" --attempts 3 --revise-command 'your-revision-command'
```

`--workspace` と `--prompt` は必須です。`--revise-command` は1回分の改訂を実行するコマンドであり、候補ディレクトリ内で動きます（`strata_cli/cli.py:352-365`）。関連項目は [`--revise-command`](--revise-command.md)、[`--workspace`](--workspace.md)、[`--output`](--output.md) を参照してください。

## 値と既定値

- 省略時は `2` です。CLI parser は `type=int, default=2` を設定しています（`strata_cli/cli.py:356-358`）。
- 文字列を整数へ変換できない場合、`argparse` の引数エラーとなり、処理本体に入る前に usage とエラーが表示されます。終了コードは `argparse` 標準の `2` です（parser 定義: `strata_cli/cli.py:356`）。
- 負数も整数として parser を通りますが、実行時に `TimeSkipRun` が `max(0, int(max_attempts))` として保持するため、`0` と同じく改訂ループは 0 回です（`strata_control/time_skip.py:321-330`, `strata_control/time_skip.py:442-443`）。
- 0 以上の値に parser 上限や独自の最大値検証はありません。指定数が大きいほど、ループ回数・候補ディレクトリ・チェック実行数が増えます（`strata_cli/cli.py:356-358`, `strata_control/time_skip.py:442-460`）。ソースから安全な上限値は確認できません。

## 実行時の動作

実行開始時に workspace の基準版を保存してチェックを行い、その後 `1` から `N` まで各回を実行します。各候補は直前に選択された checkpoint から作られます。判定が `keep` の場合だけ候補を checkpoint として選択し、拒否・判定不能の候補を次回の入力にはしません（`strata_control/time_skip.py:430-459`, `strata_control/time_skip.py:463-472`）。

`N=0` では基準版の checkpoint とチェックまでは行いますが、改訂ループには入りません。attempt 記録がない場合、最終判定は `inconclusive`（改訂なし）になります（`strata_control/time_skip.py:442-443`, `strata_control/time_skip.py:558-582`）。

`--revise-command` を省略すると CLI の改訂関数は `None` を返します（`strata_cli/cli.py:1572-1583`）。ただし `N>0` なら内部ループ自体は `N` 回進み、各回で候補を複製して同じチェックを行います。したがって parser help の「改訂なし」とは、改訂コマンドを呼ばないという意味です。同じチェック結果で意図した改善が示されない場合、決定ロジックは `inconclusive` とします（`strata_control/time_skip.py:442-460`, `strata_control/time_skip.py:551-556`）。

## 適用条件と副作用

- `--workspace` が既存ディレクトリでなければ、run は開始されずエラーコード `2` になります（`strata_cli/cli.py:1557-1564`）。
- run の状態、checkpoint、候補は state directory 以下に作成されます。`--attempts` は `--state-dir` と `STRATA_TIMESKIP_DIR` による保存先選択を変えません（`strata_cli/cli.py:366-368`, `strata_cli/cli.py:1476-1485`, `strata_control/time_skip.py:321-347`, `strata_control/time_skip.py:408-420`）。
- `TimeSkipRun` は workspace を基準版へコピーして調査し、改訂ごとに独立候補ディレクトリを作ります。`--attempts` による自動適用はありません。workspace への反映は別の `timeskip apply` 操作です（`strata_control/time_skip.py:17-19`, `strata_control/time_skip.py:430-459`, `strata_control/time_skip.py:597-604`）。
- 各反復でチェックが実行されるため、値を増やすとチェック処理も繰り返されます。チェック定義がない場合は stderr に警告を出します（`strata_cli/cli.py:1561-1568`）。改訂コマンドを指定する場合、そのコマンドは候補ディレクトリで `shell=True` により実行され、prompt と試行番号を環境変数で受け取ります（`strata_cli/cli.py:1572-1583`）。

## 出力とエラー

人間向け出力では run ID と状態、実行された attempt の判定、最終 decision、status 確認・apply dry-run の案内を表示します（`strata_cli/cli.py:1590-1602`）。`--output json` では成功時に run 結果を JSON で返します（`strata_cli/cli.py:1585-1589`）。

run 中の例外は run 状態 `failed` として記録されます。失敗時の CLI 終了コードは `6` で、人間向けでは stderr、JSON 出力ではエラー JSON になります。指定した改訂コマンドが非 0 で終了すると、その終了値と stderr または stdout の末尾最大 300 文字を含むエラーになります（`strata_cli/cli.py:1577-1583`, `strata_control/time_skip.py:480-493`, `strata_cli/cli.py:1585-1602`, `strata_cli/cli.py:527-532`）。

## 根拠

- parser 定義・既定値・help 文: `strata_cli/cli.py:352-369`
- run の前提検査、値の引き渡し、改訂関数、出力と失敗処理: `strata_cli/cli.py:1557-1602`
- 回数の下限補正・永続化・checkpoint・反復・採用規則・最終判定: `strata_control/time_skip.py:321-372`, `strata_control/time_skip.py:408-478`, `strata_control/time_skip.py:558-593`
- workspace を保持し明示的 apply まで候補を反映しない設計と apply 処理: `strata_control/time_skip.py:15-23`, `strata_control/time_skip.py:597-604`
