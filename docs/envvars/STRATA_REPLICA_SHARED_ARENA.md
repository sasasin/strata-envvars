# `STRATA_REPLICA_SHARED_ARENA`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata の serving server が複数レプリカを起動するとき、各エンジンに共有 expert arena のパスを `--shared-expert-arena` として渡すかを選びます。共有が成立すると、最初のエンジンが arena に expert を読み込み、他のエンジンは同じ arena を使うため、expert 用の RAM コピーをレプリカごとに作らずに済みます。これは `serve/replicas.py` の `shared_arena_plan` が行う server 側の判断で、エンジン側の独立した環境変数ではありません（`serve/replicas.py:161-224`、`serve/server.py:9555-9577`、`src/core/expert_source.cpp:6269-6303`）。

## 値と判定

`shared_arena_plan` はまず `cfg.get("replica_shared_arena")` を確認し、その値が `None` の場合だけ、渡された `environ`（通常は `os.environ`）から変数を読みます。環境変数は値を文字列化し、前後の空白を `strip()` で取り除き、小文字化してから `1`、`true`、`on`、`yes` のいずれかと完全一致するかを判定します。数値変換はせず、空文字や部分一致は有効になりません（`serve/replicas.py:167-172`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `cfg["replica_shared_arena"]` が `None`（通常の環境変数判定） | 無効 | `1`, `true`, `on`, `yes`。大文字小文字は区別せず、前後空白は無視 | 空文字、`0`, `false`, `off`, `no`, `0anything`, `trueish`。いずれも許可語との完全一致ではない |
| `cfg["replica_shared_arena"]` が `None` 以外 | 環境変数を読まず、設定値の真偽値で判定 | 真と評価される設定値 | 偽と評価される設定値 |

設定ファイルの `replica_shared_arena` が明示されると環境変数より優先します。レプリカプロファイルが適用されると、共有可能な OS では `cfg.setdefault("replica_shared_arena", True)` を設定するため、そこでは環境変数 `=0` も上書きできません（`strata_control/replica_profile.py:102-118`）。設定値の型検証はこの判定箇所にないため、文字列 `"false"` も Python では真として扱われます（`serve/replicas.py:169-172`）。

## 有効になる条件

- server がレプリカ起動経路 `start_replicas` に入り、2 個以上のレプリカを計画する必要があります。1 個のとき、または判定値が偽なら共有 arena を作らず、ログ行も出しません（`serve/server.py:9555-9569`、`serve/replicas.py:169-173`）。
- Linux では `--mmap-experts`、`--resident-experts`、`--shared-expert-arena`、`--resident-budget-gib` が共通引数またはいずれかのレプリカ引数に含まれる場合、共有可能な private expert arena がないものとして共有を使いません（`serve/replicas.py:181-187`）。
- Windows では named section のパスを計画します。Linux でも `os.memfd_create` が利用できない、または作成に失敗した場合は `/dev/shm` のファイル方式を試します。Linux 以外の OS（Windows を除く）では不適用の理由をログに出し、各レプリカを個別の expert コピーで起動します（`serve/replicas.py:174-224`）。
- Linux の memfd 方式は空き RAM が 8 GiB 未満なら共有なしで戻り、`/dev/shm` 方式には進みません。memfd が利用できない場合に限って `/dev/shm` ファイル方式を試し、こちらもディレクトリが存在して書き込み可能で、空きが 8 GiB 以上である必要があります。条件を満たさなければ共有なしで続行します（`serve/replicas.py:99-100, 190-224`）。
- `cfg["env"]` にこの名前を設定しても共有計画には反映されません。計画関数は `cfg["env"]` でなく server プロセスの `os.environ` を見ます。`cfg["env"]` は後でエンジン子プロセスの環境に加えられます（`serve/replicas.py:167-171`、`serve/server.py:4428-4441`）。

## 実行時の詳細

レプリカ起動時に `shared_arena_plan` が一度呼ばれ、server が選んだパスを各レプリカの引数末尾に `--shared-expert-arena` として追加します。環境値自体を保持する static cache はなく、計画時に `os.environ` を読みます。一方、server の通常起動では計画結果をその起動処理中に使うため、起動後に環境を変えても既に起動したエンジン群には反映されません（`serve/server.py:9567-9577`）。

Linux の memfd は server が作成して `/proc/<server pid>/fd/<n>` で渡します。memfd が利用可能で空き RAM が 8 GiB 未満なら計画を終了し、共有なしで続行します。memfd 自体が利用できないか作成に失敗した場合は `/dev/shm` ファイル方式を試します。Windows では server プロセス ID を含む named section 名を渡します（`serve/replicas.py:174-224`）。エンジンの arena 初期化に成功すると、共有状態ヘッダーを使い、1 エンジンが expert を読み、他は読み込み完了を待って読み込みを省きます。読み込み担当 PID が終了した場合は別のエンジンが読み直し、担当が生存したまま 45 分を超えて待つ場合は待機側も自身で読み込みを進めます（`src/core/expert_source.cpp:6269-6303`）。

もし arena 付きで一部エンジンだけ起動に失敗すれば、server は失敗したレプリカを同じ arena で再試行します。それでも失敗する場合は arena を除去し、全レプリカを個別コピーで起動し直します。arena なしでも失敗すれば `SystemExit` で起動を終えます（`serve/server.py:9592-9615`）。成功した場合は server 終了時に arena を閉じる／ファイルを削除するため `atexit` に登録します（`serve/server.py:9616-9621`）。

## ログと測定値

共有パスが計画されると `[strata] one shared expert arena ...` の行を server が stdout に出します。メモリ不足、対象外 OS、使えない `/dev/shm` など共有を計画できない場合は理由付きの `[strata] shared expert arena: ...` 行を出します。Windows と Linux memfd のいずれでも、定量的な起動性能値はこの環境変数の実装箇所にはありません（`serve/server.py:9567-9569`、`serve/replicas.py:174-224`）。

engine 側では共有 arena 初期化の失敗理由が arena のエラー情報になります。server が arena 付きの再起動にも失敗すると `[strata] replica <番号> did not start with the shared expert arena (...); starting every replica with its own copy of the experts instead` を表示します。エンジンの読み込み担当が途中で終了した場合は stderr に `strata generate: shared expert arena: engine ... died while reading it; reading it again`、待機側には `strata generate: shared expert arena: engine ... is reading the experts; waiting for it instead of reading them again` が出ます（`serve/server.py:9592-9615`、`src/core/expert_source.cpp:6287-6303`）。

## 根拠

- `serve/replicas.py:161-224` — 環境値の変換、設定優先、OS・引数・空き領域による計画分岐。
- `serve/server.py:9555-9621` — 計画結果のログ、エンジン引数への追加、再試行・共有なしへの fallback、後片付け。
- `strata_control/replica_profile.py:102-118` — レプリカプロファイルが共有設定を既定で真にする条件。
- `serve/server.py:4428-4441` — 子エンジン環境の生成と設定 `env` の適用。
- `src/core/expert_source.cpp:6269-6303` — エンジン間の読み込み担当選定、待機、担当交代。
- `src/core/pinned.cu:297-434` — Linux 共有ファイルの作成・ヘッダーと pack hash の検証・RAM 確保・`MAP_SHARED`。
