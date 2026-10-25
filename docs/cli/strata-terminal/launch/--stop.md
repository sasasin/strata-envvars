# `--stop`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--stop` |
| 別名 | なし |
| 値 | 取らないフラグ（`store_true`）。 |

## 役割

`strata launch` が管理するサーバーを停止します。`--preset NAME` を同時に指定すると、その preset 名に対応する launch profile だけを対象にします。指定しない場合は `launch-` で始まる全 profile を対象にします。

## 使い方

```sh
# strata launch が管理するサーバーを停止
strata launch --stop

# Office preset に対応するサーバーだけを停止
strata launch --stop --preset "Office"
```

## 値と既定値

`--stop` 自体は値を取りません。省略時は停止処理に入りません。`--preset` は通常の文字列引数で、停止分岐では `strata_cli.launch.settings.slug()` により小文字化・安全な文字への置換・最大48文字への切り詰めを行い、profile ID `launch-<slug>` を対象にします。名前の存在確認や preset ファイルの読み込みはこの分岐では行わないため、未登録名でも停止対象を照会し、該当する実行中状態がなければ「実行中のものはない」と表示します（`strata_cli/launch/cmd.py:141-146,661-663`、`strata_cli/launch/settings.py:310-315`）。

## 実行時の動作

- `--stop` は preset 一覧・削除の分岐の後、通常の起動設定処理より前に処理されます。そのためモデルのカタログ取得やサーバー起動には進みません（`strata_cli/launch/cmd.py:643-663`）。
- `--preset` がない場合は profile 一覧から ID が `launch-` で始まるものを集めます。指定がある場合は、その名前から作った `launch-<slug>` のみを対象にします（`strata_cli/launch/cmd.py:460-466`）。preset と profile は共有ストアに対応し、launch profile は `launch-<slug>` という名前で作られます（`strata_cli/launch/store.py:1-7`）。
- 各対象の runtime 状態が `ready`、`starting`、`failed`、`stale` の場合、runtime の停止処理を180秒の timeout で呼びます。それ以外の状態ではサーバー停止を呼びません（`strata_cli/launch/cmd.py:467-470`）。runtime は通常、管理ホストへ停止要求を送り、ホストが失われている状態では記録されたプロセスを照合して残存プロセスの終了・状態回復を試みます（`strata_control/runtime.py:614-640,643-667`）。
- 対象ごとに Cloudflare tunnel の停止処理も行います。記録済みプロセスの PID・token・コマンドが Strata が開始したものと一致するときだけ終了を試み、tunnel 状態ファイルを削除します（`strata_cli/launch/cmd.py:460-472`、`strata_cli/launch/access.py:437-449`）。

## 適用条件と副作用

- 対象は `strata launch` の launch profile です。`--stop` は全 profile や任意の推論プロセスを停止する指定ではありません。profile ID の接頭辞による選別は `strata_cli/launch/cmd.py:460-466` にあります。
- 既定（preset 省略）では停止可能状態の全 launch profile を順に処理します。`--preset` 指定時は一つだけです。停止できると、その profile が管理するサーバーと、存在すれば対応する tunnel が終了します。
- runtime 状態が `stopped` など停止対象状態以外でも tunnel の後始末関数は呼ばれます。記録された tunnel 状態ファイルは削除対象です（`strata_cli/launch/cmd.py:467-472`、`strata_cli/launch/access.py:437-449`）。
- `--output json` と併用しても、`--stop` 分岐は `_stop_all()` の通常テキスト表示を使います。JSON 出力の生成処理は `--stop` より後の `--status` 分岐にはありますが、`--stop` 側にはありません（`strata_cli/launch/cmd.py:634-641,661-670`）。

## 出力とエラー

成功した停止は標準出力に `Stopped <name>.`、停止失敗は `Could not stop <name>: <error-or-state>.` と表示します。処理対象がなく停止数も0の場合は `Nothing from \`strata launch\` is running.` を表示します（`strata_cli/launch/cmd.py:469-477`）。

停止結果が失敗でも `_stop_all()` はエラーメッセージを表示した後に続行し、通常は終了コード `0` を返します。runtime の停止処理自体が例外を送出した場合は `run_launch()` 内の `ValueError` 捕捉で `--output` に応じたエラー表示とコード `2` になります（`strata_cli/launch/cmd.py:460-477,832-835`）。

## 根拠

- `strata_cli/launch/cmd.py:141-146` — `--stop` と `--preset` の parser 定義。
- `strata_cli/launch/cmd.py:460-477,643-663` — 対象の選択、状態判定、runtime/tunnel 停止、通常起動に先行する分岐と表示。
- `strata_cli/launch/settings.py:310-315` — preset 名から profile slug への変換。
- `strata_cli/launch/store.py:1-7` — preset/profile の対応関係。
- `strata_cli/launch/access.py:437-449` — tunnel の終了条件と状態ファイル削除。
- `strata_control/runtime.py:444-455,614-667` — runtime 状態と停止・残存プロセス回収の処理。
- `strata_cli/cli.py:2153-2155,2166-2173` — `strata launch` への委譲と共通エラー経路。
