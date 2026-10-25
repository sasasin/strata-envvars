# `strata tune auto --leave-ram`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--leave-ram` |
| 別名 | なし |
| 値 | 整数の割合 `PERCENT`。0〜50 |

## 役割

自動 tuning の目標をメモリに余裕を残す `room` として扱い、候補設定が現在の設定よりシステムメモリを大きく消費する場合に候補から外すための指定です。値が0以外なら、`--goal` の省略値 `speed` は `room` に切り替わります（`strata_cli/tune_commands.py:29-32,184-196`）。

## 使い方

```sh
strata tune auto my-profile --leave-ram 20
```

`my-profile` は tuning 対象の保存済み profile 名、または run configuration の JSON パスです。`--goal speed` を併記しても、`--leave-ram` が0以外なら実行時の目標は `room` になります（`strata_cli/tune_commands.py:26,178-188`）。

## 値と既定値

- `argparse` は整数として読み取り、省略時は `0` です。parser 上に `choices` はありませんが、処理時に0〜50の範囲を検証します（`strata_cli/tune_commands.py:31,184-185`）。
- 負数、51以上はエラーです。小数は整数変換に失敗して parser エラーになります。0は RAM の希望を追加せず、単独では `speed` から `room` へ切り替えません（`strata_cli/tune_commands.py:31,184-187`）。
- 同じオプションを複数回指定した場合は `argparse` の通常の `store` 動作で最後の値が使われます（`strata_cli/tune_commands.py:31`）。

## 実行時の動作

検証後、0以外の値を `autotune.Options.ram_wish_pct` に渡します。`goal` が `speed` のときは `room` に変更し、明示的に `room` または `room:MiB` を指定した場合も RAM の希望を併用します（`strata_cli/tune_commands.py:139-147,184-196`; `strata_control/autotune.py:50-68`）。

`room` では各候補の測定後に、候補が基準設定より RSS peak を `5% + 512 MiB` 超えて増やしていないか、最小空き RAM が基準より `max(512 MiB, 総 RAM の3%)` を超えて減っていないかなどを確認します。違反した候補は失敗扱いとなり、探索対象から外れます（`strata_control/autotune.py:493-500,691-703`）。

指定値そのものを総 RAM に掛けて「必ずその割合を空ける」閾値にする処理は確認できませんでした。割合の数値は `ram_wish_pct` に渡されますが、上記の候補比較では非0かどうかだけが分岐条件で、比較幅には使われません。一方、0以外なら preset の `choices.leave_ram_pct` に値が記録されます（`strata_cli/tune_commands.py:194-196,236-239`; `strata_control/autotune.py:700-703`）。

この希望とは別に、測定開始時は利用可能メモリを読み、最低3,584 MiBと測定に必要な追加量を確保できない場合は待機または候補の skip が起きます。空きメモリを読めない場合、この tuner 側のガードは判定を通し、エンジン自身のガードに委ねます（`strata_control/autotune.py:35,268-301`）。

## 適用条件と副作用

- メモリ比較による候補制約は `goal == "room"` のときに適用されます。`--leave-ram` が0以外なら `speed` から自動的にこの目標へ切り替わります（`strata_cli/tune_commands.py:184-196`; `strata_control/autotune.py:695-703`）。
- このオプションは対象 profile / run configuration 自体のメモリ量を変更しません。自動 tuning は engine worker を使って測定し、試行履歴を記録します。測定結果が `improved` または `default_confirmed` で `--no-save` がなければ preset を作成し、その選択情報に非0の値を保存します（`strata_cli/tune_commands.py:217-230,236-249`）。
- `--output json` でなければ進捗は標準エラーへ出ます。`--work-dir` 未指定時は一時ディレクトリを作り、`--status-file` 指定時は進捗 JSON を更新します（`strata_cli/tune_commands.py:205-219,209-215`）。

## 出力とエラー

- 0〜50の範囲外は終了コード `2`。人向け出力では `strata: --leave-ram is a percentage from 0 to 50` を標準エラーへ出します。`--output json` の場合は `ok: false` と `error.code`, `error.message` を含む JSON を標準出力へ出します（`strata_cli/tune_commands.py:95-108,184-185`）。
- 正常な tuning の終了コード・結果表示は測定結果によって決まります。測定前の対象解決や engine 不在などでも別のエラー経路があり、このオプション固有の成功終了コードはありません（`strata_cli/tune_commands.py:178-190,230-261`）。
- 値を省略した場合や整数でない値を渡した場合は `argparse` の usage/error 経路です。余分な引数も parser error に送られます（`strata_cli/tune_commands.py:31`; `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/tune_commands.py:20-46` — `strata tune auto` parser、型、既定値、同階層の `--goal`。
- `strata_cli/tune_commands.py:139-147,174-196` — goal の解釈、値の検証、goal 切り替え、tuner option への引き渡し。
- `strata_cli/tune_commands.py:205-261` — 進捗、work directory、status file、試行記録、preset 保存、出力と終了コード。
- `strata_control/autotune.py:35,50-68,268-301` — tuner の RAM 既定ガードと測定前の待機・skip 条件。
- `strata_control/autotune.py:437-500,691-711` — 候補測定と room goal における基準設定とのメモリ比較。
- `strata_cli/cli.py:2217-2231` — `argparse` の余分な引数処理。
