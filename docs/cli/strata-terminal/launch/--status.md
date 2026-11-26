# `strata launch --status`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--status` |
| 別名 | なし |
| 値 | 取らない。`store_true` のフラグ |

## 役割

`strata launch` が起動したサーバーのうち、現在 `ready` または `starting` 状態のものを列挙します。preset の保存内容やモデル一覧を調べるものではなく、launch 用 runtime の状態を読み取ります。

## 使い方

```sh
strata launch --status
strata launch --status --output json
```

## 値と既定値

値や引数は不要です。省略時は `False` で、通常の `strata launch` の起動経路へ進みます。`--status` に値を付ける構文はありません。`--preset` を併記しても、status 分岐ではその preset 名は参照されず、全 launch を調べます（parser は `--preset` を別に定義し、status 分岐は `a.preset` を使わず `running_launches()` を呼びます）。

## 実行時の動作

`running_launches()` は保存済み profile を列挙し、ID が `launch-` で始まるものに対して `runtime.status()` を呼びます。応答状態が `ready` または `starting` の profile について、profile の上書き設定から port と host を読み、表示用 URL を組み立てます。破損した profile を読めない場合は空の設定として既定 port と loopback host を使います。profile 一覧の取得や個別の runtime 状態確認で例外が起きた場合、その一覧・profile は結果から除外されます（`terminal/strata_cli/launch/cmd.py:663-690`）。

`runtime.status()` は runtime state を読み、state がなければ `stopped`、host lease が見つからなければ `stopped`、lease が有効でなければ `stale` を返し、それ以外は owner に status RPC を問い合わせます。`running_launches()` は `stale` を表示対象に含めません（`terminal/strata_control/runtime.py:490-501`、`terminal/strata_cli/launch/cmd.py:676-680`）。

`--output json` を指定すると `schema_version: 1`、`ok: true`、`running` 配列を含む JSON を出力します。preset 管理や停止と同時に指定した場合は、処理順で先に判定される `--list-presets`、`--delete-preset`、`--stop` が status より優先されます（`terminal/strata_cli/launch/cmd.py:753-797`）。

## 適用条件と副作用

このオプションは status 読み取り経路に入り、モデル起動・停止や preset 更新は行いません。runtime 状態の読み取りと、応答可能な owner への status RPC は行われます（`terminal/strata_cli/launch/cmd.py:789-797`、`terminal/strata_control/runtime.py:490-501`）。

## 出力とエラー

人間向け出力では、該当する launch ごとに `<名前>: <状態> at <URL>` を表示します。対象がなければ「Nothing from `strata launch` is running.」を表示します。status 分岐の終了値は対象の有無にかかわらず `0` です（`terminal/strata_cli/launch/cmd.py:789-797`）。

JSON モードでは JSON オブジェクトに加え、対象が1件以上あると同じ launch の人間向け行も続けて stdout に書かれます。これは JSON Lines ではなく、標準出力全体を単一 JSON として読む利用側では解析を妨げる形式です（`terminal/strata_cli/launch/cmd.py:790-797`）。一覧取得・runtime 確認の例外は `running_launches()` 内で握りつぶされるため、status の出力だけから個々の失敗を識別できない場合があります（`terminal/strata_cli/launch/cmd.py:668-680`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:155-160` — `--status` は値を取らない `store_true` として `strata launch` の manage 引数群に登録。
- `terminal/strata_cli/launch/cmd.py:663-690` — launch profile の抽出、状態フィルター、URL 構築、profile/runtime 読み取り失敗の扱い。
- `terminal/strata_cli/launch/cmd.py:753-797` — status 分岐の優先順、human/JSON 出力と終了値。
- `terminal/strata_control/runtime.py:490-501` — runtime status の state・lease 判定と owner RPC。
- `terminal/strata_cli/cli.py:516-517, 2235-2237` — `launch` parser の登録と `run_launch()` へのディスパッチ。
