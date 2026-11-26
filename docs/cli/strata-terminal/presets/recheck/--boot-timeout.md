# `--boot-timeout`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査時の作業ツリーは `main` で未変更。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--boot-timeout` |
| 別名 | なし |
| 値 | 秒数。Python の `float` として解釈される |

## 役割

再確認で設定を測定する worker を起動した後、`/health` が ready を返すまで待つ時間を指定する。これは `strata presets recheck` 全体の制限時間ではなく、再確認中の worker 起動ごとの ready 待ち時間である。プロンプト速度の再測定や、条件に応じた標準設定の測定で worker を起動し直す場合、それぞれに適用される。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config.json> --boot-timeout 1200
```

`<preset>` は再確認する保存済み preset、`<profile-or-config.json>` はその preset の対象 profile または run configuration で、ここでは起動待ちを 1200 秒にする例。

## 値と既定値

- 値は秒単位の浮動小数点数。省略時は `900.0` 秒（15 分）。
- `argparse` の `type=float` による変換のみで、正数・有限値かどうかの個別 validation はない。数値に変換できない文字列は引数解析エラーになる。
- 0 または負の値では ready 待ちループに入らず、worker 起動失敗（`TIMEOUT`）として扱われる。正の小数はその秒数で待つが、タイムアウト理由の表示は秒数を整数化する。
- `NaN` や無限大を拒否する明示的な検査はない。`NaN` は期限判定を通らず、失敗理由を整数化する段階で `ValueError` となり、CLI の一般エラー経路に入る。正の無限大は有限の期限を設けないため、worker が終了するか ready になるまで待ち得る。

## 実行時の動作

parser はこのオプションを `strata presets recheck` に登録し、値を `WorkerSession` の `boot_timeout_s` に渡す。worker 起動後は期限まで 127.0.0.1 の `/health` を確認し、HTTP 200 で ready とする。期限までに ready にならなければ `StartFailed("TIMEOUT", ...)` を発生させる。

再確認処理は worker の起動失敗を測定結果として受け取り、保存済み設定を起動できなかった場合は verdict を `retune` にする。その結果は preset の `recheck.last_result` に記録され、JSON 出力では verdict・reason・result・preset、通常出力では「Not as fast as before…」と再調整案内が返る。オプション自体は preset の設定値や engine に渡す引数を変更しない。

## 適用条件と副作用

- `strata tune auto` にも同名のオプションがあるが、別コマンドの parser スコープであり、この文書の対象外。`presets recheck` 側の既定値も独立して定義されている。
- `--work-dir` を指定しない場合、再確認用の一時作業ディレクトリが作られ、プロセス終了時に削除される。指定した場合はそのディレクトリが再確認ログ等の保存場所として残る。タイムアウトは worker のログを失敗扱いにするが、再確認コマンドの通常フローでは preset の `last_result` を更新する。
- worker は測定のたびに起動され、ready 待ちの後に測定処理へ進む。起動に失敗した worker は終了処理される。

## 出力とエラー

- タイムアウト時、worker session は `TIMEOUT` と「engine was not ready within … s」を含む `StartFailed` を返す。再確認処理はこれを捕捉して `retune` 判定に変換するため、単独のタイムアウトだけでは CLI の終了エラー経路にせず、結果を preset に記録する。
- 数値変換できない値は `argparse` の引数エラー（終了コード 2）。`NaN` の整数化など、再確認中に発生する `ValueError` は `presets_command` がエラーコード 2 として処理し、通常出力では stderr に `strata: ...`、JSON モードでは `ok: false` の JSON を出力する。

## 根拠

- `terminal/strata_cli/tune_commands.py:88-96` — `presets recheck` parser と positional 引数、`--boot-timeout` の型・既定値。
- `terminal/strata_cli/tune_commands.py:615-644` — 再確認処理で値を `WorkerSession(boot_timeout_s=...)` へ渡す箇所。
- `terminal/strata_control/tune_session.py:527-572` — worker ごとの作業ファイル・プロセス起動。
- `terminal/strata_control/tune_session.py:574-597` — ready 待ち期限、timeout の `StartFailed` 化、失敗ログ保持。
- `terminal/strata_control/tune_session.py:598-610` — 起動済み worker の終了処理。
- `terminal/strata_control/autotune.py:959-975` — 起動失敗の捕捉と `retune` 判定。
- `terminal/strata_cli/tune_commands.py:652-661` — 再確認結果の保存後に返す出力。
- `terminal/strata_control/presets.py:441-458` — `last_result` 等を preset に記録する処理。
- `terminal/strata_cli/tune_commands.py:101-110, 472-530` — human/JSON 出力と `ValueError` のエラー処理。
- `terminal/strata_cli/tune_commands.py:34-52, 55-96` — `strata tune auto` 側の同名 option は異なる parser scope であること。
