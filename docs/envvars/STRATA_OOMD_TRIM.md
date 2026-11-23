# `STRATA_OOMD_TRIM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Linux サーバーがモデル用 engine を起動した後、systemd-oomd のメモリ圧力を監視する pacer が適用される場合に、engine が読み込むモデルファイルのページキャッシュをロード中に返すかを選びます。既定では返却対象を作り、値が文字列 `0` のときだけ対象を空にします。読み取りは `serve/oomd_pacer.py` の `start()` にあり、生成中の推論や token 選択はこの変数で変更されません。`terminal/serve/oomd_pacer.py:574-594`。

## 値と判定

値を数値や真偽値に変換せず、`os.environ.get(...) != "0"` の文字列完全一致で判定します。大文字小文字・空白の正規化もありません。

| 条件 | unset | trim 対象を作る値 | trim 対象を作らない値 |
|---|---|---|---|
| `start()` が適用される場合 | 有効（`None != "0"`） | `""`、`"00"`、`"1"`、`"true"`、`"false"`、`" 0 "` など、文字列 `"0"` 以外のすべて | `"0"` のみ |

この判定は engine ごとの `start()` 呼び出し時に一度行われます。起動後に `os.environ` を変更しても、その pacer が保持した対象リストには反映されず、次の engine 起動時に読み直されます。`terminal/serve/oomd_pacer.py:589-592`。

## 有効になる条件

- `server.py` が lazy 起動で早期 return せず engine を実際に起動し、起動した process に対して `oomd_pacer.start()` を呼ぶこと。`terminal/serve/server.py:792-794, 823-836`。
- `start()` 内の `applicable()` が有効な監視条件を見つけること。Linux であり、`STRATA_OOMD_PACER` が文字列 `"0"` でなく、`user@UID.service` 配下の cgroup と `memory.pressure` が読め、`systemd-oomd` が active で、manager の `ManagedOOMMemoryPressure` が `kill` かつ kill limit を取得できる必要があります。条件を満たさなければ `start()` は `None` を返し、この変数による trim は行われません。`terminal/serve/oomd_pacer.py:95-114, 574-580`。
- 実際に trim するには、engine 引数に `--native` と絶対パスがあり、その GGUF ファイル（および存在する split shard）が対象として見つかる必要があります。`--no-ple`、`--ple-io direct`、または PLE テーブルを含まないモデルでは PLE テーブル除外は発生しません。対象を空にした場合、pacer の trim callback 自体が設定されません。`terminal/serve/oomd_pacer.py:143-177, 296-318, 567-571, 589-591`。
- `STRATA_OOMD_PACER=0` は pacer 全体を止めるため、`STRATA_OOMD_TRIM` が unset や `1` でも trim は行われません。`STRATA_OOMD_ROOM=0` は engine 起動前の `make_room()` を止める別設定であり、起動後の本変数による trim を直接無効化しません。`terminal/serve/oomd_pacer.py:98-99, 380-396, 574-591`; `terminal/serve/server.py:823-836`。
- コンテナ内では `make_room()` にコンテナ向け経路がありますが、ロード中の trim は `start()` の `applicable()` が必要です。user manager の cgroup を見つけられないなどで `applicable()` が `None` なら、この変数だけでは trim 経路を有効にしません。`terminal/serve/oomd_pacer.py:95-114, 353-357, 574-580`。

## 実行時の詳細

engine 起動後、`start()` は `applicable()` が返した manager の pressure ファイルを読む daemon thread を作ります。`STRATA_OOMD_TRIM` が `"0"` 以外なら、`trim_files(args)` が `--native` の既存 GGUF shard を列挙し、PLE テーブルを engine が後で再利用する条件ではその shard を除外します。`terminal/serve/oomd_pacer.py:567-594`。

thread は READY（`loading` event）になるまで pressure をポーリングし、pressure が oomd kill limit の 30% 以上で、直近 trim から 1 秒以上経っていれば、対象ファイルごとに `_drop_cache()` を呼びます。したがって trim は条件が続く間おおむね毎秒繰り返され、READY 後は停止します。`_drop_cache()` はファイルを読み取り専用で開いて `os.posix_fadvise(fd, 0, 0, _DONTNEED)` を呼びます。ファイルを開けない、または API 呼び出しに失敗した場合は `False` を返します。`terminal/serve/oomd_pacer.py:328-339, 453-483, 484-500`。

trim callback の例外は `_maybe_trim()` 内で握りつぶされます。また `start()` 自体も例外を捕捉して `None` を返すため、trim の不成立を理由に engine 起動を失敗させる経路ではありません。環境変数は server プロセスの `os.environ` から読まれます。engine の起動時には別引数の `env` を `Popen` に渡しますが、この変数を特別に加工する処理はありません。`terminal/serve/oomd_pacer.py:574-595`; `terminal/serve/server.py:827-836`。

## ログと測定値

対象リストがあり、pressure 条件に達して callback が例外なく戻ると、初回に限り server の出力へ次の行を出します（`say` の既定は `print(..., flush=True)` です）。個々の `_drop_cache()` が `False` を返しても戻り値は検査されないため、このログは全対象のキャッシュ返却成功を確認するものではありません。

`[strata] memory guard: memory is tight, so the memory that holds copies of the model's file is given back as it loads (this does not slow the load)`

変数が `"0"`、対象ファイルがない、pressure が閾値未満、pressure を読めない、または READY 済みの場合、この trim のログは出ません。ソースコメントには特定環境の測定記録がありますが、この文書では一般的な性能効果として扱いません。`terminal/serve/oomd_pacer.py:469-482, 584-592`。

## 根拠

- 候補名の実読み取りと値判定、対象リスト・callback: `terminal/serve/oomd_pacer.py:589-592`。
- trim 対象と PLE の除外条件: `terminal/serve/oomd_pacer.py:143-177, 296-318, 567-571`。
- pressure 適用条件、閾値、間隔、ログ: `terminal/serve/oomd_pacer.py:95-114, 453-483, 484-500`。
- キャッシュ返却 API と失敗時の扱い: `terminal/serve/oomd_pacer.py:328-339, 574-595`。
- server の engine 起動前後の呼び出し: `terminal/serve/server.py:823-836`。
