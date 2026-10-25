# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 必須。保存済み profile の名前 |

## 役割

停止・drain する Strata の管理対象 runtime を、保存済み profile 名で指定します。profile の JSON ファイルパスや任意の config パスではありません。`runtime stop` はその profile が所有するローカル instance に対する操作です。

## 使い方

```sh
strata runtime stop --profile office
```

停止前に対象 owner と instance を確認するには、plan の ID を実行時の条件として渡します。

```sh
strata runtime stop --profile office --plan
strata runtime stop --profile office --if-owner-id OWNER_ID --if-instance-id INSTANCE_ID
```

plan 表示だけでは停止しません。実行時に ID 条件を付ける場合は、plan で確認した ID を指定してください。

## 値と既定値

- `--profile` は必須で、省略時の既定値はありません。値は `strata_cli/cli.py` の argparse では文字列として受け取り、profile 名として検証されます。
- 名は小文字の `a-z` で始まり、続きは小文字英字・数字・`_`・`-` のみ、全体で1〜64文字です。大文字、空文字、パス区切りなどは名前検証で拒否されます。
- 該当する保存先の profile が存在しない、通常ファイルでない、または内容が profile schema と一致しない場合も失敗します。profile 保存先は `STRATA_PROFILE_DIR` があればそれを使い、未設定時は OS と `XDG_CONFIG_HOME` / `APPDATA` に応じた既定ディレクトリです。
- `--profile` 自体に alias はありません。`--json` と `--quiet` はこの one-shot parser に別途追加される共通出力オプションであり、profile 名の別名ではありません。

## 実行時の動作

parser は `--profile` を必須引数として受け取り、runtime dispatch がその値を `management.runtime_action()` に渡します。stop 操作は profile 名を検証し、通常の停止では保存済み profile を読み込んで revision を得た後、`runtime.stop` の操作記録を作って runtime 制御へ渡します。したがって、この指定は停止対象の選択に使われ、保存 profile や profile 設定を変更する指定ではありません。

`--plan` を付けると、指定名の runtime 状態を照会し、所有されている状態なら owner ID・instance ID 等を含む plan を表示します。plan は `would_drain: false` / `would_stop: false` で、ここでは停止処理を行いません。`--if-owner-id` / `--if-instance-id` は同じ profile に対する任意の実行前提条件です。plan と一緒に ID 条件を付けることはできません。実行時に owner ID を指定すると、事前照会で owner と instance の両方を照合し、さらに owner host 側でも指定 ID を照合します。instance ID だけを指定した場合は owner host 側でその ID を照合します。

## 適用条件と副作用

- 停止対象は Strata が管理するローカル runtime です。別 profile や、管理記録のない任意プロセスを指定する機能ではありません。
- 通常の停止では owner host に stop を要求し、子 server を終了させます。Windows では owner pipe を閉じて drain を要求し、POSIX では server に `SIGTERM` を送ります。停止期限を超えると子プロセスツリーを kill し、失敗結果を返す場合があります。
- owner host が既に失われていると、通常 RPC ではなく、記録された profile の leftover process を PID・起動時刻・command line で再確認して終了させる回収経路に入ります。この経路は `--if-owner-id` / `--if-instance-id` の照合より先に選ばれるため、ID 条件は live owner が応答する通常経路の停止対象確認として扱ってください。
- 通常実行では operation journal に停止操作と結果が記録されます。`--plan` は停止操作を記録せず、状態照会のみを行います。
- `--wait` は `1..600` 秒の有限値で、既定値は330秒です。profile の意味や対象を変えず、stop 処理に渡す待ち時間を指定します。

## 出力とエラー

- 成功時は通常、人向け出力で profile 名と状態を表示します。`--output json` または alias の `--json` では結果を JSON で出力します。成功した plan は plan オブジェクトを出力します。
- profile 名・`--wait` 等の入力検証エラーは、人向け出力では標準エラーに `strata: ...` を出し、該当する `ProfileError` の終了コードで終了します。`--output json` / `--json` では JSON エラーを標準出力に出します。存在しない profile は終了コード5です。
- runtime 停止結果が失敗なら、状態・エラーを含む結果を出し、runtime が返した終了コード（未指定時は6）で終了します。stop 期限超過はコード8、残留プロセスを安全に識別できない／終了できない stale 回収はコード6になります。
- live owner への制御接続ができない場合は制御不可エラー（コード3）、応答待ち期限超過はコード8として扱われます。プロセス停止が期限内に完了しない場合は子ツリー終了を試みても失敗状態になり得ます。

## 根拠

- `strata_cli/cli.py:197-202,226-232` — runtime のコマンド階層と `runtime stop` の parser 定義。`--profile` は必須、alias なし。
- `strata_cli/cli.py:510-515,1331-1373` — one-shot parser に `--json` / `--quiet` を追加する箇所、profile 引数の dispatch、plan・人向け・JSON 出力と終了コード処理。
- `strata_control/profiles.py:25-27,38-56,150-166` — profile 名の正規表現、保存先、保存 profile 読み込みと未存在時のエラー。
- `strata_control/management.py:113-117,271-291` — wait 値の有限範囲検査、stop plan・ID 条件・profile revision 読み込み・operation journal と runtime stop 呼び出し。
- `strata_control/runtime.py:604-611,614-667` — plan が表示する所有状態、stop の待ち時間・ID validation、live owner RPC と stale owner 回収経路。
- `strata_control/runtime.py:402-440,990-1012,1166-1224` — 制御 RPC の失敗経路、OS ごとの drain/終了処理、owner host 側での ID 再照合。
- `strata_control/journal.py:376-393` — 通常 stop の開始・結果記録。

調査範囲は指定 commit の Terminal CLI とその runtime/profile 管理実装です。CLI の `--help` は補助実行せず、parser と呼び出し先のソースを照合しました。Release 配布バイナリでの挙動差は確認していません。
