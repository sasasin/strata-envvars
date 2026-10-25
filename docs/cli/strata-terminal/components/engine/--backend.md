# `strata components engine --backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend family 名を受け取る文字列。ソースで定義された値は `cuda`、`hip`、`sycl`、`metal`、`cpu` |

## 役割

ローカルの engine component から、この PC で使う backend family を指定して候補を調べます。コマンドは engine を起動せず、ダウンロードもしません。主な用途は自動検出と異なる family の候補を確認することです。

## 使い方

```sh
strata components engine --backend cuda
```

この例は `cuda` backend の engine をローカル component フォルダーから探します。コマンド名と `--backend` の parser 定義は `strata_cli/cli.py:132-138` にあります。

## 値と既定値

- 引数は `default=None` の文字列で、parser に `choices` や CLI 側の型変換はありません（`strata_cli/cli.py:134`）。実装上の backend family は `cuda`、`hip`、`sycl`、`metal`、`cpu` です。OS ごとの対応は `strata_control/targets.py:23-29` に定義されています。
- 省略時は resolver が `detect_backend()` を呼びます。`STRATA_ENGINE_BACKEND` が設定されていれば小文字化した値が優先され、有効値以外は `ComponentProblem` になります。未設定なら macOS は `metal`、それ以外は OS/adapter 情報や既設 GPU 検出ツール等を使って判定し、backend を検出できなければ `cpu` を選びます（`strata_control/engine_component.py:439-482, 868-874`）。
- CLI の明示値自体は argparse で検証されません。未知値やその OS で利用できない値は resolver に渡され、対応する installed package がなければ usable engine がない結果になります。OS と family のサポート表は `strata_control/targets.py:23-29, 42-51` にあります。
- 重複指定時の専用処理はありません。argparse の通常の単一値引数として最後に解析された値が使われます。空文字列を明示すると `None` ではない値として resolver に渡されるため、自動検出の代わりにはなりません。

## 実行時の動作

CLI は `a.backend` を `engine_component.status(..., backend=a.backend, full=a.full)` に渡します（`strata_cli/cli.py:2017-2020`）。status は component folder を走査し、明示 backend がある場合はそれを resolver に渡して package backend と照合します。候補が複数ある場合は usable なもののうち pin が有効なら pin を優先し、そうでなければ version 等で選びます（`strata_control/engine_component.py:969-988, 881-894, 937-944`）。このオプションは候補選択の指定であり、別 backend 用の package を実行可能にするものではありません。

未指定時の `STRATA_ENGINE_BACKEND` は検出値の override になります。一方、CLI に backend を明示した場合はその値が resolver に渡るため、検出値より CLI 指定が選択に使われます（`strata_control/engine_component.py:439-447, 868-874, 983`）。status は表示用 backend 情報を作る過程で検出も呼びますが、CLI 値がある場合は報告上の backend をその値にします（同 `engine_component.py:972-984`）。

通常の status 検証は entrypoint の hash を確認し、`strata components engine --full` を併用した場合に全ファイルを hash します。検証モードの選択は `--full` 側の指定です（`strata_cli/cli.py:137, 2020`; `strata_control/engine_component.py:859-862, 911-918`）。

## 適用条件と副作用

`--backend` は local component の照合条件として使われます。`STRATA_COMPONENTS_DIR` があればそこを使い、なければユーザー領域の既定 component folder を使います（`strata_cli/cli.py:135-136`; `strata_control/engine_component.py:176-190`）。コマンドは読み取り専用で、engine を起動せず、download やファイル変更を行いません。GPU 検出経路では既設の検出ツールを最大8秒で読み取り専用実行する場合があります（`strata_control/engine_component.py:439-482, 861-867`）。

## 出力とエラー

- 成功時は終了コード `0`。human 出力では component folder、PC/backend、installed package、選択された engine を表示します。JSON 出力は `--output json` で、`schema_version`、`ok`、status report を出します（`strata_cli/cli.py:2023-2040`）。
- 指定値に合う usable engine がない場合、終了コード `5` です。human 出力では notice を stderr に出し、JSON では `ok: false` を含む report を stdout に出します。どちらも download は行いません（`strata_cli/cli.py:2023-2040`; `strata_control/engine_component.py:919-936, 969-988`）。
- 自動検出で `STRATA_ENGINE_BACKEND` が不正な場合など、`ComponentProblem` は終了コード `2` として出力されます。human では `strata: ...` を stderr、JSON mode では error object を stdout に出します（`strata_cli/cli.py:2019-2022, 527-532`; `strata_control/engine_component.py:439-447`）。未知の CLI backend 文字列は parser validation error にはなりません。

## 根拠

- parser と option scope: `strata_cli/cli.py:132-138`
- command dispatch、exit code、表示: `strata_cli/cli.py:2014-2041`
- backend 環境変数と GPU 検出: `strata_control/engine_component.py:439-482`
- resolver による値の適用、照合と失敗: `strata_control/engine_component.py:859-936`
- status の report と missing engine 処理: `strata_control/engine_component.py:969-988`
- component directory の既定値: `strata_control/engine_component.py:176-190`
- 対応 backend と OS: `strata_control/targets.py:20-51`

