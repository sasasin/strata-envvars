# `HY4S_LOGSUM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4S_LOGSUM` は、同梱の Hy4-Flash SYCL runner `strata-hy4-sycl` の通常 greedy decode で、各 decode step の logits を GPU から host にコピーし、その全 byte から 16 桁の 16 進ハッシュを計算して stdout に出す診断用スイッチです。生成 token の選択や logits 自体を変更する設定ではありません。値を有効化しても、追加の logits コピーと待機が入るため実行時間には影響し得ます。読み取りと出力は `engine/src/hy4flash/sycl/sy_main.cpp` の decode loop にあります（同ファイル:527-560）。ビルドスクリプトは同ファイルを `strata-hy4-sycl` にコンパイルします（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6,62-68`）。

## 値と判定

C++ の `std::getenv("HY4S_LOGSUM")` の戻り値が null かどうかだけで判定します。文字列の parse・比較・数値変換はありません（`engine/src/hy4flash/sycl/sy_main.cpp:553`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL runner の通常 greedy decode が decode loop に到達 | 設定なしなので出力しない | 空文字、`0`、`1`、`false`、その他どの文字列でも、環境変数が存在すれば有効 | unset のみ |

空文字も `getenv` が非 null を返すため有効です。`0` や `false` を特別扱いせず、大文字小文字、空白、数値としての妥当性、文字列全体も検査しません。既定値は unset 相当（ハッシュ出力なし）です。CLI 引数や他の環境変数による上書き・優先順位はありません。

## 有効になる条件

- `engine/src/hy4flash/sycl/build_hy4_sycl.sh` が作る SYCL runner に含まれるコードです。ソースは Linux 向け Intel Arc SYCL runner と記述され、`fat` / `bmg` / `acm` の各 build mode で同じ `sy_main.cpp` をコンパイルします。この変数の判定に build macro による分岐はありません（`engine/src/hy4flash/sycl/sy_main.cpp:1,553`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-40,62-68`）。
- `--serve` は `hy4s_serve_main` に移り `main` から戻るため、この runner の decode loop に入りません（`engine/src/hy4flash/sycl/sy_main.cpp:215-249`）。
- 非 server 実行で `--gen` が正数であり、通常 greedy decode の `else if (gen > 0)` に入る必要があります。`--draft dfly2` で `spec_mode` が成立する場合は別分岐が先に実行され、この hash 出力箇所を通りません（`engine/src/hy4flash/sycl/sy_main.cpp:250-253,276-280,379-409,527-560`）。
- `--load-only` は prefill 前に終了します。また prefill 中には読み取られず、通常 decode の各 step で初めて判定されます（`engine/src/hy4flash/sycl/sy_main.cpp:319-320,527-560`）。モデル、token 入力、GPU/SYCL 実行の初期化が成功し、decode step が進むことも必要です。

## 実行時の詳細

この変数は decode loop の各 step で `std::getenv` により読み直され、値を保持する static cache はありません。プロセス起動時に shell が渡した環境は、そのプロセス実行中は通常固定です。コード中に `HY4S_LOGSUM` の設定・転送や子プロセス起動はありません（`engine/src/hy4flash/sycl/sy_main.cpp:527-560`）。

各 step では先に `r.head`、`argmax_row`、argmax の device-to-host copy と `wait()` を行って次 token を取得します。その後、変数が設定されていれば logits 全行を別の `std::vector<float>` に device-to-host copy して再度 `wait()` し、`V * 4` byte を順にハッシュします。ハッシュ状態の初期値は `1469598103934665603`、各 byte `b` に対する更新は `(hash ^ b) * 1099511628211` です。`printf` は `H <step-index> <16桁小文字hex>` を出力します。step index は loop の `s`（0 始まり）です（同ファイル:538-560）。

この分岐は `next = nx` より前にありますが、hash 用のコピー先は別ベクトルで、`nx` は既に読み出し済みです。hash 結果を token selection、状態、終了条件へ戻す処理はありません。decode の `forward_chunk` が失敗した場合は `stderr` に `forward: <error>` を出し status 1 で戻るため、その失敗した step の hash 出力には到達しません（同ファイル:543-560）。

## ログと測定値

有効時、通常 greedy decode の各 step について stdout に `H %d %016llx\n` 形式の行を出力します。無効時はこの行を出しません。ソース中のコメントはこのハッシュを run-to-run の determinism 比較に使う意図を示しますが、文書・コードに測定値や正確性保証は記載されていません（`engine/src/hy4flash/sycl/sy_main.cpp:553-560`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:1-12` — runner の識別と SYCL 実装。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-249,276-280,379-409,527-560` — server/speculative/greedy 経路と読み取り、hash 出力。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-40,62-68` — SYCL build mode と runner へのコンパイル。
