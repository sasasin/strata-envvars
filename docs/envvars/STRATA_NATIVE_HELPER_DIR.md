# `STRATA_NATIVE_HELPER_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal の Python コードが、明示的に有効化された native helper 実行ファイルを探すディレクトリを指定する。変数値を真偽値や数値には変換せず、前後の空白を除いた文字列をフォルダー名として使う。値だけを設定しても helper は動かず、`STRATA_NATIVE_HELPERS` が `gguf-preflight` または `all` を選び、指定場所に対応する通常ファイルがある必要がある（`terminal/strata_control/native_helpers.py:54-75`）。

本 commit での利用先は GGUF メタデータの import preflight である。helper が使えない場合は同じ処理の Python 実装へ戻る。これは Terminal の Python 経路であり、engine の GPU backend やサーバー推論を切り替える設定ではない（`terminal/strata_control/gguf_preflight.py:165-185`、`terminal/strata_control/native_helpers.py:99-125`）。

## 値と判定

`program()` は有効化判定後に `env.get(DIR_ENV, "")` を取得し、`str(...).strip()` した結果が空なら配置先なしとして `None` を返す。未設定、空文字、空白だけの値は同じ扱い。非空値はパス文字列として使い、他の形式検証や値域検査はしない（`terminal/strata_control/native_helpers.py:62-75`）。

| 条件 | unset | 配置先として使う値 | helper 不在・無効時 |
|---|---|---|---|
| Terminal Python が `gguf-preflight` を有効化 | 空文字扱い。helper は見つからない | 空白を除いた任意の非空パス。例: `/opt/strata/helpers`、`./target/release`、`0`（最後の例も真偽値でなく相対パス名） | 空文字・空白だけは配置先なし。実行ファイルがない、`stat()` が `OSError` になる、または子のパスが通常ファイルでなければ配置先なし。PATH は検索しない |
| `STRATA_NATIVE_HELPERS` が helper を選ばない | 同左 | この変数は読まれず、値が設定されていても使わない | helper を呼ばず Python 実装へ進む |

実行ファイル名は POSIX 系では `<dir>/strata-gguf-preflight`、Windows では `<dir>/strata-gguf-preflight.exe`。`Path.stat()` の結果を `stat.S_ISREG` で確認するため、実行権限をここでは検査しない。実際に起動できない場合は後段で「利用不可」となる。末尾の空白は除去され、パスの大文字小文字や存在性は Python の `Path` / OS に渡される（`terminal/strata_control/native_helpers.py:67-75, 105-113`）。

## 有効になる条件

- `STRATA_NATIVE_HELPERS` の値を `strip().lower()` し、全体が空、`0`、`off`、`none`、`no`、`false` のいずれかなら無効。その他はカンマで分け、各項目の前後空白を除いて `gguf-preflight` または `all` が含まれる場合だけ有効。個別名との比較も小文字化後に行われる（`terminal/strata_control/native_helpers.py:54-59`）。
- 有効化後も本変数が空なら不使用。指定先に上記の名前の通常ファイルがなければ不使用となる。PATH や Rust の `target/release` / `target/debug` からの自動発見はしない（`terminal/strata_control/native_helpers.py:62-75`）。
- `gguf_preflight._native_inspect()` が呼ばれる処理に限る。ソース上では Terminal のモデル import plan と projector 確認など `inspect_metadata()` の呼び出し、および `setup.py` の既存 GGUF 完全性確認が該当する（`terminal/strata_control/models.py:673-701, 854-860, 967-980`、`terminal/setup.py:3739-3746`）。
- OS による実行ファイル名の違い以外に backend、GPU、build macro、モデルの実行状態による条件はない。CLI 引数でこのディレクトリを上書きする処理も見当たらない（`terminal/strata_control/native_helpers.py:62-75`）。

## 実行時の詳細

環境値はプロセス起動時に固定・キャッシュされない。`inspect_metadata()` が helper 判定に達するたびに `enabled()` が環境を調べ、`call()` から `program()` に入る際にも再判定し、その後に本変数を読み取る。値は既定で `os.environ` から読む。従ってプロセス内で環境を変更した場合は次の呼び出しで反映される（`terminal/strata_control/gguf_preflight.py:165-185`、`terminal/strata_control/native_helpers.py:54-75, 99-105`）。

見つけた helper は `--strata-protocol 1 inspect <GGUF の実パス>` で起動され、最大 10 秒待つ。タイムアウト、起動時の `OSError`、1 MiB 超の stdout、UTF-8/JSON 不正、protocol 不一致、応答 schema 不一致などは `Unavailable` となり、呼び出し元がそれを捕捉して Python の reader を使う。準拠した `ok: false` 応答は `Rejected` となり、`ProfileError` に変換されて Python reader への再試行はしない（`terminal/strata_control/native_helpers.py:99-130`、`terminal/strata_control/gguf_preflight.py:172-185`）。

helper の有効な結果は Python reader と同じ metadata preflight の戻り値として扱われる。たとえば `models import --plan` では、その結果が candidate の判定や表示内容に使われ、issue があれば CLI は stderr に問題文を出して終了コード 5 を返す。配置先の値そのものについてのログや警告は実装されていない（`terminal/strata_control/models.py:967-980, 1018-1040`、`terminal/strata_cli/cli.py:590-599`）。

## ログと測定値

この変数の読み取り・配置先確認・利用不可への fallback に固有のログ出力はない。helper が利用不可なら `gguf_preflight.py` がその例外を捕捉して `None` を返し、Python reader が続行する。helper が有効な拒否応答を返した場合は `ProfileError` になる。測定値は該当資料に記載がない（`terminal/strata_control/native_helpers.py:62-75, 99-130`、`terminal/strata_control/gguf_preflight.py:172-185`）。

## 根拠

- `terminal/strata_control/native_helpers.py:30-34, 54-75` — 変数名、依存する有効化設定、空白除去、パス構築、通常ファイル確認。
- `terminal/strata_control/native_helpers.py:99-130` — 起動引数、timeout、出力上限、プロトコル検査と利用不可・拒否の判定。
- `terminal/strata_control/gguf_preflight.py:165-185` — helper 呼び出しと拒否・利用不可時の分岐。
- `terminal/strata_control/models.py:673-701, 854-860, 967-980` — model import plan / picture reader 確認からの使用。
- `terminal/setup.py:3739-3746, 3779-3813` — setup が自前 GGUF の完全性確認に同じ preflight を使う箇所。
- `terminal/strata_cli/cli.py:590-599` — `models import --plan` の可視結果と issue 時の終了コード。

