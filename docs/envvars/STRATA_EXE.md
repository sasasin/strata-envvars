# `STRATA_EXE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

同梱の3つの会話キャッシュ診断スクリプトが起動する Strata engine 実行ファイルを、実行設定 JSON の `exe` 値から差し替えます。対象は `tools/session_pressure_test.py`、`tools/cancel_park_test.py`、`tools/batch_groups_cache_test.py` です。通常のサーバー起動設定や `setup.py` の起動処理がこの変数を読む実装は確認できません。

## 値と判定

| 環境変数の状態 | 実行ファイルの選択 |
|---|---|
| 未設定 | JSON 設定の `cfg["exe"]` |
| 設定済み（空文字を含む） | `os.environ.get("STRATA_EXE", cfg["exe"])` が返す環境変数値 |

値の parse、空文字の除外、パスの検証や正規化は行いません。したがって空文字を設定すると JSON の値へ戻らず、空文字が `StrataEngine` に渡されます。別の実行ファイルパスを指定した場合も、その文字列をそのまま使います。

## 有効になる条件

この変数を読むのは上記の診断スクリプトだけです。スクリプトを実行しない通常の Strata CLI / server 使用では、この変数による実行ファイル選択はありません。各スクリプトは JSON 設定などを読み込んだ後、環境変数を優先して `StrataEngine` を作ります。

## 実行時の詳細

選択された値は `StrataEngine(exe, ...)` に渡されます。`StrataEngine` は `Path(exe).parent / "BUILD.json"` からバージョン情報を試みて読み、起動時には `[exe, "--serve", *args]` を `subprocess.Popen` に渡します。`BUILD.json` が読めない場合はバージョン情報を `None` にします。実行ファイルが起動できない場合は `popen` が通常の `OSError` を再送出します（特定の Windows ポリシーエラーには説明文を付加します）。

環境変数は各診断スクリプトのモジュール初期化時に一度選択され、同じスクリプト内の `StrataEngine` 起動に使われます。`StrataEngine` の再起動時も保存済みの `exe` を使います。実行中に環境変数を変更しても、選択済みの実行ファイルは切り替わりません。子プロセスに渡す環境辞書は `child_env(cfg)` が別に構成し、`STRATA_EXE` はその辞書を通じて起動先を選択するものではありません。

## 根拠

- `tools/session_pressure_test.py:29-30`、`tools/cancel_park_test.py:30-31`、`tools/batch_groups_cache_test.py:33`: 環境変数を `cfg["exe"]` より優先して `StrataEngine` に渡す。
- `serve/server.py:793-815`: 実行ファイル値を保持し、同じ値から `BUILD.json` を参照する。
- `serve/server.py:837-843`: `--serve` と引数を付けて engine を起動する。
- `serve/server.py:76-88`: `subprocess.Popen` の呼び出しと起動時 `OSError` の扱い。
- `serve/server.py:2858-2875`: 子プロセス環境の構築。実行ファイル値の選択とは別の処理。

