# `STRATA_GATE_SETUP_TIMEOUT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`tools/feed_model_install_gate.py` の feed-install gate が `setup.py` を実行する際の、1 回あたりの待ち時間上限（秒）を指定する。Strata の推論エンジンや通常の `setup.py` 起動を直接設定する変数ではなく、この gate スクリプトの setup 検査だけで使われる。既定値は 300 秒である（`tools/feed_model_install_gate.py:57,257-269`）。

## 値と判定

モジュール読み込み時に `os.environ.get("STRATA_GATE_SETUP_TIMEOUT", "300")` の結果を Python の `int()` に渡す。未設定なら文字列 `"300"` が使われる。空文字も設定値として返るため `int("")` となり、`ValueError` が発生する。整数として解釈できない文字列（例: `"3s"`, `"1.5"`）も同様に失敗し、gate の `main()` に入る前に終了する。整数として解釈される値は符号や前後空白を含められ、`0` や負数も特別扱いされず、そのまま保存される。ソース側に範囲検査、丸め、clamp、無効値 fallback はない（`tools/feed_model_install_gate.py:57`）。

| 条件 | unset | 設定時に渡される値 | 変換に失敗する例 |
|---|---|---|---|
| gate スクリプトを import するすべての実行経路 | `300` 秒 | `"12"` → `12`、`" 12 "` → `12`、`"0"` → `0`、`"-1"` → `-1` | 空文字、`"3s"`、`"1.5"` は `ValueError` |

この変数用の CLI 引数や別設定との優先順位はない。CLI が指定する `--tokenizer-from`、`--engine`、`--full` などは timeout 値を上書きしない（`tools/feed_model_install_gate.py:426-433`）。

## 有効になる条件

- `tools/feed_model_install_gate.py` が import または直接実行され、`run_setup()` の既定引数を使う setup 検査で有効になる。テスト `tools/test_feed_model_install_realfile.py` も同モジュールを import してこの経路を使う（`tools/feed_model_install_gate.py:257`, `tools/test_feed_model_install_realfile.py:19-22,37`）。
- 1 回目と 2 回目の setup 実行はいずれも同じ `SETUP_TIMEOUT` を使う（`tools/feed_model_install_gate.py:289-294,325-330`）。
- gate は setup 子プロセス向けの環境を作る際、親環境から `STRATA_` で始まる名前を除外する。このため、この変数は子の `setup.py` に渡される設定ではなく、親 gate が `communicate()` の timeout に渡す値である（`tools/feed_model_install_gate.py:234-242,257-264`）。
- `--engine --full` のエンジン起動・サーバー準備・リクエスト段階には適用されない。エンジン起動待ちは別途 600 秒の deadline、HTTP 要求にも個別の timeout が使われる（`tools/feed_model_install_gate.py:373-407`）。

## 実行時の詳細

環境値は関数呼び出しごとではなく、Python がモジュールを読み込む時に一度 `SETUP_TIMEOUT` へ変換・保持する。実行中に環境変数を変更しても、すでに import 済みのモジュールでは値は再読込されない（`tools/feed_model_install_gate.py:57`）。

`run_setup()` は `setup.py` を `subprocess.Popen` で起動し、合流した標準出力・標準エラーを `proc.communicate(timeout=timeout)` で待つ。期限内なら子の終了コードと出力を返す。期限切れなら gate は起動したプロセスツリーを終了させ、終了後に出力を回収して終了コード `124` と `[the gate stopped setup after {timeout} s]` を付けた出力を返す。ここで timeout 値の明示的な範囲検証は行われない（`tools/feed_model_install_gate.py:246-269`）。

setup が `124` を返した場合、`check()` は `setup exited 124` を問題として記録する。gate の標準出力には `setup run 1: exit 124 in ... s`（または 2 回目の行）が記録され、問題があれば `FAIL:` と問題一覧、setup 出力末尾が表示され、通常の gate 終了コードは `1` になる（`tools/feed_model_install_gate.py:293-298,329-337,457-464`）。

## ログと測定値

timeout 発生時の setup 出力には `[the gate stopped setup after {timeout} s]` が追記される。gate は各 setup 実行について `setup run 1: exit {code} in {seconds} s` / `setup run 2: exit {code} in {seconds} s` を時刻付きで標準出力へ出し、失敗時は `FAIL:` と `setup exited {code}` を出す（`tools/feed_model_install_gate.py:257-269,293-298,329-337,437-438,457-463`）。この変数に関連する性能測定値は、候補一覧以外の Strata 資料・実装では確認できなかった。

## 根拠

- `tools/feed_model_install_gate.py:57` — 環境変数の読み取り、既定値、整数変換のタイミング。
- `tools/feed_model_install_gate.py:234-242,257-269` — gate 子環境からの `STRATA_` 除外、setup 実行の timeout と timeout 経路。
- `tools/feed_model_install_gate.py:289-298,325-337,426-475` — setup 実行回数、ログ、失敗判定と gate 終了コード。
- `tools/feed_model_install_gate.py:373-407` — エンジン段階に別の待ち時間があること。
- `tools/test_feed_model_install_realfile.py:19-22,25-40` — 同 gate モジュールを使うテスト経路。
