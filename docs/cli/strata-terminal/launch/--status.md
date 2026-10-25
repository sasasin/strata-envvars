# `--status`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--status` |
| 別名 | なし |
| 値 | 取らない。`argparse` の `store_true` フラグ |

## 役割

`strata launch` が管理する稼働中の server 状態を照会し、名前・状態・接続 URL を表示します。`launch-` で始まる profile だけを調べ、状態が `ready` または `starting` のものを結果に含めます。preset の一覧・server 停止とは別の管理操作です。

## 使い方

```sh
strata launch --status
```

JSON で結果を受け取る場合:

```sh
strata launch --status --output json
```

## 値と既定値

`--status` 自体は値を取りません。省略時は `False` で、通常の起動経路に進みます。複数回指定しても真偽フラグのままです。表示形式は別 option `--output` が決め、`human` が既定、受理値は `human` と `json` です（`strata_cli/launch/cmd.py:140-145`）。

## 実行時の動作

`run_launch` は preset 操作・停止処理の後、起動や設定構築より前に status 分岐へ入ります。そのため、通常の status 照会ではモデル選択・起動・preset 保存には進みません。`running_launches()` は profile 一覧から `launch-` prefix の ID を選び、`strata_control.runtime.status()` を呼びます。状態が `ready` / `starting` であれば、profile の `overrides.port`（なければ既定 port）を使って `http://127.0.0.1:<port>` を表示用 URL として組み立てます（`strata_cli/launch/cmd.py:567-592,661-671`）。

人間向け出力では稼働中の各項目を `<名前>: <状態> at <URL>` と表示します。該当項目がない場合は `Nothing from \`strata launch\` is running.` と表示します。`--output json` の場合は `{"schema_version":1,"ok":true,"running":[...]}` 形式を stdout に出します。通常の完了コードは `0` です（`strata_cli/launch/cmd.py:663-671`）。

## 適用条件と副作用

照会対象は Strata の profile のうち ID が `launch-` で始まるものに限られます。runtime の状態が `stopped`、`stale`、または `ready` / `starting` 以外の場合は一覧から除外します。`runtime.status()` は state と host lease を読み、lease が有効なら runtime の status RPC を呼びます。profile 一覧が存在しない場合、照会結果は空になります（`strata_control/runtime.py:444-455`、`strata_control/profiles.py:169-182`）。

この経路に起動・停止・設定保存の呼び出しはありません。ソース上で確認できる副作用は状態照会と標準出力への表示です。`--preset` を同時指定しても status の検索対象はその preset に限定されません。なお、同時に `--stop` を指定すると、parser 後の分岐順で `--stop` が先に処理され、status 表示には進みません（`strata_cli/launch/cmd.py:661-671`）。

## 出力とエラー

- 人間向け出力は stdout、未知の引数に対するエラーは parser の後処理から stderr に出て終了コード `2` になります（`strata_cli/cli.py:2223-2231`）。
- profile 一覧取得時の例外は `running_launches()` 内で空の一覧として扱われ、status コマンド自体は「稼働なし」として `0` を返します。個別の `runtime.status()` の例外もその profile を飛ばして続行します（`strata_cli/launch/cmd.py:571-584,663-671`）。
- runtime の `stale` 状態は失敗として表示せず、稼働一覧から除外します（`strata_control/runtime.py:448-455`、`strata_cli/launch/cmd.py:578-584`）。
- profile 読み込みで例外が起きた場合、`running_launches()` は `ov` を空にしますが、その後 `prof.get("source_config")` も参照します。該当 profile の runtime が `ready` / `starting` を返す条件で `prof` が未定義なら例外になり得ます。この異常経路の表示形式・終了コードは、当該ソースでは個別に処理されていません（`strata_cli/launch/cmd.py:582-592`）。

## 根拠

- `strata_cli/launch/cmd.py:140-145` — `--output` と管理 option の parser 定義。`--status` は値なしの `store_true`。
- `strata_cli/launch/cmd.py:567-592` — launch profile の絞り込み、runtime 状態照会、表示用 URL の組み立て。
- `strata_cli/launch/cmd.py:630-641,661-671` — status 分岐、human / JSON 出力、完了コード。
- `strata_control/runtime.py:444-455` — runtime の state / lease 確認と status RPC。
- `strata_control/profiles.py:169-182` — profile 一覧の読み込みと不正 profile の扱い。
- `strata_cli/cli.py:2223-2231` — 未知引数を stderr に出して `2` を返す処理。
