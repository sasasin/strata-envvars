# `STRATA_REPLICA_START`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の serving サーバーが複数 replica engine を起動するとき、起動処理を順番に行うか、スレッドを使って並行して行うかを選ぶ。`terminal/serve/server.py` の `start_replicas` が環境から直接値を読み、完全一致する値 `serial` のときだけ順次起動する。それ以外は replica ごとのスレッドを起動して全て join する（`terminal/serve/server.py:8829-8865`）。

これはレプリカ数や GPU 割当てを設定する変数ではない。レプリカ構成は別途 config の `replicas` または `--replicas` から作られ、少なくとも 2 グループがあるとき `start_replicas` に入る（`terminal/serve/server.py:9230-9233, 9314-9315, 9460-9475`; `terminal/serve/replicas.py:55-84`）。

## 値と判定

Python の `os.environ.get("STRATA_REPLICA_START", "") == "serial"` で環境値全体を文字列比較する。未設定時の既定値は `""` であり、未設定と空文字はいずれも順次起動を選ばない。大文字小文字を区別し、空白除去・数値変換・真偽値変換はしない（`terminal/serve/server.py:8857-8865`）。

| ビルド・起動条件 | unset | 設定時に順次起動となる値 | 設定時に順次起動とならない値 |
|---|---|---|---|
| serving の Strata engine 経路で複数 replica を構成 | `""` 相当。replica 起動スレッドを使う | `serial`（完全一致） | 空文字、`SERIAL`、`Serial`、` serial`、`serial `、`1`、`0`、`true`、`false`、その他すべて |

## 有効になる条件

- サーバーが `--engine strata` で起動し、config が必要であり（`terminal/serve/server.py:9386-9394`）、`rp.gpu_groups(cfg)` が 2 つ以上のグループを返す必要がある。`replicas` が未設定または `false`、数値 1 以下、あるいは指定グループが 1 個なら `start_replicas` に進まず、この変数は起動順に影響しない（`terminal/serve/replicas.py:55-84`; `terminal/serve/server.py:9460-9477`）。
- ソース上、この環境値判定に OS・GPU backend・ビルド macro の追加条件はない。CPU affinity の利用可否などは個別 engine の起動条件だが、この変数の分岐条件ではない（`terminal/serve/server.py:8857-8865`; `terminal/serve/replicas.py:270-280`）。
- `--lazy` または `lazy_load: true` の場合、各 `StrataEngine` の初期化は `lazy` を受けてプロセスを開始せずに戻る。そのため `serial` が順番にするのは初期化呼び出しであり、後で lazy engine が実際に起動する順序をこの分岐が直列化するわけではない（`terminal/serve/server.py:798-800, 8850-8865, 9399`）。
- 各子 engine の環境は `child_env` が親の `os.environ` をコピーして作り、replica config の `env` を後から反映する。このため変数は通常子プロセスにも引き継がれるが、replica config の `env` に同じキーがあればその値で上書きされる。調査した checkout では、この名前を読む Strata 所有コードはサーバーの上記箇所だけで、engine 側の読み取りは見つからなかった（`terminal/serve/server.py:4007-4028, 8850-8852`; `terminal/serve/replicas.py:252-267`）。

## 実行時の詳細

判定は `start_replicas` を呼ぶたびに一度行われ、関数内で cache されない。`serial` の場合は replica index の昇順で `one(i)` を呼び、通常の非 lazy 起動では `StrataEngine` の初期化が子 engine の `READY` を待って戻るため、次の replica の開始呼び出しはその後になる（`terminal/serve/server.py:843-860, 8845-8865`）。各起動で例外が起きても `one` はそれを記録して戻るので、残りの replica も順に試し、全起動処理後に共有 arena の再試行または失敗処理を行う（`terminal/serve/server.py:8845-8854, 8866-8889`）。

値が `serial` 以外なら、全 replica 用スレッドを作成して開始し、その全てを join する（`terminal/serve/server.py:8860-8865`）。環境変数をサーバー稼働中に変更しても、すでに実行済みの判定やその起動には反映されない。通常の後続 engine restart は保存済み spawn 引数を使い `start_replicas` を再度通らないため、この値を再読しない（`terminal/serve/server.py:767, 1206-1222`）。ただし共有 arena を使った起動失敗時に arena 無しへ切り替えて `start_replicas` 自体を再帰呼び出しする経路では、再度判定される（`terminal/serve/server.py:8885-8889`）。

## ログと測定値

この変数の値や順次起動の選択を示す専用ログはない。replica 起動時の共通表示は `[strata] {n} replicas on the cards ...: requests go to the least busy one, a conversation back to its own` で、serial / 並行のどちらでも同じである（`terminal/serve/server.py:8835-8838`）。起動失敗時は arena 条件に応じて再試行案内を出すか、`[strata] replica {i} did not start: {e}` で終了するが、これは起動結果によるもので変数専用の失敗経路ではない（`terminal/serve/server.py:8866-8889`）。この変数による性能測定値は該当資料に見当たらない。

## 根拠

- `terminal/serve/server.py:8829-8865` — replica 起動関数、環境値の判定、順次起動とスレッド起動。
- `terminal/serve/server.py:4007-4028` — 子 engine 環境の複製と config 環境値の反映。
- `terminal/serve/server.py:767, 798-800, 843-860, 1206-1222` — spawn 設定、lazy 初期化、READY 待ち、後続 restart。
- `terminal/serve/server.py:9230-9233, 9314-9315, 9386-9400, 9460-9477` — CLI/config とサーバーモードから replica 起動に至る条件。
- `terminal/serve/replicas.py:55-84, 252-267, 270-280` — replica group の条件、replica config、CPU affinity の条件。
