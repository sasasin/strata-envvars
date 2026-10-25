# `--wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | `SECONDS`。`argparse` の `float` として解釈 |

## 役割

engine を利用中の Strata server が停止するまで、rollback 処理が待つ秒数を指定します。rollback は、直前の更新で保持された engine を使うよう状態を切り替える操作です。`--wait` は稼働中の engine 自体を停止しません。

## 使い方

```sh
strata components rollback --wait 120
```

この例では、rollback 処理が稼働中 engine の停止を最大 120 秒待ちます。

## 値と既定値

- 値は `float` 秒です。オプションを省略した場合の parser 上の既定値は `None` で、実行時に `0.0` として updater context に渡されます。
- ソースに正の範囲や上限の validation はありません。`float` に変換できない文字列は `argparse` が拒否し、usage とエラーを表示して終了コード 2 になります。
- 0 または負数は、rollback 内の待機関数では待たずに稼働状態を確認します。稼働中なら Busy エラーになります。
- 同じ `--wait` を複数回指定した場合の専用処理はありません。通常の `argparse` の引数処理により最後に指定した値が使われます。

## 実行時の動作

1. `strata components rollback` parser は共通 option 定義を使い、`--wait` を `type=float, default=None` で登録します。
2. 実行時に `a.wait or 0.0` が updater context の `wait` に渡されます。rollback 分岐では `_maybe_wait()` を通した後に `rollback_engine()` を呼びます。
3. `_maybe_wait()` は、`ctx.wait` が真なら対話確認を行わず戻ります。値が未指定または 0 の場合は稼働 engine を確認し、TTY の対話実行で Strata 自身の `launch-` engine 以外が動いていれば、待つかどうかを質問します。`y` / `yes` なら 6 時間待つ設定になります。JSON 系出力、非 TTY、Strata の `launch-` engine では質問せず、後続の rollback 判定に進みます。
4. `rollback_engine()` は更新ロックを取得し、previous engine があることを確認してから `wait_until_idle()` を実行します。待機関数は最初に稼働状態を確認し、稼働中なら設定秒数の期限まで 3 秒間隔で再確認します。engine が停止すれば次の検証・切替処理へ進みます。

`--wait` は feed のダウンロードや rollback 対象の選択には使われません。rollback はネットワークから取得せず、保持済み engine の署名・内容検証と、この PC で起動時に選ばれることの確認を行います。切替後は state に rollback pin、previous/active engine、履歴を記録し、条件により保存済み tuning preset に再確認マークを付けます。

## 適用条件と副作用

- 待機対象は updater の `serving_now()` が検知する managed engine、または共有 activity lease を保持する server です。lease の確認は取得を試みて直ちに閉じます。
- 待機中は 3 秒ごとに稼働状態を再確認します。期限までに停止しない場合、または待機秒数が 0 以下の場合は rollback をせず Busy エラーになります。
- 明示した負数は真値として `_maybe_wait()` の対話確認を飛ばしますが、updater では期限切れ扱いとなり、稼働中なら即座に Busy になります。
- `float` の範囲検証がないため、Python が受理する `nan` / `inf` も parser を通ります。稼働状態が続く場合、`wait_until_idle()` の期限比較ではこれらが通常の有限 timeout として機能せず、停止するまで待ち続ける可能性があります。
- rollback は `--wait` の有無にかかわらず状態ファイルを書き換えます。待機中に状態を変更する処理はありません。previous engine がない場合は待機前に終了し、rollback 先が壊れている、または現在の PC に適合しない場合はエラーになります。

## 出力とエラー

- 人向け出力では待機開始時に `An engine is serving; waiting for it to stop before updating.` を表示します。rollback 成功時は切替元・切替先と preset の扱いを表示します。
- `--output jsonl` では待機イベントを JSONL に出します。`--output json`（または one-shot 共通 option の `--json`）では通常の待機メッセージを抑制し、失敗は `ok: false` と error object を含む JSON にします。
- timeout または 0 以下の待機時間で engine がまだ稼働中なら Busy エラーとなり、終了コード 7 です。TTY で質問に `y` / `yes` 以外を答えた場合も追加待機は設定されず、rollback 側で Busy になる可能性があります。待機中に Ctrl-C を受けた場合は Busy ではなく、CLI の割り込み経路で終了コード 130 になります。
- previous engine がない、または既にその previous engine が有効な場合は終了コード 2。previous engine の検証失敗や現在の PC に適合しない場合は終了コード 5 です。CLI は `UpdateError` のメッセージを人向けなら stderr、JSON 系なら JSON に出力します。

## 根拠

- `strata_cli/update_cmd.py:30-59` — `_common()` による `--wait` の parser 定義と、`components rollback` での共通定義の利用。
- `strata_cli/update_cmd.py:163-196` — 秒数を context に渡す処理、rollback の分岐、成功出力。
- `strata_cli/update_cmd.py:62-84` — human / JSON / JSONL のイベント出力。
- `strata_cli/update_cmd.py:167-172,225-234` — 失敗出力、`UpdateError` と割り込みの終了処理。
- `strata_cli/update_cmd.py:237-252` — 未指定時の対話確認、質問条件、肯定時の 6 時間待機。
- `strata_control/updater.py:275-297` — 稼働 engine / activity lease の検出。
- `strata_control/updater.py:300-311,316-333` — 待機期限、再確認間隔、context の既定値。
- `strata_control/updater.py:1033-1078` — previous の確認後の待機、検証と rollback state 更新。
- `strata_control/updater.py:54-59,65-75` — `UpdateError` と Busy の終了コード・メッセージ。
- `strata_cli/cli.py:508-515,2119-2137` — one-shot の `--json` / `--quiet` 登録と update/rollback handler への委譲。

調査は上記 commit のソース checkout に限定しました。異なる OS での lease 実装や Release 配布物の実行結果は確認していません。
