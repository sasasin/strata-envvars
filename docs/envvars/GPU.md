# `GPU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`GPU` は Strata Docker イメージの entrypoint が起動時に読む設定で、モデルの初回セットアップに使うカード番号を指定する。entrypoint は選ばれた値を `strata launch --gpu` に渡す。通常の Terminal 起動や engine が直接 `GPU` を読む実装は見つからず、ここで確認できる適用範囲は Docker entrypoint 経由の起動に限られる（`tools/docker/entrypoint.sh:2-6,68-71,226-240`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 無効・特別扱いの値 |
|---|---|---|---|
| Docker entrypoint が通常の起動経路に入る場合 | 空として扱い、`--gpu` を付けない | カード番号のリスト。例 `0`、`0,1`。`GPUS` が未設定または空なら `GPU` が採用される | 空文字は未指定と同じ。`all` と `ALL` は未指定と同じ扱い。`All` など別の大文字小文字は特別扱いされず CLI に渡る（`tools/docker/entrypoint.sh:226-240`） |

entrypoint は `${GPUS:-${GPU:-}}` で選択するため、非空の `GPUS` が `GPU` より優先される。値を小文字化したり、GPU 番号を entrypoint 内で検証したりはしない。`GPU` が採用されると空白を含む元の値を `--gpu` の引数として渡す一方、保存済み設定との比較時だけ空白を除く（`tools/docker/entrypoint.sh:226-239`）。

`strata launch --gpu` 側は空白を除いてカンマで分割し、空要素を除いた各要素を Python の `int` に変換する。したがって `0, 1` や `0,,1` は整数リストに変換され、`-1` も整数としては変換できるが、番号の範囲はこの変換関数では検査しない。`true`、`1x`、`All` など整数に変換できない文字列は `'<値>' is not a list of graphics card numbers. Use 0 or 0,1.` のエラーになる（`terminal/strata_cli/launch/cmd.py:206-213,262-266,1011-1012`）。

## 有効になる条件

- entrypoint が引数なし、`run`、または `serve` で起動されること。`strata ...` など別コマンドを渡す経路は環境設定を組み立てる前に `exec` するため、`GPU` は `--gpu` に転送されない（`tools/docker/entrypoint.sh:68-71`）。
- `GPUS` が非空ならそちらが採用されるため、同時に設定した `GPU` は使われない（`tools/docker/entrypoint.sh:226`）。
- `GPU_ROLES` が非空で、選択されたカード値が空・`all`・`ALL` 以外の場合は両方を指定したエラーで終了する（`tools/docker/entrypoint.sh:241-246`）。エラー文は `Set GPU_ROLES or GPU / GPUS, not both.`、終了コードは `2`。
- 既定 preset がある場合も環境値は `--gpu` 引数として渡される。さらに `/data/install/strata-*.json` の各設定ファイルについて、設定内の `gpu` と空白を除いた要求値が異なると、その設定ファイルを削除して再セットアップを促す。モデルファイルは削除対象ではない（`tools/docker/entrypoint.sh:229-239`）。
- CLI は指定カードを launch 設定の `gpus` に入れ、`gpu_roles` をクリアする。カードの番号や backend で利用可能かは別途 launch の GPU 判定に依存する（`terminal/strata_cli/launch/cmd.py:262-266,446-465`）。

## 実行時の詳細

値はコンテナ entrypoint が起動処理を組み立てる際に評価される。`GPU` を再読み込みする cache やリクエスト単位の読み取りはない。採用値は `strata launch --gpu <値>` のコマンドライン引数として Terminal 子プロセスへ渡り、選択内容はモデルのセットアップ設定に反映される（`tools/docker/entrypoint.sh:226-240,299-310`; `terminal/strata_cli/launch/cmd.py:262-266`）。

空・`all`・`ALL` の場合は `--gpu` を渡さず、launch の既存設定やカード選択規則に任せる。非空の選択値により保存済み `gpu` 設定との不一致が見つかると entrypoint は対応 JSON を削除し、「`The saved run settings use graphics card ...`」を表示して再作成させる。CLI が数値変換に失敗した場合、launch はエラーを返し、entrypoint は `strata launch stopped with code ... (the lines above say why). The container ends.` と出してコンテナを終了する（`tools/docker/entrypoint.sh:231-239,314-316`; `terminal/strata_cli/launch/cmd.py:211-213,1011-1012`）。

## ログと測定値

- 保存済みカード設定との差がある場合、stdout に `The saved run settings use graphics card '${cur:-default}', GPU/GPUS asks for '$want': making them again (model files are kept).` を出す（`tools/docker/entrypoint.sh:234-237`）。
- 無効な整数リストは `strata launch` のエラーとなり、entrypoint が終了コードを含む停止メッセージを stderr に出して終了する（`terminal/strata_cli/launch/cmd.py:211-213,1011-1012`; `tools/docker/entrypoint.sh:314-316`）。
- 対象変数の性能測定値は該当なし。

## 根拠

- `tools/docker/entrypoint.sh:68-71,226-246,299-316` — 適用経路、`GPUS` との優先、値の特別扱い、CLI 引数への転送、保存設定の作り直し、終了時の観測結果。
- `terminal/strata_cli/launch/cmd.py:206-213,262-266,446-465,1011-1012` — `--gpu` の値変換、launch 設定への反映、GPU 条件に関する notice とエラー経路。
