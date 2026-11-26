# `STRATA_PARALLEL_SOLO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Terminal の serve が `--batch` / `--parallel` で動作中、スロットでデコードしているリクエストが一つだけになったとき、そのリクエストをバッチスロットから通常の solo `GEN` 経路へ戻す動作を抑止するスイッチ。値が厳密に `0` のときだけ抑止し、それ以外はサーバー側の条件を満たせば戻す。スロット内デコードの制御箇所は `Engine._may_go_solo` である（`terminal/serve/server.py:1942-1955`）。

この変数は通常の solo リクエストの経路を止めるものではない。`generate()` は engine が batch slot を報告しているときだけ `generate_batched()` を使い、この変数はその中でスロットデコードから solo に戻すかの判定にだけ使われる（`terminal/serve/server.py:2625-2636, 2368-2371`）。

## 値と判定

サーバープロセスの `os.environ.get("STRATA_PARALLEL_SOLO") == "0"` という文字列全体の比較である。数値変換、真偽値変換、trim はしない。未設定 (`None`)・空文字・`0anything`・`00`・`1`・`true`・`false`・空白付きの値はいずれも `"0"` と一致せず、抑止スイッチは作動しない（`terminal/serve/server.py:1949-1950`）。

| 条件 | 値 | 判定 |
|---|---|---|
| `STRATA_PARALLEL_SOLO` 未設定 | `None` | solo へ戻る機能を値だけでは抑止しない |
| 文字列が厳密に `0` | `0` | solo への復帰を抑止し、スロットに残す |
| 空文字またはその他の設定値 | `""`, `00`, `0anything`, `1`, `true`, `false`, ` 0` など | solo へ戻る機能を値だけでは抑止しない |

## 有効になる条件

- リクエストが Terminal serve の batch 経路を通ること。`self.batch` が truthy の場合に `generate_batched()` が呼ばれる（`terminal/serve/server.py:2629-2635`）。
- Engine の `INFO` に `slot_cache` が truthy であること。通常の `engine/src/program/generate.cpp` は batch 有効時に `--prompt-cache` 相当の `o.prompt_cache > 0` なら `slot_cache=1` を通知する。sfnx は `a.batch > 1`、qwen35 は `E.n_sess > 1` の場合に通知する（`engine/src/program/generate.cpp:16224-16227`; `engine/src/split/tools/sfnx.cpp:1155-1157`; `engine/src/qwen35/q36_engine.cu:5281-5285`）。従って一般 engine で prompt cache が無効（例: `--prompt-cache 0`）なら、この判定は行われない。
- 埋め込みリクエストではないこと、残りの `max_new` が 32 以上であること、同じリクエストがすでに solo に戻った回数が 2 未満であること（`terminal/serve/server.py:1942-1950`）。
- その時点で busy な slot がちょうど 1 個で、待機リクエストが 0 件であること（`terminal/serve/server.py:1954-1955`）。
- `INFO slot_read=1` かつ `STRATA_SLOT_READ` が厳密に `0` ではなく、さらに複数会話が sticky 期間内に動いている場合は、会話をその slot に留める判定が優先され、この変数の値にかかわらず solo へ戻らない。複数会話判定は `STRATA_PARALLEL_STICKY_S` が正のときだけ行われ、sticky 期間内に busy または使用済みの slot が 2 個以上あるかを調べる（`terminal/serve/server.py:1952-1955, 1966-1979`）。

## 実行時の詳細

slot の `BT` トークンを受け取り、応答へ token を yield した直後に `_may_go_solo()` が判定される。`STRATA_PARALLEL_SOLO` が `"0"` なら `False` が返り、`BSTOP <slot>` は送られず、そのリクエストは slot の `BT` / `BDONE` 経路を続ける（`terminal/serve/server.py:2367-2372, 1945-1955`）。

値が `"0"` でなく他の条件も満たす場合、サーバーは engine に `BSTOP <slot>` を送り、slot が `BDONE ... cancel` を返した後、元の prompt と既生成 token をつないで solo `GEN` を開始する。コード上、この復帰は一リクエストにつき最大 2 回で、残り token 数が 32 未満になると以降は復帰しない（`terminal/serve/server.py:1942-1950, 2368-2400`）。一般 engine は `BSTOP` を受けると指定 slot を stop 対象にする（`engine/src/program/generate.cpp:18437-18442`）。

環境変数はクラス属性や起動時設定に cache されず、`_may_go_solo()` が呼ばれるたびに `os.environ.get` で読み直される。したがってサーバープロセス内で `os.environ` の値が変われば次の判定から反映される。親プロセス側で起動後に環境を変更しても、既に動作中の子プロセスの環境は変わらない。ほかの条件で判定が先に `False` になる場合は、この値を読む比較まで到達しない（`terminal/serve/server.py:1945-1955, 2368-2370`）。

## ログと測定値

この変数専用のログ、警告、終了コード、失敗経路はない。値 `"0"` のときは solo 復帰を抑止するだけで、slot の既存エラー処理は変えない（`terminal/serve/server.py:2368-2401`）。性能測定値は記載しない。

## 根拠

- `terminal/serve/server.py:1942-1955` — 復帰の上限・残り token 閾値・値比較・slot 状態条件。
- `terminal/serve/server.py:2367-2400` — slot デコード中の判定、`BSTOP`、solo 再開。
- `terminal/serve/server.py:2625-2636` — batch 経路への振り分け。
- `engine/src/program/generate.cpp:16224-16227` — 一般 engine の `slot_cache` 通知条件。
- `engine/src/split/tools/sfnx.cpp:1155-1157`、`engine/src/qwen35/q36_engine.cu:5281-5285` — 他 engine の `slot_cache` 通知条件。
- `terminal/serve/server.py:1966-1979` — `STRATA_PARALLEL_STICKY_S` と複数会話判定。

