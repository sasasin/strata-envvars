# `ZES_ENABLE_SYSMAN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata のエンジンコードに、この名前を直接読んで値を判定する箇所は確認できない。Strata が行うのは、サーバー設定またはプロセス環境から子プロセスへ値を渡す処理である。特に Intel SYCL 用ランチャー `sycl/serve/strata-sycl.sh` はホスト環境の `ZES_*` 変数を Docker コンテナへ転送する。したがって、この変数による下流の機能や GPU driver の挙動は Strata のソースだけからは説明しない。`serve/server.py` は設定 `env` を子エンジン環境に反映し、SYCL ランチャーは `ZES_*` を転送対象に含める（`serve/server.py:4428-4441`、`sycl/serve/strata-sycl.sh:33-42`）。

## 値と判定

Strata エンジンは値を parse しない。通常のサーバー経路では設定 `env` の値を文字列化して子環境に設定する。Intel の Docker ランチャーではホスト環境の値を読み、空文字列と文字列 `0` を Docker に渡さず、それ以外をそのまま渡す。数値・真偽値としての検証、大文字小文字変換、空白除去はない（`serve/server.py:4440-4441`、`sycl/serve/strata-sycl.sh:33-42`）。

| 条件 | unset | 転送される値 | 転送されない値 |
|---|---|---|---|
| サーバーの一般的な子プロセス環境 | 親環境にも設定 `env` にもなければ未設定 | 設定 `env` の値は文字列化して反映。値の内容は判定しない | 特別な無効値判定なし。`strata launch --set` で `off`、`unset`、`none` を指定すると設定キーを削除し、親環境からの継承に戻る |
| Intel SYCL の `strata-sycl.sh` 経由 | ホストで未設定ならランチャーから Docker に渡さない。標準の SYCL 開発イメージでは Dockerfile の `ENV` によりコンテナ内の既定値 `1` が設定される | 空でも `0` でもない値。例: `1`、`true`、`false`、`0anything` は値を変えず渡す | 空文字列と厳密に `0` のみ。比較は shell case pattern であり、空白や大文字小文字の正規化はしない |

SYCL 開発イメージのコンテナ既定値 `1` は `sycl/tools/Dockerfile:8` に記述されている。ランチャーでホスト値 `0` または空文字列を除外しても、標準イメージの場合はそのイメージ既定値が残る。これは Strata の値変換ではなく、ランチャーの転送条件と Docker イメージ設定の組み合わせである（`sycl/serve/strata-sycl.sh:40-42`、`sycl/tools/Dockerfile:8`）。

## 有効になる条件

- 一般のサーバー経路では、設定ファイルの `env` にこの名前が指定されるか、サーバープロセス環境に設定されていれば、子エンジン環境に届く。設定値は親環境の値より後に反映される（`serve/server.py:4431-4441`）。
- Intel 用コンテナ経路では `sycl/serve/strata-sycl.sh` が起動され、ホスト環境に `ZES_ENABLE_SYSMAN` が空でも `0` でもない値で存在する必要がある。ランチャーは `STRATA_SYCL_*` を除外しつつ、`ZES_*` を Docker の `-e` 引数にする（`sycl/serve/strata-sycl.sh:33-42`、`sycl/serve/strata-sycl.sh:46-52`）。
- `strata launch --set ZES_ENABLE_SYSMAN=VALUE` のような任意の大文字を含む環境変数名も設定構文として受理され、設定 `env` に反映される。`off`、`unset`、`none` はこの CLI 経路で設定解除として扱われる（`strata_cli/launch/settings.py:228-252`、`strata_cli/launch/settings.py:259-284`、`strata_cli/launch/runner.py:503-510`）。
- GPU backend、GPU 世代、モデル状態による Strata 側の値判定はない。Strata エンジンがこの名前を直接読む箇所は見つからず、転送後に何が有効になるかは本調査範囲では確認できない。

## 実行時の詳細

サーバーの `child_env` はサーバープロセス環境を基に子エンジン用環境を作り、設定 `env` の各項目を `str(k)`、`str(v)` として上書きする。その環境をエンジン起動時に子プロセスへ渡す。値の変更をリクエストごとに読む処理や、Strata エンジン内の cache は確認できない（`serve/server.py:4428-4441`、`serve/server.py:1161-1165`）。

Intel コンテナ経路では、`strata-sycl.sh` の起動時に環境変数名を列挙し、`STRATA_*`、`ONEAPI_*`、`UR_*`、`IGC_*`、`SYCL_*`、`ZES_*` などの値をコンテナ起動引数に追加する。`ZES_ENABLE_SYSMAN` は `ZES_*` に該当する。Strata 側の処理はこの転送までで、エンジン起動後に値を再読込したり変更したりしない（`sycl/serve/strata-sycl.sh:33-52`）。

## ログと測定値

Strata 所有コードに、この変数の値に応じたログ、警告、終了・失敗分岐は見つからない。`000_envvers.md` の候補名に加え、SYCL 用 Dockerfile の既定値、Intel Arc 文書の設定例、研究 harness の環境設定、CLI の環境変数名パターン例に名前が現れるが、これらは Strata エンジンでの値判定を示すものではない。外部依存の `third_party/strata-llama/.../helper.hpp` にある警告文は依存コードの記述であり、Strata 自身のログとして扱わない。

## 根拠

- `serve/server.py:4428-4441` — サーバーの子環境作成と設定 `env` の反映。
- `serve/server.py:1161-1165` — 作成した環境でエンジンを起動。
- `sycl/serve/strata-sycl.sh:33-42` — `ZES_*` を含む環境変数の選別と空文字列・`0` の除外。
- `sycl/serve/strata-sycl.sh:46-52` — 選別した環境を Docker 起動に渡す。
- `sycl/tools/Dockerfile:8` — 開発イメージの `ZES_ENABLE_SYSMAN=1` 既定値。
- `strata_cli/launch/settings.py:228-252`、`strata_cli/launch/settings.py:259-284`、`strata_cli/launch/runner.py:503-510` — 任意の環境変数名を受ける `--set` と設定への反映。
- `strata_cli/launch/cmd.py:121-122` — `--set KEY=VALUE` の CLI 定義。
