# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime cleanup` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | saved profile 名。省略可能。先頭は小文字 `a-z`、続きは小文字 `a-z`、数字、`_`、`-` の最大64文字。 |

## 役割

cleanup の対象を1つの saved profile に記録された残存プロセスへ絞ります。省略すると記録済みの全 profile を対象にします。Strata が開始した server や engine でも、その起動元 owner が動作中のものは cleanup の対象になりません。

## 使い方

```sh
strata runtime cleanup --profile demo
```

`demo` は saved profile 名です。`--profile` を付けない場合は全 profile の残存プロセス記録を調べます。

## 値と既定値

値は必須ですが、オプション自体は任意です。未指定時は `None` となり、全 profile が対象です。指定値は runtime 側で profile 名として検証されます。名前は小文字英字で始まり、以降に小文字英字・数字・`_`・`-` を使え、長さは1〜64文字です。大文字、パス、空文字、65文字以上などは拒否されます。重複指定時の特別な扱いは実装にありません（`argparse` の通常の単一値引数として最後に解析された値が使われます）。

## 実行時の動作

parser は `runtime cleanup` に `--profile` を値付きで登録し、値を必須とはしていません。cleanup の dispatcher は値を `strata_control.runtime.cleanup()` に渡します。実装は指定値を profile 名として検証し、`strata_control.procs.end_leftovers(profile=...)` に渡します。プロセス記録を絞る条件は記録中の profile 名との完全一致です。指定なしでは profile 条件を使いません。

対象プロセスは記録上の PID だけで停止されるのではありません。記録時の開始時刻 token とコマンドラインが現在のプロセスと一致し、記録された親プロセスが同一のまま生存していないことを確認します。起動元がまだ生きているプロセスは残存扱いしません。PID が再利用された記録やコマンドラインが異なる記録は、別プロセスとして扱われ、記録だけが破棄されます。記録がないプロセスは対象外です。

`--profile` を指定した場合、プロセス処理後にその profile の runtime 状態ファイルも確認します。状態があり owner host の lease が失われている場合は、孤立した子プロセスの終了と private runtime state の回収を試みます。回収時には owner token と child marker、子プロセスの終了、ready file、POSIX の socket 等を検査します。owner host の lease が有効な実行中インスタンスには回収を行いません。この状態回収経路は profile 指定時だけです。

## 適用条件と副作用

残存と確認されたプロセスは終了されます。POSIX では SIGTERM を送り、最大8秒待っても同じ PID・開始時刻・コマンドラインで動作していれば SIGKILL を試みます。Windows では再確認後に `taskkill /F /PID` を実行します。終了したプロセスの記録は削除されます。存在しない PID や別プロセスに再利用された PID の stale record も削除対象です。

開始時刻またはコマンドラインを確認できず対象か判定できないプロセスは終了せず、`unverifiable` として報告されます。停止後も同一プロセスが確認される場合は `stuck` として報告されます。profile 指定時の stale runtime 回収エラーはこの関数内で抑止され、回収できない状態ファイル等が残ることがあります。

## 出力とエラー

既定の human 出力は終了数を表示し、停止できなかったプロセス数と識別不能で放置したプロセス数があれば併記します。`--output json` または one-shot 共通 alias の `--json` を指定すると、`schema_version` と cleanup 結果を含む JSON が stdout に出ます。結果に `stuck` または `unverifiable` がある場合は失敗扱いとなり終了コード6、それ以外は0です。

不正な profile 名など `ValueError` 系の失敗は、human 出力では `strata: ...` を stderr に出し、既定の終了コード2を返します。JSON 出力では `{schema_version, ok: false, error: {code, message}}` 形式です。OS のファイル操作エラーは終了コード6として処理されます。引数の値を省いた場合など parser エラーは `argparse` により usage とエラーを stderr に出し、終了コード2です。

## 根拠

- `strata_cli/cli.py:233-237` — `runtime cleanup` の parser と `--profile` の任意性、説明。
- `strata_cli/cli.py:508-515` — cleanup parser への `--json` と `--quiet` 共通 option 追加。
- `strata_cli/cli.py:1331-1344` — profile 値の処理関数への引き渡し、human/JSON 出力と終了コード。
- `strata_cli/cli.py:2119-2173` — `ValueError` のエラー表示、終了コード、および JSON エラー形式。
- `strata_control/runtime.py:95-99`、`strata_control/profiles.py:25` — runtime の profile 名検証と許容形式。
- `strata_control/runtime.py:670-684` — `cleanup()` の profile 絞り込み、stale host recovery、結果状態と終了コード。
- `strata_control/runtime.py:285-294`、`297-378` — owner lease 判定と stale runtime の回収条件・副作用。
- `strata_control/procs.py:253-264`、`269-291` — 記録の profile 完全一致、親生存・PID token・コマンドラインによる残存判定、stale record の削除。
- `strata_control/procs.py:294-342` — 終了直前の再検証、POSIX/Windows の終了方法、stuck/unverifiable の結果。
