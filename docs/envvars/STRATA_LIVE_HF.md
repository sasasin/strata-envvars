# `STRATA_LIVE_HF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この変数は通常の Strata アプリや engine の動作を変える設定ではなく、`terminal/tools/test_qwen4_intake.py` にある Hugging Face の live test を opt-in で実行するためのテストゲートである。同ファイルの `LiveHuggingFace` クラスに `unittest.skipUnless` が付き、環境値が文字列 `"1"` の場合だけクラス内のテストを skip しない（`terminal/tools/test_qwen4_intake.py:426-427`）。候補一覧上の名前は、ここではこのテスト専用の読み取りを指す。

## 値と判定

`os.environ.get("STRATA_LIVE_HF") == "1"` の文字列完全一致で判定する。数値変換、trim、大文字小文字変換はない。未設定、空文字、または `"1"` 以外の値ではテストを skip し、`"1"` だけが skip を解除する（`terminal/tools/test_qwen4_intake.py:426`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `test_qwen4_intake.py` のテストクラス | クラスを skip | `1` | 空文字、`0`、`01`、`1anything`、`true`、`TRUE`、前後に空白のある `1` など |

ここで「有効」はライブテストを実行対象にする意味に限る。アプリや engine に対する既定値、CLI 引数との優先順位、範囲制限はない。`HF_ENDPOINT` はライブテストから呼ばれる `qwen4_intake.py` が HTTP 接続先を選ぶ別の環境変数であり、`STRATA_LIVE_HF` の判定値を上書きしない（`terminal/tools/qwen4_intake.py:663-679`）。

## 有効になる条件

- `terminal/tools/test_qwen4_intake.py` が import されてテストが収集・実行されること。ファイルは `unittest.main()` による直接実行にも対応する（`terminal/tools/test_qwen4_intake.py:597-598`）。
- その import 時点で `STRATA_LIVE_HF` が厳密に `1` であること。ほかの値ではライブテストだけが skip され、同ファイルの他のテストにはこのゲートは掛からない（`terminal/tools/test_qwen4_intake.py:420-427`）。
- 実行時は `setUp` が `STRATA_TEST_ALLOW_NETWORK=1` を一時設定し、ライブテスト用のネットワークガードを通す（`terminal/tools/test_qwen4_intake.py:428-431`）。

OS、GPU backend、build macro、サーバーモード、モデル実行状態による分岐は、この変数の読み取り箇所にはない。Strata アプリを起動するだけでは、このテストゲートは適用されない。

## 実行時の詳細

値はテストモジュールの import 時にクラス定義の `skipUnless` で一度評価される。したがって、同一プロセスで import が済んだ後に環境値を変更しても、そのクラスの skip 判定は更新されない（`terminal/tools/test_qwen4_intake.py:426-427`）。

ゲートを通ると、テストは `qwen4_intake.main()` を Hugging Face の `unsloth/Qwen3.8-Flash-Next-GGUF`、固定 revision、`UD-Q4_K_XL` ディレクトリに対して `--quiet` 付きで呼び、出力 JSON を読み込む。テストコードは実行時間が 60 秒未満であること、判定 case が `A` であること、最初のファイルに SHA-256 値があることを assert する（`terminal/tools/test_qwen4_intake.py:433-443`）。`qwen4_intake.py` は `--hf` でファイル一覧を取得し、各 GGUF のヘッダーを読み、JSON レポートを書き出す。接続先は `HF_ENDPOINT` があればその値、なければ `https://huggingface.co` である（`terminal/tools/qwen4_intake.py:663-681,1110-1133`）。

この処理はテスト・補助ツールの経路であり、モデルを Strata engine で実行したり、通常の生成処理を変更したりするものではない。テスト用の `STRATA_TEST_ALLOW_NETWORK` は `setUp` の patch と cleanup によりテスト期間中だけ設定される（`terminal/tools/test_qwen4_intake.py:428-431`）。

## ログと測定値

ライブテストは `--quiet` を指定するため、`qwen4_intake.py` のレポート表示と JSON パス表示は抑止されるが、JSON ファイル自体は書き出される（`terminal/tools/test_qwen4_intake.py:435-438`、`terminal/tools/qwen4_intake.py:1129-1133`）。60 秒の条件はテストの assert であり、環境変数自体の timeout 設定ではない。ネットワーク呼び出しやレポート処理の例外はテスト失敗として伝播し、時間・case・SHA の assert 不成立も失敗になる（`terminal/tools/test_qwen4_intake.py:433-443`）。Strata アプリのログや終了動作を制御する読み取り箇所はない。

## 根拠

- `terminal/tools/test_qwen4_intake.py:426-443` — 完全一致による skip 判定、ネットワーク許可の一時設定、live test の呼び出しと assert。
- `terminal/tools/test_qwen4_intake.py:597-598` — このテストモジュールの直接実行経路。
- `terminal/tools/qwen4_intake.py:663-681,1110-1133` — 補助ツールの Hugging Face 読み取り、endpoint、quiet 出力、JSON 書き出し。
- `terminal/conftest.py:79-89` — テストプロセスのネットワークガードに関する説明。`STRATA_LIVE_HF` のアプリ実行時の効果を示すものではない。
