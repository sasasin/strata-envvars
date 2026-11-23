# `STRATA_OOMD_PACER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Python サーバーが Linux の systemd ユーザーマネージャー配下で engine を起動するとき、systemd-oomd の memory pressure に応じて engine を一時停止・再開する pacer を無効化する。`terminal/serve/oomd_pacer.py:95-114` の `applicable()` が `STRATA_OOMD_PACER` を判定し、`terminal/serve/server.py:835-836` から engine 起動直後に pacer を始める。環境変数を読むのはサーバープロセスであり、engine の C++ 側で読む箇所はない（候補名の全参照は同ファイル 98 行と `terminal/tests/terminal/test_oomd_pacer.py:67`）。

`0` 以外では、条件を満たす環境で engine のロード中に圧力が上がると、サーバーは engine プロセスへ `SIGSTOP` / `SIGCONT` を送り、ロード完了（READY）までの実行を調整する。生成処理や通常の engine CLI 動作を直接切り替える変数ではない（`terminal/serve/oomd_pacer.py:484-503,522-550`）。

## 値と判定

Python の `environ.get("STRATA_OOMD_PACER") == "0"` という完全一致判定であり、数値・真偽値への変換や空白除去はない（`terminal/serve/oomd_pacer.py:95-99`）。

| 条件 | unset | pacer 判定を通す値 | pacer を無効にする値 |
|---|---|---|---|
| 全実行環境 | 有効条件の検査へ進む | `""`、`"1"`、`"false"`、`"00"`、`"0anything"`、`" 0"` など、文字列が厳密に `"0"` でない値 | `"0"` のみ |

「判定を通す」は pacer の有効化そのものではなく、下記の Linux・cgroup・systemd-oomd 条件をさらに検査するという意味。CLI 引数による優先順位や上書きはなく、サーバーの環境変数を使う。

## 有効になる条件

- `sys.platform.startswith("linux")` であること。Linux 以外では `applicable()` は常に適用外を返す（`terminal/serve/oomd_pacer.py:95-100`）。
- サーバープロセスの cgroup v2 情報に `user@UID.service` が見つかること。その cgroup の `memory.pressure` が読み取れ、`some avg10=...` を解析できる必要がある（同 `:53-65,89-107`）。
- `systemctl is-active systemd-oomd` が成功し、対象 user manager の `ManagedOOMMemoryPressure` が `kill` であること。`ManagedOOMMemoryPressureLimit` は数値として読める必要があり、0 以下または未設定ならコード上の既定値 60% を使う（同 `:68-78,109-114`）。
- 上記条件を満たさない、または `STRATA_OOMD_PACER="0"` の場合、engine 起動後の `start()` はスレッドを作らず戻る。ロード完了前のこの pacer は Strata サーバー経由で起動した engine に限られる（同 `:574-593`、`terminal/serve/server.py:835-840`）。
- `STRATA_OOMD_PACER="0"` は user manager 条件で行う起動前の cache 解放にも影響する。`make_room()` は `applicable()` が適用外になると通常の user manager 経路では何もしない。一方、Linux コンテナと判定される場合は `in_container()` 経路に進めるため、この値だけではコンテナ用 cache 解放を止めない。`STRATA_OOMD_ROOM="0"` は cache 解放自体を止める（同 `:380-396`、`terminal/serve/server.py:823-829`）。
- `STRATA_OOMD_TRIM="0"` は pacer スレッド内のモデルファイル cache の段階的解放を止める。`STRATA_OOMD_PACER="0"` なら pacer 開始が先に見送られるため、この段階的解放も行われない（`terminal/serve/oomd_pacer.py:578-592`）。

## 実行時の詳細

読み取りは起動時の固定キャッシュではない。`applicable()` が呼ばれるたびに渡された mapping（通常は `os.environ`）を参照する。サーバーは engine 起動前の `make_room()`、engine 起動直後の `start()`、engine が `-9` で終了した場合の `killed_words()` からそれぞれ判定する（`terminal/serve/server.py:823-836`、`terminal/serve/server_parts/engines.py:317-328`、`terminal/serve/oomd_pacer.py:97-99,393,559,578`）。`start()` の判定後は環境変数を再確認せず、pressure の値を 0.5 秒間隔で読み、READY または engine 終了まで動く（同 `:41,484-498`）。

pacer は oomd の kill limit の 70% 以上で engine に停止信号を送り、プロセス状態が `T` になるか状態を取得できない場合は停止したものとして、pressure が limit の 30% 以下になるか、1 回の停止が 30 秒に達するまで待って再開する。状態を取得できるのに 2 秒以内に `T` にならない場合は直ちに再開する。停止時間の累計が 600 秒に達すると以後は停止せずロードを続ける（同 `:36-45,484-520,522-544`）。この機能はロード時だけで、READY 後は終了する。

## ログと測定値

この変数を `"0"` にしたこと自体を示すログはない。適用条件を満たして pacer が停止したときは、たとえば次の形式をサーバー出力に出す。

```text
[strata] memory guard: this desktop (systemd-oomd) ends a program when memory has been under strain for 20 s (now X %, its limit Y %). The engine waits a few seconds while memory settles (pause N).
```

ロード完了時は停止回数と累計秒数、累計 600 秒到達時は以後停止しない旨を出す（`terminal/serve/oomd_pacer.py:492-503,533-535`）。engine の終了コードが `-9` で、`applicable()` が有効な場合、サーバーの start error に systemd-oomd が終了させた可能性を示す文を追加する。`STRATA_OOMD_PACER="0"` のときは `applicable()` が無効になるため、この補足も付かない（同 `:555-564`）。

## 根拠

- 判定と適用条件: `terminal/serve/oomd_pacer.py:53-114`
- サーバーの起動前・起動後フック: `terminal/serve/server.py:823-840`
- pacer の閾値、停止・再開、ログ: `terminal/serve/oomd_pacer.py:36-45,484-550`
- cache 解放・trim との相互作用: `terminal/serve/oomd_pacer.py:380-441,574-592`
- SIGKILL の説明補足: `terminal/serve/oomd_pacer.py:555-564`、呼び出し元 `terminal/serve/server_parts/engines.py:317-328`
- `docs/DOCKER.md:332-348` はコンテナ用の起動前 cache 解放を記載するが、`STRATA_OOMD_PACER` の説明はない。コード上では同変数は pacer 判定に加えて user manager 経由の `make_room()` にも関係し、コンテナ経路では cache 解放を止めない。
