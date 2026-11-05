# `STRATA_BLOCKING_CONSOLE`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

Python サーバーの標準出力・標準エラーに設ける非同期出力ラッパーを無効にします。値が厳密に `1` のとき、サーバーは `decoupled_console()` を使わず `_main()` を直接実行します。既定では独立した writer thread と有界キューを使い、コンソールや出力 pipe が詰まってもサーバーのリクエスト処理をその出力待ちで止めにくくします。この変数は Strata の C++ engine や GPU backend の設定ではなく、Python サーバープロセスの出力経路を切り替えます。

## 値と判定

`serve/server.py` は `os.environ.get("STRATA_BLOCKING_CONSOLE") == "1"` を判定します。文字列を trim・数値変換せず、値全体を大文字小文字を区別して比較します。

| 環境値 | 動作 |
| --- | --- |
| 未設定 | `decoupled_console()` を使う |
| 空文字 | `decoupled_console()` を使う |
| `1` | ラッパーを使わず `_main()` を実行する |
| `01`, `1 `, `true`, `TRUE`, `0` など | `decoupled_console()` を使う |

専用の警告、エラー、値の fallback はありません。CLI 引数や設定ファイルによる上書きもなく、この条件式の結果で選択されます。根拠: `serve/server.py:9842-9847`。

## 有効になる条件

`serve.server.main()` が呼ばれたときに適用されます。CLI の `strata serve` はこの `main()` を呼び出し（`strata_cli/cli.py:945-956`）、サーバーを直接起動する経路も同じ実装を使います（`serve/server.py:9842-9847,10487`）。setup が生成する起動コマンドは `serve/server.py` を起動します（`setup.py:7593-7594,8130-8141`）。mock/Strata engine や CUDA/HIP 等の backend による分岐はありません。

ラッパーは `sys.stdout` / `sys.stderr` がそれぞれプロセス本来の標準ストリーム（`sys.__stdout__` / `sys.__stderr__`）である場合だけ取り付けられます。テスト runner などが差し替えたストリームは既定経路でもそのままです（`serve/nonblocking_out.py:105-123`）。環境変数は `main()` の分岐で毎回評価されるため、モジュール import 時の固定値や static cache ではありません。一度 `_main()` が走り始めた後には再評価されません。

## 実行時の詳細

値が `1` 以外の場合、既定の `decoupled_console()` は対象となる標準出力・標準エラーごとに `NonBlockingOut` を作成します。`write()` は最大 1 MiB または 4000 chunk の有界キューに入れて戻り、上限を超えると古い chunk から捨てます。実ストリームへの書き込みと flush は `strata-console` daemon thread が行います。実ストリームの書き込みで `OSError`、`ValueError`、`UnicodeError` が起きた場合、その出力は失われます。サーバー終了時は最大 2 秒 drain を試みてからラッパーを復元します（`serve/nonblocking_out.py:20-32,34-54,68-103,105-123`）。

値が `1` の場合はこれらの wrapper・キュー・writer thread を作らず、通常の Python 標準ストリームへ同期的に出力します。そのため、標準ストリームの書き込みが遅い・停止している場合に出力を行ったサーバー処理も待つ経路になります。Strata の資料・実装にはこの環境変数専用のログや状態表示はなく、選択結果は出力経路にだけ現れます。既定ラッパーは診断出力用で、engine の pipe や HTTP 応答は対象外です（`serve/nonblocking_out.py:1-10`）。

## 根拠

- `serve/server.py:9834-9847` — 既定動作と環境変数の厳密な値判定、サーバー本体への適用。
- `serve/server.py:10487` — スクリプトとして実行したとき `main()` を呼ぶ入口。
- `serve/nonblocking_out.py:20-54,68-103,105-123` — キュー上限、古い出力の破棄、非同期書き込み、例外処理、終了時 drain、ストリームの対象条件。
- `strata_cli/cli.py:945-956` — `strata serve` からの呼び出し。
- `setup.py:7593-7594,8130-8141` — setup が生成・実行する Python サーバー起動経路。
