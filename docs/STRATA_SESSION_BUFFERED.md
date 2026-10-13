# `STRATA_SESSION_BUFFERED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリや OS の環境変数処理は対象外。

## 役割

セッションファイルの読み書きで、POSIX 実装が `O_DIRECT` を使おうとするのを抑止し、通常の buffered I/O を使わせます。対象は会話セッションの保存・復元で、通常のモデルファイル読み込みには適用されません。セッションファイル機能は server の `SAVE <path>` / `RESTORE <path>` 経路から呼び出されます。

## 値と判定

POSIX 実装では `getenv()` の結果が null でなく、先頭文字が `'1'` のときだけ buffered I/O を強制します。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 強制しない。`O_DIRECT` が利用可能なら使用を試みる |
| 空文字 | 強制しない |
| `1`、`10`、`1anything` | 強制する |
| `true`、`0`、`2`、先頭が空白の ` 1` | 強制しない |

## 有効になる条件

- `RawFile` の POSIX 実装でセッションファイルを新規作成または復元用に開くときに判定されます。`O_DIRECT` がビルド環境に存在しない場合は、常に buffered I/O となり、条件式の短絡により環境変数も読みません。
- `_WIN32` の実装は通常の buffered I/O を使い、この変数を読みません。
- `O_DIRECT` を試す経路でも、ファイルシステムが descriptor への設定を拒否すれば `direct_` は有効にならず、そのまま buffered I/O になります。設定後の読み書きが `EINVAL` で失敗した場合も、`O_DIRECT` を外して同じ操作を再試行します。

## 実行時の詳細

変数は `buffered_forced()` 内で各セッションファイルの open 時に読み直されます。static cache はなく、同一プロセスでも次の open には環境変更が反映されます。書き込みと復元の双方で `RawFile::try_direct()` が呼ばれるため、両方の転送に作用します。

強制時もファイル形式や内容は変わりません。I/O は引き続き 16 MiB ブロックのバッファを経由しますが、direct I/O 用の最終ブロック padding と alignment 条件は使われません。変数専用のログや警告はありません。

## 根拠

- `src/core/conversation_file.cpp:79-92` — セッションファイル転送の 16 MiB バッファと direct/buffered I/O の説明・アライン済みバッファ。
- `src/core/conversation_file.cpp:339-342,443-449` — `getenv()` と先頭文字判定、`O_DIRECT` を試す条件。
- `src/core/conversation_file.cpp:350-374` — 保存用ファイルと復元用ファイルを開く際の判定。モデル入力用の `open_model()` は `try_direct()` を呼ばない。
- `src/core/conversation_file.cpp:388-406,552-565,608-620` — I/O 時の `EINVAL` fallback、書き込み padding、ブロック読み込み。
- `src/program/generate.cpp:9764-9774,9895-9902,9934-9942` — server の SAVE/RESTORE コマンドからセッションファイル read/write を呼ぶ経路。
- `docs/DETAILS.md:1193-1197` — セッションファイル機能の利用条件と、Linux で `O_DIRECT` を使い、`STRATA_SESSION_BUFFERED=1` または未対応ファイルシステム等で buffered I/O にする説明。資料には Linux/CUDA での実行実績が記されている。
