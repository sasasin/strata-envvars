# `STRATA_REPLICA_SHARED_ARENA`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数動作は対象外。

## 役割

Strata の `serve/server.py` が複数 replica engine を起動するとき、各 engine の expert arena を共有する backing object を使うか決めます。共有できれば expert の RAM copy を replica ごとに持たずに済むよう、サーバーが作った arena のパスを各 engine の `--shared-expert-arena` 引数に追加します。環境変数だけでは replica 起動は有効にならず、`--replicas N` または config の `replicas` で少なくとも二つの replica が選ばれている必要があります（`serve/server.py:9038-9041,9261-9275`）。

これは server 側の Python が読む環境変数です。Strata engine にこの環境変数の値を渡して解釈させる実装ではありません。engine へ渡るのは、条件が通った場合の `--shared-expert-arena <path>` 引数です（`serve/server.py:8700-8710`）。

## 値と判定

設定の `replica_shared_arena` が `None` または存在しない場合だけ、server は `environ.get("STRATA_REPLICA_SHARED_ARENA", "")` の文字列を `strip()` し、`lower()` した結果を完全一致で判定します（`serve/replicas.py:167-172`）。

| 環境変数値（前後空白除去・小文字化後） | 要求値 |
|---|---|
| `1`, `true`, `on`, `yes` | 有効要求 |
| 未設定、空文字、その他すべて（例: `0`, `false`, `2`, `y`, `enabled`） | 無効要求 |

部分一致や数値変換ではありません。大文字小文字は区別せず、前後の空白は無視します（例: ` TRUE ` は有効）。空文字は無効です。

設定 `replica_shared_arena` に `None` 以外の値がある場合、環境変数は参照されず、設定値そのものの Python truthiness が使われます。従って config の `false` は環境変数が `1` でも共有を止め、config の `true` は環境変数が `0` でも共有を要求します。文字列 `"false"` も truthy なので共有要求になります（`serve/replicas.py:169-172`）。

なお `STRATA_REPLICA_PROFILE` による自動 profile は、条件成立時に `cfg.setdefault("replica_shared_arena", True)` を行います。その場合はこの env var の値を読む分岐に入らず、明示 config 値がなければ `true` が優先されます（`strata_control/replica_profile.py:101-120`）。

## 有効になる条件

有効要求のうえで `n_replicas >= 2` のときだけ arena の選択を続けます。それ以外は黙って `(None, "")` を返し、この機能に関するログも出しません（`serve/replicas.py:172-173`）。通常の起動経路では `n_replicas` は `gpu_groups(cfg)` が返した replica group 数で、config の `replicas` または `--replicas N` から決まります（`serve/server.py:9038-9041,9261-9275`）。

- Windows では named section 用の `win:Local\\strata-replicas-<server pid>` を返します（`serve/replicas.py:174-178`）。
- Linux では `arch == "deepseek41"`、または全体・replica 個別の `args` に `--mmap-experts`、`--resident-experts`、`--shared-expert-arena`、`--resident-budget-gib` のいずれかがあれば共有を使わず、各 replica が個別 arena を使う旨を返します（`serve/replicas.py:181-187`）。
- Linux で memfd を使える場合、既定では memfd を試します。ただし config 値の文字列表現が大文字小文字を無視して `devshm` の場合は memfd を使わず `/dev/shm` 経路にします（`serve/replicas.py:188-190`）。利用可能 RAM が 8 GiB 未満なら各 replica 個別コピーに fallback するログを返します。memfd 作成が `OSError` で失敗した場合も `/dev/shm` 経路へ進みます（`serve/replicas.py:191-200`）。
- `/dev/shm` 経路では、指定ディレクトリ（通常 `/dev/shm`）が存在し書き込み可能で、空きが 8 GiB 以上である必要があります。不成立なら個別コピーへ fallback するメモを返します。成立時は stale arena を掃除して uid と server pid を含む `.bin` パスを選びます（`serve/replicas.py:215-224`）。
- Linux / Windows 以外は共有対象外で、個別コピーにするメモを返します（`serve/replicas.py:179-180`）。

`--replicas` は replica を起動する CLI ですが、共有 arena を直接 on/off する CLI option はこの処理にありません。Linux の config args にある上記の非互換 engine option は共有を無効にします（`serve/server.py:9038-9041`; `serve/replicas.py:181-187`）。

## 実行時の詳細

値は `start_replicas()` が replica 起動を組み立てるとき、`shared_arena_plan(cfg, n)` を一度呼ぶ中で評価されます。関数に `static` 等の cache はなく、各 server 起動（fallback による再起動も含む）で評価し直します。起動後に親プロセスの environment を変えても、すでに選んだ arena や起動済み child engines には反映されません（`serve/server.py:8700-8702,8715-8723,8743-8746`）。

arena path が得られると、server は各 replica の engine args に `--shared-expert-arena <path>` を追加して `StrataEngine` を起動します。env var 自体は `child_env()` が親環境からコピーするため子プロセスにも継承されますが、Strata の該当箇所では子 engine 向けにこの値を使わず、共有有無は server が決めた CLI 引数で伝えます（`serve/server.py:8704-8710,3747-3760`）。arena の選択メモが空でなければ `[strata] <メモ>` を stdout に出します（`serve/server.py:8701-8702`）。

共有 arena で replica 起動に失敗した場合、失敗 replica の一部だけが落ちていれば、server は再試行するログを出して同じ arena で再起動します。失敗が残れば arena を解放し、共有を `false` にした config で全 replica を再起動します。共有なしの再試行も失敗する場合は `[strata] replica <番号> did not start: <例外>` で `SystemExit` になります（`serve/server.py:8724-8747`）。起動成功後は server 終了時に arena を解放する `atexit` handler を登録します（`serve/server.py:8748-8753`）。

## 根拠

- 全参照の確認: 実装上の読み取りは `serve/replicas.py:171` の一箇所。候補名はモジュール説明・docstring、`serve/server.py` の `STRATA_REPLICA_START` 分岐、setup variant/recon 用文字列にも現れますが、これらは対象 env var の値を読む処理ではありません。テスト `serve/test_replicas.py:323-351` は unset / `0` / `1` と platform・model/args 条件を fixture で確認しています（調査ではテストを実行していません）。
- 候補一覧には `docs/envvars/000_envvers.md:1411` に掲載されています。実際の環境値読み取りは Strata 同梱 server の Python 実装で確認できました。
- 値取得・arena 条件: `serve/replicas.py:161-224`。
- profile が config default を補う箇所: `strata_control/replica_profile.py:101-120`。profile の適用入口: `setup.py:10348-10362`。
- replica 数決定・arena 引数の転送・ログ・失敗時 fallback: `serve/server.py:8688-8753,9038-9041,9261-9279`。
- 子 engine 環境の構築: `serve/server.py:3747-3760`。
