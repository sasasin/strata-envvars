# `STRATA_TIMESKIP_DEADLINE_S`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Time-skip の revision helper `integrations/harness/revise_once.py` が、Harness に依頼する1回の agent turn の制限時間（秒）を設定します。Strata 本体や Time-skip run 全体の制限時間ではなく、この helper が起動した Harness agent の URL 待ちと turn 完了待ちに使われます。

## 値と判定

| 状態 | `revise_once.py` の値 |
|---|---|
| 未設定 | 240.0 秒 |
| 数値として変換できる設定値 | Python の `float()` で変換した値（小数を含む） |
| 空文字・数値でない文字列 | `float()` 変換に失敗し、argparse のエラーで helper は終了する |
| `--deadline` が指定された場合 | CLI 引数の値が環境変数由来の既定値を上書きする |

コードに正数への clamp や有限値の検査はありません。負数では Harness URL 待ちの timeout が負になり、待ちループは開始せず失敗します。`nan` では全体の期限比較が成立せず turn 待ちに入らず終了します。正の無限大を受け付けた場合、URL 待ちは最大120秒ですが、その後の turn 完了期限は実質無制限になります。

## 有効になる条件

- `integrations/harness/revise_once.py` が revision command として実行されることが必要です。この変数を読むのは同ファイルだけで、通常の `strata timeskip run` 自体は値を読みません。
- `strata timeskip run --revise-command ...` は revision command に親プロセスの環境を引き継ぎ、`STRATA_TIMESKIP_PROMPT` と `STRATA_TIMESKIP_ATTEMPT` を追加します。そのため、この変数を実行環境に設定すれば helper から参照されます。Time-skip の HTTP 呼び出しでは revision command のパスはホスト側で設定され、呼び出し側から任意の shell command を渡す設計ではありません。
- `--deadline` を revision command に渡すと、この環境変数より CLI 値が優先されます。

## 実行時の詳細

値は `main()` が argparse の引数定義を評価するときに一度読み取られます。プロセス内で再読込・キャッシュ更新する処理はありません。設定値を実行中に変更しても、既に計算した期限には反映されません。

helper は開始時刻に期限を計算し、Harness の URL 出力を `min(120秒, 指定秒数)` で待ちます。その後、session の `turn/end` を最大0.5秒間隔で確認し、期限までに終わらなければ stderr に `revise_once: the attempt did not finish within ...; stopping the Harness and reporting a made attempt` と出して非ゼロで終了します。終了処理では Harness に SIGTERM を送り、8秒で終了しなければ kill を試みます。上位の Time-skip CLI は revision command の非ゼロ終了を失敗として記録します。

ここでいう期限は agent turn の待ち時間を制限します。URL 待ちは指定秒数を上限としますが、agent 起動・HTTP セッション作成・prompt 送信などの処理には、この期限を個別に強制する仕組みはありません。

## 根拠

- `integrations/harness/revise_once.py:53-55,70-82` — 既定値と `float(os.environ.get(...))` による取得、`--deadline` 引数。
- `integrations/harness/revise_once.py:102-115,138-160,174-187` — 期限計算、Harness 起動、URL・turn 待ち、timeout 出力と終了処理。
- `integrations/harness/_bridge.py:109-122` — Harness URL 待ちの timeout ループ。
- `strata_cli/cli.py:1557-1570` — revision command に環境を継承し、prompt と attempt 番号を設定。非ゼロ終了を run error にする。
- `apps/host/server/timeskip.mjs:418-437,446-455` — HTTP 経由で開始する場合の revision command 設定と子プロセス環境の構築。
