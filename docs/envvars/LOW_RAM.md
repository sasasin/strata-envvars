# `LOW_RAM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

現行 Strata のエンジン設定として `LOW_RAM` を読む箇所は見つかりませんでした。Strata の Docker entrypoint が旧イメージ向けの環境変数として名前を確認し、値があれば無視する旨を警告します。Docker の案内でも、旧イメージ由来の `LOW_RAM` は警告付きで無視されるとされています（`docker/entrypoint.sh:80-82`、`docs/DOCKER.md:265-275`）。

## 値と判定

entrypoint は変数を動的な名前で展開し、値が空でないかだけを検査します。数値や文字列としての内容は解析しません。

| 環境値 | entrypoint の動作 |
|---|---|
| 未設定 | 警告なし |
| 空文字 | 警告なし（未設定と同じ扱い） |
| 空でない値（例: `0`, `1`, `false` など） | 値の内容を問わず警告を stderr に出す。設定は無視される |

判定は entrypoint の起動処理で行われます。実行中の再読み取りや値の cache はありません。Docker entrypoint は起動時に `warn` を stderr に出力し（`docker/entrypoint.sh:37-39,80-83`）、`LOW_RAM` による分岐や `strata launch` 引数への変換を行いません（同 `:169-195`）。

## 有効になる条件

この確認と警告が発生するのは `docker/entrypoint.sh` が実行され、旧変数チェックまで進んだ場合です。現行の Docker image では `LOW_RAM` の値は低 RAM 動作を有効にしません。Docker 文書は `STRATA_SET` をエンジン設定に、`strata launch --help` をその他の設定に案内しています（`docs/DOCKER.md:270-275`）。

`setup.py` にある低 RAM 機能は環境変数 `LOW_RAM` ではなく `--low-ram` CLI 引数です。引数は `auto`, `on`, `off`, `resident`, `mmap` を受け付け、既定値は `auto` です（`setup.py:9678-9682`）。これは `LOW_RAM` の環境値の変換や優先順位を示すものではありません。

## 実行時の詳細

entrypoint は `HOST`, `LOW_RAM` などの旧イメージ用名を順に調べ、各値が空でない場合に `[!] <名前> is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` を stderr に出します（`docker/entrypoint.sh:80-82,37-39`）。空でなければどの値でも同じ警告です。警告による終了や拒否はなく、コメントもこの節を “plain warnings (never refusals)” としています（同 `:67-68`）。

その後の起動引数の組み立てでは `MODEL`, `FAMILY`, `MODEL_PATH`, `CONTEXT`, `PARALLEL`, `KV` などを個別に flags に追加しますが、`LOW_RAM` は追加されません（`docker/entrypoint.sh:169-195`）。そのためこの環境変数は entrypoint 経由の低 RAM 動作を選択しません。コアコード・他の実行経路で `LOW_RAM` を環境から読む箇所は、対象 commit の `LOW_RAM` 全参照検索では確認できませんでした。

## 根拠

- `docker/entrypoint.sh:37-39,67-83` — 警告出力先、旧変数名の動的な参照、空でない値に対する警告。
- `docker/entrypoint.sh:169-195,280-283` — `strata launch` 引数の構成と起動。`LOW_RAM` は引数へ追加されない。
- `docs/DOCKER.md:265-275` — 旧イメージから移行する際の `LOW_RAM` の扱い。
- `setup.py:9678-9682` — 別機能である `--low-ram` CLI 引数とその選択肢・既定値。
