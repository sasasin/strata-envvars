# `HY4S_GRAPH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4S_GRAPH` は、Hy4-Flash の SYCL runner が SYCL `command_graph` を使うかどうかを制御する。SYCL command graph API がコンパイル時に利用でき、選択中の device が graph aspect を持つ場合、環境変数が無効化条件に当たらなければ `Runner::graph_enabled` を true にする。これは graph capture/replay を使う経路を許可する設定であり、通常の計算内容や token 選択を直接変更する値ではない。`engine/src/hy4flash/sycl/sy_graph.h:621-631`、実際の trunk 経路の条件は `engine/src/hy4flash/sycl/sy_graph.h:1382-1392`。

この環境変数を読むのは `sy_graph.h` の `Runner::init` だけで、`rg` によるリポジトリ全体の完全一致検索ではこの読み取り以外にコメント 1 箇所が見つかった。helper 経由や動的な名前の読み取り箇所はない。`sy_main.cpp` の通常実行と `sy_serve.h` の server 実行はいずれも同じ `Runner` を生成するため、この設定判定を共有する（`engine/src/hy4flash/sycl/sy_main.cpp:283-295`、`engine/src/hy4flash/sycl/sy_serve.h:262-270`）。

## 値と判定

`std::getenv("HY4S_GRAPH")` の結果を文字列として parse せず、設定値が存在し、かつ先頭文字が文字 `'0'` のときだけ graph を無効化する。先頭文字以降や値全体の妥当性は検査しない（`engine/src/hy4flash/sycl/sy_graph.h:624-626`）。

| 条件（build など） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `HY4S_HAS_GRAPH` が 1 で device が graph aspect 対応 | 有効 | 空文字、`1`、`true`、`false`、` 0` など先頭が `'0'` でない値 | `0`、`0anything`、`00` など先頭が `'0'` の値 |
| `HY4S_HAS_GRAPH` が 1 で device に graph aspect がない | 無効 | なし（環境変数では capability を覆せない） | 無効のまま |
| `HY4S_HAS_GRAPH` が 0 | 無効 | なし。環境変数を読むコード自体がコンパイル対象外 | 無効のまま |

未設定は無効化条件に当たらないため、device capability があれば有効。明示的な空文字も `getenv` は非 null を返すが `eg[0]` は終端文字なので無効化されず、有効になる。`false` や `0anything` を含む通常の意味での真偽値 parse は行わず、大小文字・数値形式・空白も検証しない。` 0` は先頭が空白なので無効化されない。`engine/src/hy4flash/sycl/sy_graph.h:624-626`。

## 有効になる条件

- `sy_common.h` が `<sycl/ext/oneapi/experimental/graph.hpp>` を include できること。ヘッダーの有無で `HY4S_HAS_GRAPH` を 1 または 0 に定義する（`engine/src/hy4flash/sycl/sy_common.h:9-14`）。
- `HY4S_HAS_GRAPH` が 1 の場合、選択 device が `ext_oneapi_limited_graph` または `ext_oneapi_graph` aspect のいずれかを持つこと（`engine/src/hy4flash/sycl/sy_common.h:198-217`）。
- `HY4S_GRAPH` が unset、空、または先頭文字が `'0'` 以外であること（`engine/src/hy4flash/sycl/sy_graph.h:624-626`）。SYCL backend/device の選択は別の設定や runtime によるが、この変数自体は backend を選ばない。
- trunk の graph forward は `T <= 8` で、dump/tap/prof/prof2/hash/vision/force-route の各診断・特殊経路が使われていない場合に限り graph を試す。それ以外は eager queue 経路を通る（`engine/src/hy4flash/sycl/sy_graph.h:1382-1395`）。
- DFly2 の graph capture も `r.graph_enabled` を共有し、`prof2`、dump、tap が無効な場合に試す（`engine/src/hy4flash/sycl/sy_dfly2.h:703-706`、`928-931`）。
- `--serve` を含む server 経路も同じ `Runner::init` を使う。`--info` など `Runner` を作らない実行経路では、この判定は実行されない（Runner 生成: `engine/src/hy4flash/sycl/sy_main.cpp:283-295`、`engine/src/hy4flash/sycl/sy_serve.h:262-270`）。CLI 引数や別環境変数による `HY4S_GRAPH` の上書きは該当コードにない。

## 実行時の詳細

値を読むのは `Runner::init` の allocation・fusion 構築後で、初期化成功前に graph capability と環境値を評価する（`engine/src/hy4flash/sycl/sy_graph.h:617-632`）。`dev_caps()` の device capability は関数内 `static` で初回に cache される（`engine/src/hy4flash/sycl/sy_common.h:198-217`）。環境値自体は `getenv` の一度の評価結果から `graph_enabled` に保存され、以後は同フィールドを分岐に使うため、runner 初期化後の環境変更は反映されない。

graph が許可された場合、trunk の forward は chunk が 8 以下で特殊経路でないとき `get_or_build_graph` を呼び、graph set を作成・cache して replay する。cache は最大 16 graph set で、上限到達時に queue を待って cache を clear する（`engine/src/hy4flash/sycl/sy_graph.h:1246-1278`、`1267-1271`、`1337-1378`）。capture が `sycl::exception` で失敗すると `graph_enabled` を false にし、eager queue に戻る（`engine/src/hy4flash/sycl/sy_graph.h:1330-1334`、`1386-1392`）。head graph capture が失敗した場合も graph を無効化して eager head 計算へ続くが、この catch 自体はログを出さない（`engine/src/hy4flash/sycl/sy_graph.h:1438-1470`）。

## ログと測定値

Runner 初期化時に stderr の `[runner] ... graph=%d ...` が `graph_enabled` の 0/1 を表示する。GPU capability の行には別途 `graph=%d` があり、これは device の graph capability を示す（`engine/src/hy4flash/sycl/sy_graph.h:629-631`、`engine/src/hy4flash/sycl/sy_main.cpp:255-259`）。decode 完了時の `[decode] ... graph replays %llu captures %llu` は実際の replay/capture 回数を示す（`engine/src/hy4flash/sycl/sy_main.cpp:582-585`）。

trunk の capture 失敗では `[graph] capture failed (%s), falling back to eager queue`、DFly2 の capture 失敗では `[dfly2-graph] capture failed (%s), eager fallback` を stderr に出す（`engine/src/hy4flash/sycl/sy_graph.h:1330-1333`、`engine/src/hy4flash/sycl/sy_dfly2.h:732-735`、`957-960`）。上記 head capture の例外はログなしで無効化する。通常の eager fallback は runner の処理を続ける。SYCL の例外がこの capture fallback で捕捉されず main の外側まで伝播した場合は `SYCL exception: %s` を出して終了コード 4 となる（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。この環境変数による速度や正確性の測定値は、対象資料から確認できなかった。

## 根拠

- `engine/src/hy4flash/sycl/sy_graph.h:621-631` — 環境変数の読み取り、判定と runner 起動ログ。
- `engine/src/hy4flash/sycl/sy_common.h:9-14,198-217` — compile-time header gate と device capability。
- `engine/src/hy4flash/sycl/sy_graph.h:1246-1278,1330-1392,1438-1470` — graph cache、capture fallback、forward/head の適用条件。
- `engine/src/hy4flash/sycl/sy_dfly2.h:703-735,928-960` — DFly2 graph と fallback。
- `engine/src/hy4flash/sycl/sy_main.cpp:255-259,283-295,582-585,612-615`、`engine/src/hy4flash/sycl/sy_serve.h:262-270` — 通常/server の runner 生成、観測ログ、未捕捉 SYCL 例外。
