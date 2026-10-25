# `strata runtime start`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/management.py`、`strata_control/runtime.py` |
| 関連 command | [`runtime status`](../status/README.md)、[`runtime stop`](../stop/README.md) |

## 役割

保存済み profile の設定で Strata server を起動し、CLI の終了後も動作するローカルのバックグラウンド service として管理します。server の起動とモデルの読み込みを確認してから戻ります。profile がまだない場合は、先に [`strata profile create`](../../profile/create/README.md) で run config から作成します。

`strata serve --profile CONFIG.json` は呼び出した terminal に結び付いた foreground 起動です。terminal を閉じても動かす管理起動には `runtime start` を使い、停止には `runtime stop` を使います。

## 基本的な使い方

```sh
# 保存済み profile の候補と実行予定を確認（起動しない）
strata runtime start --profile four-gpu --plan --output json

# profile の server を起動し、ready になるまで最大 300 秒待つ
strata runtime start --profile four-gpu

# GUI アプリの所有プロセスが終了したら server も停止する
strata runtime start --profile four-gpu --die-with-pid 12345
```

成功後は [`strata runtime status`](../status/README.md) で状態を確認し、停止するときは [`strata runtime stop`](../stop/README.md) を実行します。登録されている option は [`docs/cli/README.md`](../../../README.md) の `strata runtime start` 節を参照してください。

## 実行モード

| モード | 動作 |
| --- | --- |
| 起動計画 (`--plan`) | profile と起動候補を読み、2回読み取った候補と設定 digest が一致することを確認します。process は起動せず、計画には `would_start: false` が含まれます。通常起動で行う engine component の事前確認は、この plan 分岐では呼び出されません。 |
| 管理 service 起動 | owner host を切り離して起動し、server 起動、ready file と instance の照合、config/launch の attestation、1 token generation の readiness probe を経て `ready` を返します。 |
| 待機なし (`--wait 0`) | owner host の state file ができるところまで待ち、その後 `starting` を返します。server の readiness 完了は待ちません。 |

例:

```sh
strata profile create four-gpu --from-config /absolute/path/to/strata-model.json
strata runtime start --profile four-gpu --plan --output json
strata runtime start --profile four-gpu
strata runtime status --profile four-gpu
strata runtime stop --profile four-gpu
```

## 起動時の主な動作と副作用

- `--profile` は必須で、既存の保存済み profile 名を指定します。profile から run config と有効設定を解決して server 引数を組み立てます。設定された engine component がある場合、起動前に当該 PC 用 component の存在と integrity を確認し、不備があれば process を始める前に拒否します。
- `--plan` なしでは、同じ profile の前回 owner が残した server/engine process を識別情報で個別確認して終了し、古い state があれば回復を試みます。その後 owner host を別 session/process group で起動します。host は端末が閉じても動き、通常は `runtime stop`、server 終了時、または指定された `--die-with-pid` の process が終了したときに止まります。
- owner host は profile の run config を用いて `serve.server` を起動します。managed server には acquisition 無効の環境変数を渡すため、この起動経路は不足ファイルを install/download しません。起動成功は ready file の instance ID だけでは判定せず、管理対象 server との照合、実際に読まれた config bytes と launch arguments の attestation、および1 token generation probe を確認します。意図的に lazy load する model は unloaded のままの場合があります。
- runtime state、owner control 用 socket/token、host log、server log、child marker などを runtime directory に作成・追記します。既定場所は state directory 内の `strata/runtime` で、`STRATA_RUNTIME_DIR` で変更できます。override は絶対パスかつ owner-only でなければなりません。POSIX では owner 限定の directory/file を要求し、Windows では ACL を確認します（ACL を持たない FAT/exFAT では他アカウントが読める可能性を stderr に警告します）。
- 起動失敗時に engine log の末尾が取得できれば CLI は stderr に場所と直近3行を表示します。失敗した host の診断先は runtime log です。`--quiet` は成功時の人間向け表示を抑えますが、JSON 出力は抑えません。

## 注意点

- `--wait` は 0〜600 秒（既定300秒）、`--shutdown-timeout` は 0〜300 秒（既定30秒）です。CLI の `float` 変換後に範囲検証されます。起動待機時間が尽きると server は必ずしも停止されず、`starting` と `startup_wait_expired`、終了コード8を返すため、その後の状態確認・停止は `runtime status` / `runtime stop` で行います。
- `--die-with-pid` は整数 PID を受け取り、その時点で実行中の process でなければ拒否します。process の開始 token も記録して追跡し、指定 process が終了すると instance を drain して停止します。PID を省略すれば呼び出し元 process の終了では停止しません。
- 通常の起動は単なる状態確認ではなく、background process を開始し、server/engine を起動して model を読み込みます。`--plan` は起動しない計画表示です。
- readiness probe は1 token の生成確認です。長時間の安定性、回答品質、throughput、複数 GPU の適合性を示すものではありません。調査した資料では、release 配布物やすべての OS/backend/engine 組み合わせをこの commit の source checkout と照合していません。

## 出力と失敗

- 通常の human 出力は `PROFILE: STATE` と、利用可能なら instance ID、API URL、config/launch 検証状況、readiness 状況、error code を1行で表示します。`--output json` または alias の `--json` は `schema_version: 1` を含む JSON を stdout に出します。
- 起動完了前の待機期限切れは `ok: false`、`state: "starting"`、`error: "startup_wait_expired"`、終了コード8です。起動失敗は通常終了コード6で、host が起動できない場合は runtime log の場所をエラーに含みます。engine log の内容は human 出力時 stderr に補足されます。
- 不正な引数型・範囲、存在しない profile、無効な PID、利用できない platform transport、runtime directory の権限不備、engine component の欠落/不整合などは拒否されます。エラーは human 時 stderr、JSON 時は `ok: false` の JSON で返されます。argparse による構文エラーは usage とエラーを stderr に出します。

## 根拠

- `strata_cli/cli.py:197-212,508-515` — `runtime start` の登録、必須 `--profile`、option の型・既定値、および共通 `--json` / `--quiet` の追加。
- `strata_cli/cli.py:782-826` — profile の有効設定解決、server/engine launch 引数の構成。
- `strata_cli/cli.py:1331-1373,1376-1388,2119-2173` — runtime management 呼び出し、human/JSON 出力、終了コード、エラー表示、engine log 補足。
- `strata_control/management.py:188-230` — profile 検証、start option の範囲検証、`--plan` の二重候補照合、journal 記録と実起動への引き渡し。
- `strata_control/runtime.py:81-92,101-129`、`strata_control/paths.py:13-21` — platform transport、runtime directory の条件と既定 state directory。
- `strata_control/runtime.py:458-482` — 起動候補作成と engine component の事前検証。
- `strata_control/runtime.py:518-599` — PID追跡、値の範囲、owner host の切り離し起動、ログ、wait/readiness と timeout の結果。
- `strata_control/runtime.py:744-770,840-875,904-988` — owner host、managed server 起動時の acquisition 無効化、config/launch attestation、ready instance の照合、generation probe、state 判定。
- `strata_cli/cli.py:527-542,2217-2247` — human/JSON エラー形式、`--json` と quiet の共通処理。
- `docs/TERMINAL_QUICKSTART.md:41-50`、`docs/TERMINAL.md:61-67,94`、`docs/CLOSING.md:8-18` — 利用例、foreground/background の違い、managed host の終了動作。これらは同じ checkout の利用者向け資料であり、個別 option の根拠は上記 parser と実装。
