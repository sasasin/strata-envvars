# `SPLIT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`SPLIT` は通常の Strata CLI やサーバーが読む設定ではなく、同梱の研究用ライブプローブ `research/tools/live-probes-2026-10/batch_groups_cache_test.py` が読む環境変数である。`GPUS` が空でない場合にのみ読み、値をプローブの `cfg["layer_split"]` に設定する。その後 `serve.server.engine_args()` が複数 GPU のレイヤー分割を `--layer-split` に変換できた場合、プローブが起動する Strata engine にその CLI 指定を渡す。`child_env()` は `os.environ` をコピーするため `SPLIT` 自体も子プロセス環境に残るが、調査した engine ソースには `SPLIT` の読み取りがない。したがって、この名前で Strata の一般利用者向け動作を直接制御するものではない（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-33`、`serve/server.py:3953-3954`, `4428-4432`）。

## 値と判定

プローブは Python の `os.environ.get("SPLIT", "auto")` で文字列として一度読み取る。値の parse はプローブ内では行わず、`engine_args()` が呼ぶ `layer_split_value()` が検証・正規化する（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-31`、`serve/server.py:3755-3785`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `GPUS` が空でない。複数 GPU 構成で `engine_args()` が layer split を付ける場合 | `"auto"` | `"auto"`（前後空白を除き、大文字小文字を無視）、または昇順の開始 layer 番号（例 `"24"`、`"24,36,42"`）。整数列は空白を除いて 10 進整数へ変換され、`"24, 36"` のような空白も許される | 空文字は無効値ではなく `"auto"` と同じ。`"true"`、`"0"`、`"1"`、負数、数値でない要素、空要素、重複・降順の列はエラー。先頭番号は 2 以上。GPU が複数なら番号数は GPU 数より 1 少なくなければならない |
| `GPUS` が未設定または空文字 | 読み取り・適用されない | なし | `SPLIT` の値は参照されない |

文字列全体（空白を除去した後）を `auto` と比較し、それ以外はカンマ区切りの整数として全要素を変換する。`"0anything"` のような数値の後続文字を許容する変換ではない。`layer_split_value()` は文字列の `auto` の前後空白と大小文字を正規化するが、数値要素は `int()` で変換する（`serve/server.py:3760-3785`）。

既定値 `auto` はプローブ内の既定値であり、Strata CLI の既定値ではない。プローブの `cfg["args"]` に既に `--layer-split` が含まれると `engine_args()` は `SPLIT` 由来の値を追加しない。さらにプローブは `STRATA_EXTRA_ARGS` をその後ろに追加するため、そこに `--layer-split` があれば CLI の後続指定になる（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:30-33`、`serve/server.py:3953-3954`）。

## 有効になる条件

- プローブで `GPUS` が空でないこと。`GPUS` は環境変数の設定有無ではなく空文字でないかで分岐し、カンマ区切りを `int()` で `cfg["gpu"]` に変換する（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-30`）。
- 設定された GPU が複数で、`cfg["args"]` に `--peer-device` がなく、かつ `--layer-split` が既存引数に含まれていないこと。そうでなければこの値から `--layer-split` は追加されない（`serve/server.py:3800-3803`, `3953-3954`）。
- engine 側で `--layer-split` を有効にするには `--serve` が必要。明示値は選択 GPU 数と開始 layer 数が合い、GPU ごとに異なる有効な device が割り当てられる必要がある。`auto` は可視 GPU 数や空きメモリなどの engine 側の条件でも分割先が決まり、可視 GPU が 1 枚なら分割を解除する（`src/program/generate.cpp:4507-4512`, `4540-4556`）。
- モデルがロードされる engine の起動経路で適用される。プローブは `engine_args(cfg)` の結果を `StrataEngine` に渡す。`child_env()` は現在の `os.environ` をコピーして子プロセス環境を作るため `SPLIT` も継承されるが、engine の layer split は CLI 引数で指定される（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:30-33`、`serve/server.py:4428-4432`）。

## 実行時の詳細

値はプローブのモジュール初期化時、`GPUS` 分岐内で一度読み取られる。キャッシュ用の共有 helper はなく、起動後に環境を変更しても既に `cfg` と生成済みの engine 引数には反映されない（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:21-33`）。

未設定時または空文字時は `auto` となる。明示値は `layer_split_value()` で GPU 台数に応じた形式検証の後、engine 引数 `--layer-split <値>` になる。`cfg["args"]` に `--layer-split` が先にあれば環境値は読まれて設定されても引数生成には使われない。`STRATA_EXTRA_ARGS` の同オプションは生成済み引数の後ろに連結される。子プロセス環境にも `SPLIT` は継承されるが、engine 側ではこの名前を読まず、layer split は CLI 引数から処理する（`research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-33`、`serve/server.py:3755-3785`, `3953-3954`, `4428-4432`、`src/program/generate.cpp:3881`）。

`auto` では engine がレイヤーの分割点を選ぶ。明示値は各後続 GPU に割り当てる最初の layer 番号として扱われる。layer split が成立すると engine は選択 GPU 数と分割値を stderr に `strata generate: layer split across ...` と出す。`--layer-split` の値が engine 側で不正、または `--serve` がない場合は説明を stderr に出し終了コード 2 で戻る（`src/program/generate.cpp:4507-4517`, `4552-4556`, `4673-4676`）。この engine 側の診断は CLI に渡った値へのものであり、プローブ内の `layer_split_value()` が拒否した値では Python の `ValueError` が先に発生する（`serve/server.py:3766-3784`）。

## 根拠

- `research/tools/live-probes-2026-10/batch_groups_cache_test.py:28-33` — `GPUS` 条件、`SPLIT` の読み取り、設定への格納、engine 引数生成と起動。
- `serve/server.py:3755-3785` — `layer_split` の既定値、文字列変換、数値・昇順・台数検証。
- `serve/server.py:3800-3803`, `3882-3888`, `3953-3954` — split の適用条件と CLI 引数への追加。
- `src/program/generate.cpp:3881`, `4507-4517`, `4540-4556`, `4673-4676` — CLI 値の読み取り、engine 側条件・エラーと開始時ログ。
