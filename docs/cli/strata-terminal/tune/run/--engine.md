# `strata tune run --engine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--engine` |
| 別名 | なし |
| 値 | 必須のエンジン実行ファイルのパス、または `component:strata-engine` 参照 |

## 役割

チューニング対象のエンジンを指定します。必須指定で、既定値はありません。`strata tune plan --engine` にも同名オプションがありますが、別コマンドのスコープです。この文書は `strata tune run` のものです（`strata_cli/cli.py:414-420`）。

## 使い方

インストール済みコンポーネントから CUDA engine を選ぶ例:

```sh
strata tune run --engine component:strata-engine --backend cuda --model my-model
```

この例は既定の `protocol` モードで実際に測定を開始します。`--engine` は `strata_cli/cli.py:416` で必須引数として登録され、実行時に backend とともに engine 解決へ渡されます（同 `cli.py:1757-1768`）。

## 値と既定値

- 値は argparse の通常の文字列です。選択肢や専用のパス書式 validation は parser にありません。省略すると argparse が必須引数エラーにします（`strata_cli/cli.py:416`）。
- 値が `component:` で始まるときは component 参照として扱います。受理する名前は空文字または `strata-engine` で、`component:other` など未知の名前は engine 解決エラーになります（`strata_control/engine_component.py:950-966`）。
- `component:strata-engine` は `--backend` の値でその PC に適合する component engine を解決します。該当 engine がない場合は自動取得せず、エラーになります。解決時には component の完全性検査が行われ、検査に通らない package は利用可能 engine として選ばれません（`strata_cli/cli.py:1621-1629`、`strata_control/engine_component.py:859-866, 911-936, 957-966`）。
- `component:` で始まらない値はそのまま `Path` に変換されます。実行時に `exists()` が偽なら「no engine binary at …」を返し、終了コード 2 です。存在すること以外の実行可否はこの時点では検証せず、起動・測定時の失敗として扱われます（`strata_cli/cli.py:1621-1629, 1759-1762`）。

## 実行時の動作

`--engine` から得たパスは tuning plan の構築に渡されます。plan はその engine の `--help` 出力から認識フラグを取得し、backend と照合して探索対象の dimension を絞ります。help を起動できない、またはフラグを読み取れない場合、フラグ一覧は `None` となり、静的な dimension 表が使われます（`strata_cli/cli.py:1759-1768`、`strata_control/tuning.py:205-224, 723-768`）。

- 既定の `--mode protocol` では、この engine を各候補の測定プロセスとして起動し、`--serve` と候補フラグを渡します。engine が起動しない、応答しない、または測定値を返さない場合、その候補は失敗として記録されます（`strata_cli/cli.py:1785-1786`、`strata_control/tune_engine.py:388-440, 596-610`）。
- `--mode api` では、`--engine` は plan・flag inventory・engine identity に使われますが、HTTP worker は `--config` を使って起動し、その設定内の engine が実測を行います。したがって `--engine` の指定だけでは API 測定 worker の engine は切り替わりません。API mode は `--config` と `--api-expect` も必須で、候補設定は元 config のコピーに反映されます（`strata_cli/cli.py:1771-1786`、`strata_control/tune_api.py:259-290`）。

engine の通常パス指定ではファイルの存在確認だけを行い、起動可能性は engine の flag inventory 読み取りと実測時に判明します。`.py` を指定した場合は現在の Python interpreter 経由で起動されます（`strata_control/tuning.py:177-186, 205-224`）。

## 適用条件と副作用

- `--engine` は `--backend` と対で使われます。component 参照の場合、backend に適合する installed package の選択に影響します。通常パスの場合、backend は探索可能な tuning dimension の検査に使われます（`strata_cli/cli.py:416-418, 1759-1768`、`strata_control/engine_component.py:859-966`）。
- `protocol` mode は指定 engine を複数候補について繰り返し起動し、CPU/GPU を使う測定を行います。候補ごとに engine を再起動する設計です（`strata_control/tune_engine.py:388-420`）。
- `api` mode では `--config` から一時的な候補 config ファイルを作成し、worker を起動して測定後にその一時ファイルを削除します。元の config は直接書き換えません（`strata_control/tune_api.py:263-290`）。
- sweep の記録は `--state-dir`、環境変数 `STRATA_TUNE_DIR`、または既定の user state 配下に保存されます。`--engine` 自体が有効化する設定変更ではなく、run は active profile を変更しません（`strata_cli/cli.py:1643-1650, 1708-1709, 1845-1846`）。

## 出力とエラー

- component 参照が未知、利用可能な engine がない、または integrity check に失敗した場合、engine 解決のエラーが返ります。参照失敗は `EngineMissing` を `ProfileError` に変換し、`main` の `ValueError` handler が `exit_code`（この失敗では 5）を使って出力します（`strata_cli/cli.py:1621-1629, 2166-2173`、`strata_control/engine_component.py:70-74, 953-966`）。
- 指定 path が存在しない場合は終了コード 2 です。`--output json` では `ok: false` と error object を JSON 出力し、それ以外では `strata: ...` を stderr に出します（`strata_cli/cli.py:527-532, 1759-1762`）。
- 測定中の候補 engine 起動失敗や engine 側エラーは候補の失敗理由として report に記録されます。run 完了時には job ID と recommendation の有無が表示され、`strata tune status <job-id>` で report を確認できます。適用は別の `strata tune apply` 操作です（`strata_control/tune_engine.py:429-440`、`strata_cli/cli.py:1802-1846`）。

## 根拠

- parser と必須指定: `strata_cli/cli.py:395-420`
- engine path / component 参照の変換: `strata_cli/cli.py:1621-1629`; `strata_control/engine_component.py:947-966`
- component 選択・検証・失敗: `strata_control/engine_component.py:859-944`
- engine flag inventory と tuning plan: `strata_control/tuning.py:177-224, 723-768`
- run の引数利用・protocol/API mode 分岐・出力: `strata_cli/cli.py:1742-1847`
- protocol engine 起動: `strata_control/tune_engine.py:388-440, 596-610`
- API mode の候補 config と worker: `strata_control/tune_api.py:259-290`
- エラー出力と終了コード伝播: `strata_cli/cli.py:527-532, 2166-2188`
