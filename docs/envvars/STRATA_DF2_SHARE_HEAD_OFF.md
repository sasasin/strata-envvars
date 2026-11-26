# `STRATA_DF2_SHARE_HEAD_OFF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP と DFlash2 が同じドラフト語彙の出力 head 行を使える場合に、DFlash2 が MTP の GPU 上の行バッファを共有する最適化を止めます。無効（変数が未設定）なら、DFlash2 は条件が合うと MTP の行バッファを再利用し、設定されていれば DFlash2 用に別の head 行コピーを作ります。これは head の格納・VRAM 見積もりに関する切替で、DFlash2 の選択する語彙や生成ロジックを変える処理はありません。実装は `Dflash2Drafter::bind` と `generate.cpp` の共有 head 提供・VRAM 見積もりです（`engine/src/core/dflash2.cpp:371-412`, `engine/src/program/generate.cpp:8404-8432`）。

## 値と判定

数値や真偽値への変換はありません。両読み取り箇所とも `std::getenv` のポインタが null かどうかだけを見ます。未設定なら共有候補になり、空文字を含む何らかの値が設定されていれば共有しません。したがって `1` だけでなく `0`、`true`、`false`、`0anything`、大文字小文字や前後空白を含む文字列も、いずれも「設定あり」と同じ扱いです（`engine/src/program/generate.cpp:8408-8410`, `engine/src/core/dflash2.cpp:406-407`）。

| 条件 | unset | 有効になる値（共有を止める） | 無効になる値（共有を止めない） |
|---|---|---|---|
| `STRATA_HAVE_DFLASH2` を含む generate の DFlash2 経路 | 共有の候補になり得る | 空文字、`0`、`1`、`true` など、値を問わず設定済み | なし。文字列値の無効判定はない |

## 有効になる条件

- この変数による共有停止は、`STRATA_HAVE_DFLASH2` 付きの generate 実装に限られます。ビルドに DFlash2 がなく `use_df2` が false の場合、この共有処理は実行されません（`engine/src/program/generate.cpp:8151-8159`）。
- 実際に共有を止める対象は、DFlash2 が起動し、MTP もロードされている構成です。`--draft dflash2` の有効化には、fallback を含む `--mtp`、`--spec` 2 以上、native pack、`--draft-model` が必要で、`--pipeline-windows` とは併用できません。満たさない場合の理由表示と fallback / 終了は `engine/src/program/generate.cpp:8243-8248, 8266-8326` にあります。
- 共有自体はさらに、`--mtp-q4 all` / `head` でないこと、`STRATA_MTP_FULL_HEAD`・`STRATA_Q6_PACKED`・`STRATA_MTP_Q8_SM60` が未設定であること、ドラフト語彙ファイルがあることを見積もり側が要求します（`engine/src/program/generate.cpp:8408-8410`）。`STRATA_DF2_HEAD=native` の場合も共有候補から外れます（同:8408-8424、`engine/include/strata/core/dflash2.hpp:55-56`）。
- 実際のバッファ共有には、語彙ファイルから読んだ語彙が空でないことに加え、共有行・GPU 語彙ポインタ・ホスト語彙があり、head 型・語彙数・語彙順が一致する必要があります。満たさない場合は通常の head 行コピー経路を使います（`engine/src/core/dflash2.cpp:387-412, 413-470`）。
- `df2_offer_head` は MTP の `draft_head_view` が成功した場合だけ共有候補を DFlash2 に渡します。通常の CLI 経路では MTP を bind した後に呼ばれます。サーバー経路でも DFlash2 の bind 前に同じ関数を呼びます（`engine/src/program/generate.cpp:8411-8419, 24507-24518, 13584-13595`）。

## 実行時の詳細

`df2_expect_share` は engine 初期化時に一度計算され、DFlash2 用 head の追加 VRAM を 0 と見積もるかどうかを決めます。共有を期待しない場合、MTP 併用時は `mtp.bind_bytes(...)` を head の見積もりに加えます。`df2_head_bytes()` の値はキャッシュ等の予算計算で使われます（`engine/src/program/generate.cpp:8404-8432, 8809, 9200, 9899`）。

DFlash2 の bind 時にも環境を改めて確認します。変数が未設定で全条件が一致すれば MTP の行ポインタを DFlash2 に設定して再利用し、設定済みならその分岐を飛ばして DFlash2 自身の行コピーを作ります。別 GPU に head がある場合は head 側で行を集めて DFlash2 側へ peer copy し、split head では `gather_rows` を使います（`engine/src/core/dflash2.cpp:403-470`）。バッチ用 DFlash2 は親 drafter の bind 後に共有 head を引き継ぐため、各 slot でこの環境変数を再判定しません（`engine/src/core/dflash2.cpp:658-679`）。

読み取りに static cache はありません。見積もりはセットアップ時のローカル値、実際の共有可否は bind 時の `getenv` で判定され、トークンごと・リクエストごとには読み直しません。サーバーの既存 engine で処理中のリクエストに反映される設定ではなく、再評価は次の engine setup / bind 時です（`engine/src/program/generate.cpp:8408-8410, 13584-13595, 24517-24524`; `engine/src/core/dflash2.cpp:406-407`）。

この変数自体は警告やエラーを出しません。共有が成立したときの bind ログには `, the MTP drafter's copy, no second one` が付き、共有されないときはこの句が付きません（`engine/src/core/dflash2.cpp:471-472`）。別コピーの確保や bind に失敗した場合、通常の generate 経路は `strata generate: --draft dflash2: ... The MTP drafts instead.` と出して MTP に切り替えます。サーバー経路は `strata serve: --draft dflash2: ... The MTP drafts instead.` を出し、`--draft-fallback none` なら開始を終了します（`engine/src/program/generate.cpp:24518-24523, 13598-13604`）。

## ログと測定値

ソースと `docs/DETAILS.md` には、この共有停止変数の性能差を条件付きで示す測定値はありません。上記の bind ログは共有状態の観測手段であり、性能値ではありません。

## 根拠

- 候補名の実コード参照は `engine/src/program/generate.cpp:8408` と `engine/src/core/dflash2.cpp:406`。同名コメントは `engine/src/program/generate.cpp:8406-8407`、terminal 設定登録は `terminal/data/settings-register.json:6712`。
- 値の設定有無判定、共有バッファの適用条件: `engine/src/core/dflash2.cpp:403-412`。
- 別コピーを作る fallback と bind ログ: `engine/src/core/dflash2.cpp:413-472`。
- 共有 head の供給、追加 head バイトの見積もり: `engine/src/program/generate.cpp:8404-8432`。
- DFlash2 の利用条件、CLI / serve の bind と失敗経路: `engine/src/program/generate.cpp:8243-8326, 13584-13604, 24507-24529`。
- 共有 head の slot 間引き継ぎ: `engine/src/core/dflash2.cpp:658-679`。
