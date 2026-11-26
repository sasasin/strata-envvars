# `strata launch --stop`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--stop` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

`strata launch` が管理する実行中・起動中のサーバーを停止します。`--preset NAME` を併記すると、その名前から作られる profile だけを対象にし、省略すると保存済みの `launch-` profile 全体を走査します。Cloudflare tunnel を使った launch については、対応する記録済み tunnel の停止も試みます。

## 使い方

```sh
# すべての strata launch 管理サーバーを停止
strata launch --stop

# Office preset に対応するサーバーだけを停止
strata launch --stop --preset Office
```

## 値と既定値

`--stop` は引数を取りません。指定しない場合は停止モードになりません。`--preset` は任意で、指定値を `S.slug()` で profile ID 用の文字列に変換してから `launch-` を付けます。slug 化では小文字化し、英小文字・数字・`-`・`_` 以外をハイフンに置換し、連続ハイフンをまとめ、先頭が英字でなければ `l` を付けます（最大 48 文字）。

## 実行時の動作

parser は `--stop` を boolean として受理します。`run_launch()` は preset 一覧・削除処理の後、状態表示や通常の起動処理より先に `--stop` 分岐へ進みます。この分岐では他の起動用オプションは処理されず、`--output json` を併記しても停止処理の表示は JSON 化されません。

停止対象は次の通りです。

- `--preset` なし: `profiles.list_profiles()` の結果から ID が `launch-` で始まるものを集めます。
- `--preset NAME` あり: `launch-` + slug 化した名前の profile だけを対象にします。

各対象について runtime の状態を読み、`ready`、`starting`、`failed`、`stale` の場合に `runtime.stop(profile, timeout=180)` を呼びます。それ以外の状態では runtime stop を呼びません。stop の結果が成功なら `Stopped NAME.`、失敗なら `Could not stop NAME: ERROR.` を出します。どちらの場合も対象 profile に紐づく tunnel の停止処理を試みます。runtime stop の詳細なプロセス制御は `strata_control.runtime.stop()` に委譲され、管理 host が失われた場合の残存プロセス回収も同関数内で扱われます。

## 適用条件と副作用

既定では全 `launch-` profile を対象にするため、複数 preset のサーバーが動作中ならそれぞれ停止を試みます。`--preset` 指定時の名前は保存済み preset の存在確認には使われず、slug 化した profile ID を直接指定します。

runtime stop が成功すれば Strata が管理するサーバーを停止します。runtime が停止対象を完了できなかった場合は失敗として数えます。tunnel cleanup は、Strata がその launch 用に記録したプロセスが今も同一プロセスと確認できる場合にのみ終了を試み、tunnel 状態ファイルの削除も試みます。tunnel cleanup の戻り値は CLI の成功・失敗カウントには反映されません。

## 出力とエラー

停止対象がなく、または各対象が停止対象状態でなかった場合は `Nothing from \`strata launch\` is running.` を stdout に出し、終了コード 0 です。停止に成功した対象ごとに `Stopped NAME.` を stdout に出します。失敗した対象ごとに `Could not stop NAME: ERROR.` を出し、1 件でも失敗があれば、他の対象が成功していても終了コード 1 になります。失敗があった場合は「何も実行中でない」という表示は追加しません。

## 根拠

- `terminal/strata_cli/launch/cmd.py:155-160` — `strata launch` の管理オプショングループと `--stop` parser 定義（値なし boolean、`--preset` との関係）。
- `terminal/strata_cli/launch/cmd.py:753-763, 783-788` — 管理分岐の優先順、stop 分岐で `_stop_all()` を呼ぶこと。失敗時の一般処理が human mode では stderr に出す仕様に対し、stop helper は独自に stdout 表示する。
- `terminal/strata_cli/launch/cmd.py:540-556` — 対象 profile の選択、対象状態、180 秒 timeout、メッセージ、トンネル cleanup、終了コード。
- `terminal/strata_cli/launch/settings.py:462-468` — preset 名の slug 化。
- `terminal/strata_control/profiles.py:187-200` — profile 一覧の取得と profile ID の扱い。
- `terminal/strata_control/runtime.py:801-827, 830-854` — runtime stop の timeout validation、stop RPC と owner 終了待ち、owner がない場合の残存プロセス回収。
- `terminal/strata_cli/launch/access.py:499-511` — 記録された同一 tunnel process の終了確認と状態ファイル cleanup。
- `terminal/strata_cli/launch/cmd.py:495-498` — `_say()` が stdout に行を出力すること。
