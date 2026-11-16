# `strata components rollback --backend`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | エンジン backend 名を表す文字列。parser は選択肢を制限しない |

## 役割

ロールバック時に対象とする GPU/backend を指定する。ロールバック先のバージョン自体は components store の状態に記録された `previous` から取得されるため、このオプションはロールバック先を名前で選ぶものではない。指定 backend に対して、現在使用中のエンジンを判定し、保存済みの前バージョンがこの PC で起動可能かを検査する。

## 使い方

```sh
# AMD backend として記録された前バージョンへ戻す
strata components rollback --backend amd
```

実行には rollback 対象の前バージョンが components store に保存されている必要がある。標準では backend を自動検出する。

## 値と既定値

- `--backend` は値を1つ取る。parser は `default=None` で、`choices` や独自の型変換を指定していない（`strata_cli/update_cmd.py:47-56,80-81`）。値を省略すると argparse が使用法エラーにする。
- 明示値は前後の空白を除去して小文字化される。`nvidia` は `cuda`、`amd` は `hip`、`intel` と `arc` は `sycl` に対応する。`hip-<variant>` は backend `hip` と variant に分けられる（`strata_control/engine_component.py:476-488`）。
- 空文字列を明示した場合は `a.backend` が偽として扱われ、未指定と同じ自動検出経路に入る（`strata_cli/update_cmd.py:310-315`）。
- parser は任意の文字列を受け付けるため、未知名は parser 段階では拒否されない。後続の engine 解決時に適合する engine が見つからなければ失敗する（`strata_cli/update_cmd.py:279-296`、`strata_control/engine_component.py:1081-1114`）。
- 未指定時は `updater.detect_hardware()` を使い、通常の backend 検出に加えて `STRATA_ENGINE_BACKEND` の指定も反映する。`--backend` を指定した場合はその値から hardware 情報を作る（`strata_cli/update_cmd.py:279-296,310-315`、`strata_control/updater.py:316-336`）。

## 実行時の動作

`--backend` が指定されると、`requested_hardware()` が値を backend と variant に分け、認識済み backend family ならその family を `STRATA_ENGINE_BACKEND` として hardware 検出に渡す。未知 family は検出した hardware 情報の backend 欄をその値に置き換える（`strata_cli/update_cmd.py:279-296`）。

rollback 処理は state の `engine.previous` を対象フォルダーとして読み込み、稼働中の server/engine がないか確認してから、manifest と全ファイルを検証する。その後、指定 backend の hardware 情報で「現在の engine」を解決し、rollback 先へ切り替える。切り替えは engine をダウンロード・削除せず、次回起動でその engine が選ばれるよう pin と active/previous の状態を更新する（`strata_control/updater.py:1450-1472,1398-1447`）。

`hip-<variant>` の variant は hardware 情報に保持されるが、rollback の対象 folder は state の `previous` で決まり、rollback 処理は feed package 選択を行わない（`strata_cli/update_cmd.py:287-296,318-322`、`strata_control/updater.py:1450-1472`）。

## 適用条件と副作用

- rollback は components folder の update lock を取得して実行する。同じ folder に対する別の update 操作が lock を保持中なら busy エラーになる（`strata_control/updater.py:195-215,1453-1455`）。
- `--wait` を指定した場合、稼働中の engine が停止するまでその秒数の範囲で待つ。未指定または `0` の場合、対話端末では待つか確認し、非対話または machine output では待たずに busy として扱う（`strata_cli/update_cmd.py:473-488`）。rollback の実処理でも `wait_until_idle()` が稼働状態を再確認する（`strata_control/updater.py:366-378,1459-1461`）。
- 成功時は `<components-dir>/.updates/state.json` を更新し、前後の engine、pin、rollback 履歴を記録する。engine が変わった場合、保存済み tuning preset は削除せず短い再確認の対象として印を付ける（`strata_control/updater.py:227-233,1398-1447`、出力は `strata_cli/update_cmd.py:325-331`）。
- `--components-dir` を省略した場合は既定の components folder を使う。backend はその folder 内の engine 解決に適用される（`strata_cli/update_cmd.py:261-277,310-315`）。

## 出力とエラー

- 成功時は human 出力で変更前後の version と preset の扱いを表示する。`--output json` または `--json` では JSON を stdout に出す（`strata_cli/update_cmd.py:318-331`、`strata_cli/cli.py:2266-2269`）。
- 前バージョンが記録されていない場合、すでにその前バージョンが使用中の場合は終了コード `2`。前バージョンの manifest / 完全性検証に失敗した場合、または rollback 先が現在の PC で起動可能な engine として解決できない場合は終了コード `5`（`strata_control/updater.py:1456-1471,1422-1431`）。
- 稼働中の engine が待機時間内に停止しない場合や同じ components folder がロック中の場合は busy エラー（終了コード `7`）（`strata_control/updater.py:366-378,195-215`）。
- 捕捉された `UpdateError` は human 出力では stderr、JSON 出力では `error.code` と `error.message` を含む JSON として出され、同じ終了コードで終了する（`strata_cli/update_cmd.py:303-308,368-372`）。

## 根拠

- `strata_cli/update_cmd.py:47-56,80-81` — 共通 parser の `--backend` 宣言と rollback parser への登録。
- `strata_cli/update_cmd.py:279-296,310-322` — 値の変換、hardware 検出への反映、rollback 分岐。
- `strata_control/engine_component.py:476-488` — backend alias と `hip-<variant>` の変換規則。
- `strata_control/updater.py:316-336,594-599,1081-1114` — backend を使った hardware 情報生成と installed engine 解決。
- `strata_control/updater.py:1398-1472` — engine の pin・状態更新、前バージョンの検証と rollback。
- `strata_cli/update_cmd.py:303-308,318-331,368-372,473-488`、`strata_control/updater.py:195-215,366-378` — 出力、失敗コード、稼働中 engine の待機。
