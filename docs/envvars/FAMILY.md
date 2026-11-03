# `FAMILY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Docker image の通常起動で、同じ model size が複数の model family にある場合に、起動する family を選びます。Strata の C++ engine や Terminal は `FAMILY` 環境変数を直接読みません。Docker entrypoint が空でない `FAMILY` を `strata launch --family VALUE` に変換し、Terminal がその CLI 引数を model catalog と照合します。

## 値と判定

| Docker entrypoint の値 | entrypoint の処理 |
|---|---|
| 未設定 | `--family` を追加しない。既存 preset の model 選択、または model 未指定時の通常の推奨処理に進む |
| 空文字 | `${FAMILY:-}` が空になり、`--family` を追加しない |
| 空でない文字列 | 値を変換せず `--family` の引数として渡す |

entrypoint は空かどうかだけを検査し、大小文字変換・前後空白の除去・値域検査をしません。`--model` も与えられると、Terminal は model 名を大小文字を無視して検索し、family は catalog の family ID と完全一致で検査します。指定 family が存在しない場合、またはその family が指定 model size を提供しない場合はエラーです。family を省略した場合、複数 family が同じ size を提供すると `qwen` を優先し、それ以外は catalog 上の最初の候補を選びます。`strata_cli/launch/catalog.py:397-428`。

## 有効になる条件

- Docker entrypoint の通常サーバー起動経路で使われます。`docker run IMAGE strata ...` のように任意の Strata コマンドを指定した場合は、entrypoint が設定引数を組み立てる前にコマンドを `exec` するため、`FAMILY` はこの仕組みでは渡されません（`docker/entrypoint.sh:53-56`）。
- 空でない `FAMILY` は `--family` に渡されますが、選択には対応する model が必要です。`MODEL` も指定したときはその組み合わせを catalog が検証します（`docker/entrypoint.sh:190-192`, `strata_cli/launch/cmd.py:225-230`）。
- 保存済み preset に model があり、`MODEL` を省略して `FAMILY` だけを指定すると、Terminal は preset を読み込んだ後で family をその値に置き換えます（`strata_cli/launch/cmd.py:212-218,231-232`）。この分岐では `catalog.resolve()` による family の検証は行われず、後続処理での扱いは preset の model と指定 family に依存します。
- preset に model がなく `FAMILY` だけを指定した場合、Terminal は model を選択せず、family も設定に適用しません。推奨 model が選ばれる通常経路では推奨 family/model が設定されます（`strata_cli/launch/cmd.py:231-232,372-384`）。Docker entrypoint はこの値が非空なら `have=1` としますが、`strata launch` の `have_choices` 判定に `--family` 単独は含まれません。そのため `--no-tui` で model/preset なしに family だけを渡す場合、選択がないとして失敗します（`docker/entrypoint.sh:190-192,243-251`; `strata_cli/launch/cmd.py:879-890`）。

## 実行時の詳細

entrypoint は通常起動の引数列を作るときに `${FAMILY:-}` を評価し、非空なら `--family` と値を追加します。読み取りはこの shell 起動時の一度だけで、継続中の server request ごとに環境を再評価する処理はありません。family 値は Docker entrypoint から CLI 引数として引き渡され、CLI は model が指定されていれば preset の family/model よりもその model と family の組み合わせを採用します。model がない場合は、preset に model があると family だけを上書きします（`docker/entrypoint.sh:169-192`; `strata_cli/launch/cmd.py:212-232`）。

`--model` と組み合わせた family が catalog にない場合は `There is no model family called ...`、その family に size がない場合は `... has no size ...` の `ValueError` になります。launch command はこれを stderr の `strata: ...` と終了コード 2 にします（`strata_cli/launch/catalog.py:412-424`; `strata_cli/launch/cmd.py:1048-1051`）。Docker entrypoint は launch の非 0 終了を `[X] strata launch stopped with code ...` として出し、その終了コードでコンテナを終了します（`docker/entrypoint.sh:289-292`）。

## 根拠

- 候補一覧には `FAMILY` が掲載されています（調査対象 strata-envvars の `docs/envvars/000_envvers.md:515`）が、実際の環境読み取り箇所は Strata の Docker entrypoint です。
- Docker entrypoint の説明と値転送: `docker/entrypoint.sh:9-12,169-192`。
- CLI の `--family` 定義: `strata_cli/launch/cmd.py:83-90`。
- preset/引数からの設定優先順位: `strata_cli/launch/cmd.py:212-232`。
- model-family 対応検証と省略時の選択: `strata_cli/launch/catalog.py:397-428`。
- Docker 利用例と family の役割: `docs/DOCKER.md:39-44,48-71,114-117`。
