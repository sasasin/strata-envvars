# `STRATA_RUNTIME_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

管理ランタイムが実行状態、ロック、ready ファイル、ロールバック用スナップショットなどを置くディレクトリを指定します。対象は `strata runtime` のローカル管理ホストです。Desktop の診断ログ収集も同じ変数を参照してサーバーログを探します。

## 値と判定

| 値 | 管理ランタイム (`strata_control/runtime.py`) の扱い |
|---|---|
| 未設定 | `paths.state_base() / "runtime"` を使う。POSIX は `${XDG_STATE_HOME:-~/.local/state}/strata/runtime`、Windows は `${LOCALAPPDATA:-%USERPROFILE%/AppData/Local}/Strata/runtime`。|
| 空文字 | Python の `os.environ.get()` の結果が偽になるため、未設定と同じ既定先を使う。|
| 空でない絶対パス | `Path(...).expanduser()` で先頭の `~` を展開して使用する。存在しなければ親ディレクトリも作成する。|
| 空でない相対パス | `ProfileError("STRATA_RUNTIME_DIR must be absolute")` で拒否する。|

値はパスとして扱われ、真偽値・数値・文字列全体の追加 parse はありません。空白だけの値も空ではないため相対パスとして拒否されます。`~` 展開は `Path.expanduser()` の規則に従い、環境変数展開や前後の空白除去は行いません。

## 有効になる条件

- 管理ランタイムのディレクトリを必要とする操作で有効です。`runtime_dir()` は `acquire_activity_lease()`、`active_managed_instances()`、state/ready 検証や rollback snapshot 探索などから呼ばれます。
- Windows 以外では POSIX の owner-only 検査が適用されます。指定先はディレクトリで、他ユーザーに開放されない必要があります。現在ユーザー所有で mode が広すぎる場合、実装は `0700` に直せるか試します。他ユーザー所有、シンボリックリンク等で要件を満たさない場合は拒否します。
- Windows では ACL のあるファイルシステムで現在ユーザーだけに制限されたディレクトリを要求します。既存ディレクトリの ACL が不十分なら修復を試み、満たせなければ拒否します。FAT/exFAT のように ACL を持たないボリュームでは警告を stderr に出して続行します。
- Desktop の `apps/host/server/index.mjs` の診断ログ収集は管理ランタイムとは別に `process.env.STRATA_RUNTIME_DIR ?? <components の隣>/runtime` を使います。この箇所は相対パス検査や `~` 展開をせず、列挙・読込エラーを握りつぶします。したがって空文字は nullish fallback にならず、空パス側を試します。

## 実行時の詳細

`runtime_dir()` は呼び出しごとに `os.environ.get("STRATA_RUNTIME_DIR")` を評価し、結果を static/cache しません。したがって同一プロセス内で環境辞書が変更されれば、後続呼び出しは新しい値を見ます。通常のプロセス起動後に親シェルの環境が変わっても、すでに起動済みのプロセスの環境は自動では変わりません。

POSIX では最終ディレクトリを `lstat()` してディレクトリであることと owner-only 条件を確認します。Windows では ACL の有無を調べ、ACL を使える場合は新規作成先の保護や既存 ACL の修復を行ってから検査します。POSIX の不適切な mode は所有者が現在ユーザーなら `chmod(0700)` を試し、mode を保持できないファイルシステムでは stderr に一度注意を出して続行する実装です。指定ディレクトリが不適格な場合のエラー文は、POSIX では `runtime directory must be owner-only (mode 0700)`、Windows では状況に応じてアクセス可能なアカウント等を含む説明になります。

`strata_control/private_files.py` にあるユーザーデータ修復対象の判定も `STRATA_RUNTIME_DIR` をルート候補に含めます。ここでは非空の値を `Path` として読み、resolve して修復対象の所有範囲を判断します。管理ランタイム本体の `expanduser()` と絶対パス検査とは別の処理です。

## 根拠

- `strata_control/runtime.py:101-129` — 環境変数読取、空値時の既定パス、`~` 展開、絶対パス検査、ディレクトリ作成と platform ごとの権限処理。
- `strata_control/runtime.py:173-206,239,317,351` — 管理ランタイム関連操作から `runtime_dir()` を呼ぶ箇所。
- `strata_control/paths.py:13-21` — OS ごとの state base と既定値。
- `strata_control/posix_owner.py:26-54` — POSIX 所有者・mode 検査と修復、および mode 非対応ファイルシステム時の stderr 注意。
- `strata_control/private_files.py:415-439,506-524` — 環境変数をユーザーデータのルート候補として使う処理。
- `apps/host/server/index.mjs:983-994` — Desktop の診断ログ収集での直接参照と fallback。
- `docs/TERMINAL.md:94` — 利用者向け説明では `${XDG_STATE_HOME:-~/.local/state}/strata/runtime` または `STRATA_RUNTIME_DIR` を使うと記載。実装の Windows 既定値はこの POSIX 表記とは異なります。
