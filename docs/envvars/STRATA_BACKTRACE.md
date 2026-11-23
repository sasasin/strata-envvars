# `STRATA_BACKTRACE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Python 起動側が、子プロセス用環境に `GGML_NO_BACKTRACE=1` を自動で追加するかを制御する開発者向けスイッチ。設定が有効なら helper は `GGML_NO_BACKTRACE` を新たに設定せず、呼び出し元の環境をそのままにする。engine の CLI 引数や生成処理を直接変更する読み取り箇所は見つからず、Strata が値を読むのは `terminal/strata_control/childenv.py` の `developer_wants_backtrace` だけである（`terminal/strata_control/childenv.py:15-16,49-64`）。

この helper は CLI、runtime host/server、engine 起動、画像・モデル情報 probe、setup、tuning などの子プロセス環境を作る経路から呼ばれる。たとえば CLI と setup はエントリ時に自身の `os.environ` を変更し（`terminal/strata_cli/cli.py:2314-2318`, `terminal/setup.py:11198-11202`）、managed runtime は server 用の環境コピーを作り（`terminal/strata_control/runtime.py:1051-1066`）、server は engine 用環境を作る（`terminal/serve/server.py:3870-3874`）。

## 値と判定

helper は渡された mapping（省略時はプロセスの `os.environ`）と現在の `os.environ` を順に調べ、値を `str(...)` にして前後空白を除去し、小文字化する。空になった値、および正規化後が `0`、`no`、`off`、`false` の値は無効。それ以外の非空文字列は有効で、全体の真偽文字列や数値として parse するわけではない（`terminal/strata_control/childenv.py:49-55`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `developer_wants_backtrace` の判定 | 両方の環境に未設定なら false | `1`, `true`, `yes`, `00`, `0anything` | 空文字、空白だけ、`0`, `no`, `off`, `false`（大小文字は不問、前後空白は無視） |

mapping の値は `str` に変換されるため、文字列以外を渡した場合もその文字列表現で判定される。たとえば `None` は空値扱いではなく `"None"` となり有効判定になる。実運用上の helper 呼び出しは環境文字列の mapping を渡す（同 `childenv.py:49-55,58-64`）。

有効判定は `GGML_NO_BACKTRACE` の既存値を消さない。対象 mapping に同名キーが既にあれば、`STRATA_BACKTRACE` の値にかかわらず helper は上書きしない。キーがなく、かつスイッチが無効なら `GGML_NO_BACKTRACE="1"` を追加する（`terminal/strata_control/childenv.py:58-64`）。engine 用環境では、その後 `cfg["env"]` の各項目が代入されるため、設定に `GGML_NO_BACKTRACE` があれば helper の結果を上書きできる（`terminal/serve/server.py:3870-3874,3890-3891`）。

## 有効になる条件

- `STRATA_BACKTRACE` は `terminal/strata_control/childenv.py` を使う起動経路で評価される。Python helper 内に OS・backend・build macro の条件分岐はない（`terminal/strata_control/childenv.py:49-64`）。
- helper を呼ぶ時点で、渡された環境 mapping または呼び出し元プロセスの環境のいずれかに、有効な値が必要。渡された mapping 側が false でも、プロセス環境側が有効なら有効判定となる（同 `childenv.py:51-55`）。
- 有効時も、すでに渡された環境に `GGML_NO_BACKTRACE` がある場合は削除されない。したがって、この変数だけでは既存の `GGML_NO_BACKTRACE` を解除しない（同 `childenv.py:61-64`）。
- server engine の場合は、helper の後で profile/config の `env` 項目が環境を上書きする（`terminal/serve/server.py:3870-3874,3890-3891`）。
- 専用の CLI 引数や Strata 設定ファイル項目として `STRATA_BACKTRACE` を解釈するコードは見つからない。汎用の engine `env` 設定は上記のとおり `GGML_NO_BACKTRACE` を後から上書きできる。

## 実行時の詳細

判定は共通 helper が呼ばれるたびに実行され、結果を module/static cache する実装はない（`terminal/strata_control/childenv.py:49-64`）。helper 呼び出し前にプロセスの環境が変更されれば、次の呼び出しでは新しい値を判定する。子プロセス用 dict を渡した呼び出しではその dict がその場で変更されて返る。引数省略時は `os.environ` 自体が変更され、その後に起動する子プロセスがその環境を継承する（同 `childenv.py:58-64`、呼び出し例 `terminal/strata_control/runtime.py:1650-1651`, `terminal/serve/server.py:8472-8481`）。

利用箇所は共通 helper を通している。確認できた本番コードの呼び出し元には `terminal/strata_control/local_engine.py:48-54`、`terminal/strata_control/runtime.py:1056-1074,1650-1651`、`terminal/serve/server.py:3870-3874,8480-8481,8605-8612`、`terminal/serve/images.py:177-184`、`terminal/strata_cli/launch/runner.py:969-979`、`terminal/setup.py:11198-11202`、tuning 系（`terminal/strata_control/tuning.py:208-220`, `terminal/strata_control/tune_session.py:551-559`, `terminal/strata_control/tune_engine.py:422-426`, `terminal/strata_control/tune_api.py:79-87`）、および `terminal/serve/hy4_kind.py:84-91` と `terminal/serve/inkling_kind.py:74-82` がある。各経路は子プロセスの起動や環境生成に応じて helper を呼ぶ。

## ログと測定値

この変数を判定したり `GGML_NO_BACKTRACE` を追加したりする際、Strata の helper はログを出さず、エラー終了もしない（`terminal/strata_control/childenv.py:49-64`）。調査対象コード中に、この変数に関する Strata の測定値はない。ここでは下流ライブラリが `GGML_NO_BACKTRACE` をどう解釈するかは説明しない。

## 根拠

- `terminal/strata_control/childenv.py:15-16,49-64` — 名前、値の正規化と拒否値、両環境の判定、`GGML_NO_BACKTRACE` の追加条件。
- `terminal/strata_cli/cli.py:2314-2318`, `terminal/setup.py:11198-11202` — エントリ時に helper を呼ぶ経路。
- `terminal/strata_control/runtime.py:1051-1074,1650-1651` — runtime host/server の子プロセス環境。
- `terminal/serve/server.py:3870-3891,8472-8481` — server の engine 環境と config `env` による後続上書き、および直接起動時の helper 呼び出し。
- `terminal/strata_control/local_engine.py:48-54`, `terminal/serve/images.py:177-184`, `terminal/strata_cli/launch/runner.py:969-979`, `terminal/strata_control/tuning.py:208-220`, `terminal/strata_control/tune_session.py:551-559`, `terminal/strata_control/tune_engine.py:422-426`, `terminal/strata_control/tune_api.py:79-87`, `terminal/serve/hy4_kind.py:84-91`, `terminal/serve/inkling_kind.py:74-82` — helper を使う他の本番環境生成経路。
