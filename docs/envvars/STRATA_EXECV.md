# `STRATA_EXECV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata がこの変数を読む箇所は `setup.py` のサーバー起動処理です。

## 役割

Strata のセットアッププログラムがサーバーを起動するとき、セットアップ側のプロセスをサーバーに置き換えるかを選びます。非 Windows で値が truthy の場合は `os.execve` を使い、通常の `subprocess.call` による子プロセス起動を行いません。ソースコメントは、Docker image では `STRATA_EXECV=1` を設定し、サーバーを PID 1 にして停止シグナルを受けられるようにする意図を説明しています。確認できた読み取り箇所は `setup.py` のみで、サーバーや engine の動作設定として読む箇所はありません。

## 値と判定

| OS / 値 | 起動方法 |
|---|---|
| Windows（値を問わない） | `subprocess.call` でサーバーを子プロセスとして起動 |
| 非 Windows、未設定 | `subprocess.call` で起動 |
| 非 Windows、空文字 | `subprocess.call` で起動 |
| 非 Windows、空でない文字列 | `os.execve` で現在のプロセスをサーバーに置換 |

`os.environ.get("STRATA_EXECV")` の真偽値だけを見ており、文字列の parse や数値変換はありません。そのため `1` だけでなく `0`、`false`、空白を含む任意の非空文字列も有効です。明示的な空文字は未設定と同じ分岐です。範囲、大小文字、無効値時の fallback はありません。

## 有効になる条件

この判定は `setup.py` の `start()` がサーバー起動まで進んだときにだけ実行されます。たとえば `--no-start` の経路は `start()` を呼ばず、変数は評価されません。値が truthy でも Windows では条件の `not WIN` が成立せず、プロセス置換しません。コード上、CUDA / HIP などの backend による追加制限はありません。

CLI 引数や設定ファイルがこの変数を上書きする処理はありません。CLI や設定から組み立てた `cmd` はどちらの分岐でも同じです。`STRATA_EXECV` を設定した起動元では、分岐に使った値もサーバーの環境へ引き継がれます。

## 実行時の詳細

`start()` は設定ファイルやモデルファイルを確認し、GPU/backend に応じた引数を組み立て、起動内容を表示した後にこの環境変数を読みます。したがってサーバー起動直前の評価であり、読み取り結果を保持する static cache はありません。通常のセットアップ CLI では、`main()` からモデル選択後に `start()` が呼ばれます。

非 Windows で値が空でなければ、実行ファイル `cmd[0]`（`sys.executable`）と引数 `cmd` で `os.execve` を呼び、環境には現在の `os.environ` を引き継いで `acquisition.ENV` を `"1"` に設定します。成功時には呼び出し元の Python プロセスが置換されるため、後続の `subprocess.call` には進みません。未設定・空文字、または Windows では同じコマンドを `subprocess.call` で起動し、その戻り値を `start()` の戻り値にします。こちらも環境に `acquisition.ENV="1"` を設定します。

この変数について専用の警告やログ出力はありません。`execve` が失敗した場合、`OSError` を捕捉する分岐はなく、`main()` の例外処理にも該当ハンドラーがないため、通常の未処理例外経路になります。子プロセス起動側では `subprocess.call` の終了コードが返ります。

## 根拠

- `setup.py:7110-7115` — `start()` は acquisition 禁止コンテキスト内で `_start()` を呼ぶ。
- `setup.py:7118-7128,7151-7153` — 設定・ファイル確認とサーバーコマンドの組み立て。
- `setup.py:7253-7262` — 表示後の `STRATA_EXECV` 判定、非 Windows の `execve`、通常の `subprocess.call` と子環境。
- `setup.py:9336-9353,10489-10494` — 通常の既存モデル起動から `start()` への経路とトップレベル例外処理。
- `tools/test_setup_component_start.py:29-49` — テストでは `STRATA_EXECV` を空文字にして `subprocess.call` 経路を模擬する（本番挙動の根拠ではなく、テスト設定の確認）。
- `docs/envvars/000_envvers.md:764` — 候補一覧に名前がある。候補一覧自体は動作根拠ではない。
