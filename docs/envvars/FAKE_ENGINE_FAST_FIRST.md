# `FAKE_ENGINE_FAST_FIRST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前を読む箇所は `tests/terminal/lifecycle_matrix.py` 内に埋め込まれた偽エンジンの Python スクリプトです。`FAKE_ENGINE_SLOW_STEPS` が非ゼロの場合に、生成要求ごとの疑似生成ループを指定回数ではなく 1 回にします。Strata の通常のエンジン、サーバー、CLI がこの名前を設定として読む箇所はありません。候補一覧にはありますが、通常利用者向けの Strata 実行時設定ではなく、ライフサイクル検証用 fake engine の制御です。

## 値と判定

埋め込みスクリプトは `os.environ.get("FAKE_ENGINE_FAST_FIRST")` の真偽値を条件に使います。文字列を数値や真偽値として parse せず、空文字列だけが偽です。

| `FAKE_ENGINE_FAST_FIRST` | 判定 | `FAKE_ENGINE_SLOW_STEPS` が非ゼロの場合 |
|---|---|---|
| 未設定 | 偽 | 指定された `slow` 回ループ |
| 空文字列 | 偽 | 指定された `slow` 回ループ |
| 空でない任意の文字列（例: `1`, `0`, `false`） | 真 | 1 回ループ |

`FAKE_ENGINE_SLOW_STEPS` が `0` の場合は、この変数の状態によらず 1 回ループです。負数は Python では非ゼロですが、変数が偽なら `range(slow)` は 0 回となり、`T 97` を出さず `DONE` へ進みます。変数が真なら負数の場合も 1 回ループです。`slow` の取得は `int(os.environ.get("FAKE_ENGINE_SLOW_STEPS", "0"))` なので、空文字や整数にできない値は生成要求を処理する際に `ValueError` になります。

CLI 引数や設定ファイルによるこの変数の上書きはありません。`Rig` は親プロセスの環境をコピーし、slow-step 値などを追加してサーバー起動環境として渡します。そのため、この値は呼び出し側の環境から fake engine へ継承されます。

## 有効になる条件

- `tests/terminal/lifecycle_matrix.py` が fake engine を使う経路で動く場合に限ります。`--config` で実エンジンを指定すると fake engine は使われません。
- 条件式は `GEN` または `BGEN` 要求を fake engine が受け取ったときに評価されます。
- 実際に遅いループとの差が出るのは `FAKE_ENGINE_SLOW_STEPS` が非ゼロの場合だけです。ライフサイクル matrix は通常、`serve-busy-stop` のケースに限り `slow_steps=600` を設定し、他のケースは `0` です。
- 名前に `FIRST` とありますが、実装に「最初の要求だけ」を識別する状態はありません。環境変数が真なら、そのプロセスが処理する各 `GEN` / `BGEN` 要求で 1 回ループになります。

## 実行時の詳細

`Rig` は既存環境を `self.env` にコピーし、`FAKE_ENGINE_SLOW_STEPS` を `slow_steps` で設定します。対象変数は削除も上書きもされません。`spawn_serve()` はその環境を `strata.py serve` に渡します。fake engine は lifecycle matrix が一時的に生成する `engine_main.py` で、同スクリプトが環境から対象変数を読みます。生成要求を受けるとループ回数に従って標準出力へ `T 97` を出し、最後に `DONE 1 1 1.0 1.0 length 0 0 0` を出します。STOP を受けるとループを抜けて `DONE` に進みます。

対象変数自体によるログ、警告、終了コードの変更はありません。fake engine の整数変換などで例外が起きた場合の扱いはこの変数の処理ではなく、外側のテスト／サーバープロセスの失敗経路です。pytest wrapper は matrix の各ケース結果の `ok` を検査します。

## 根拠

- 偽エンジンの埋め込み、環境値の読み取り、生成ループと出力: `tests/terminal/lifecycle_matrix.py:41-82`
- fake engine のインストールと一時環境・slow-step 値の準備: `tests/terminal/lifecycle_matrix.py:102-118,130-176`
- サーバープロセスへの環境引き渡し: `tests/terminal/lifecycle_matrix.py:252-267`
- `serve-busy-stop` にだけ非ゼロの slow-step 値を渡す箇所: `tests/terminal/lifecycle_matrix.py:762-769`
- pytest wrapper が fake-engine lifecycle matrix を実行し、結果を検査する箇所: `tests/terminal/test_lifecycle_matrix.py:1-6,21-32`

調査対象リポジトリ全体を `rg` で検索した結果、この候補名の参照は埋め込み fake engine 内の 1 箇所だけでした。`000_envvers.md` の候補名はこのテスト専用の環境変数を拾っています。
