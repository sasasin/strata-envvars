# `ZES_ENABLE_SYSMAN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、変更表示はありませんでした。

## 役割

Strata の engine 本体がこの名前を読んで分岐するコードは見つかりませんでした。Strata が行うこととして確認できたのは、SYCL 用 Docker 起動スクリプトから `ZES_*` 名の変数をコンテナへ渡すこと、Arc 用ベンチマークスクリプトでこの値を `1` に設定して engine 子プロセスを起動すること、そして汎用の起動設定から任意の環境変数として engine へ渡せることです。名前の受け手である外部 runtime / driver が値をどう解釈するかは、この調査の対象外です。

## 値と判定

engine 本体に `ZES_ENABLE_SYSMAN` 専用の値判定はありません。値を扱う Strata 側の経路ごとの規則は次のとおりです。

| 経路 | 設定値の扱い |
|---|---|
| `tools/arc/b.py` | 子プロセス用環境に既定値 `1` を設定する。`--env KEY=VALUE` で同じキーを指定すると後から上書きできる。`--env ZES_ENABLE_SYSMAN` のように `=` がない指定は空文字で上書きされる。|
| `sycl/serve/strata-sycl.sh` | スクリプト起動時の環境から `ZES_*` を収集する。値が文字列 `0` または空文字なら Docker の `-e` 引数に含めず、それ以外の値はそのまま渡す。数値化や大文字小文字変換はしない。|
| `strata launch --set ZES_ENABLE_SYSMAN=VALUE` | 汎用環境設定として値を保存し、engine 用環境に設定する。値 `off`、`unset`、`none`（大文字小文字を区別しない）は環境設定から削除する指示になる。その他の値は文字列のまま渡す。|

SYCL ラッパーの `0` / 空文字の除外は「変数をコンテナへ渡さない」という処理です。コンテナイメージには Dockerfile の `ENV ... ZES_ENABLE_SYSMAN=1` があります。そのため、このラッパー経由では `0` / 空文字がイメージ既定値を上書きしません。これはコンテナ環境の構成についての記述であり、engine や driver がその値をどう使うかを示すものではありません。

## 有効になる条件

- `sycl/serve/strata-sycl.sh` が engine の実行ファイルとして使われると、ホスト側サーバー環境にある `ZES_*` がラッパーの収集対象になります。サーバーの `cfg["env"]` 設定は `child_env()` で継承環境に上書きされて engine 用環境へ渡されます。
- ラッパーは `ZES_*` を含む変数名の集合を対象とするため、`ZES_ENABLE_SYSMAN` は対象です。`0` と空文字は転送されず、それ以外は値を保持して Docker に渡されます。
- `tools/arc/b.py` はバックエンドや値を判定せず、engine 子プロセスの環境に `ZES_ENABLE_SYSMAN=1` を追加します。任意の `--env` 指定はその後に適用されます。
- `strata launch --set` の設定は、任意の大文字を含む環境変数名として受理され、起動時の config `env` に反映されます。`child_env()` は親プロセスの環境を先にコピーし、その後 config の各項目で上書きします。config からこのキーを除いた場合は、親環境に同名変数があれば継承値が残ります。

## 実行時の詳細

SYCL server は `child_env()` の結果を engine プロセスの環境として `StrataEngine` に渡します。`strata-sycl.sh` はその環境から `ZES_*` を含む変数を集め、値が `0` / 空文字でない場合に Docker の `-e KEY=VALUE` としてコンテナへ渡します。Dockerfile 側にはイメージ既定値 `ZES_ENABLE_SYSMAN=1` が記載されています。

汎用 launcher では、`--set` の環境設定は `cfg["env"]` に入り、server 起動時の `child_env()` がその値を子 engine の環境へ反映します。これらの箇所に `ZES_ENABLE_SYSMAN` 固有の警告、ログ、終了条件はありません。engine/driver 内部での読み取り後の挙動や観測結果は Strata 所有コードからは確認できません。

## 根拠

- 候補名の参照箇所: `docs/INTEL_ARC.md:143`（使用例）、`sycl/tools/Dockerfile:8`（イメージ環境の既定値）、`tools/arc/b.py:32-39`（既定値と `--env` 上書き）、`strata_cli/launch/settings.py:253-269`（任意環境変数名としての認識）。
- CLI 設定値の変換: `strata_cli/launch/cmd.py:120-121,284-285`、`strata_cli/launch/settings.py:257-277,286-310`。環境設定の削除・文字列設定: `strata_control/tune_knobs.py:519-525`。
- config 環境の engine への反映: `strata_cli/launch/runner.py:557-562`、`serve/server.py:3747-3760,8704-8710`。
- SYCL ラッパーでの収集・フィルター・コンテナ転送: `sycl/serve/strata-sycl.sh:13-16,28-38,42-47`。

## 候補一覧との照合

`docs/envvars/000_envvers.md` には候補として掲載されています。Strata engine 自身による読み取りは確認できませんが、上記の Strata 所有コードによる設定と転送は確認できたため、この文書ではその範囲のみを説明しました。driver/runtime 側の意味や機能は記載していません。
