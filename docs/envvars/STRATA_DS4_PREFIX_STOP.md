# `STRATA_DS4_PREFIX_STOP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 サーバーが新しい会話向けに共有 prompt start（system prompt と tools の末尾）の状態を保存するとき、その位置で prompt の読み取りを止める経路を選びます。未設定では、条件が合えばその位置を含む読み取りを先へまとめて進め、共有 start の状態を読み取り中に別途保存します。設定すると、このまとめ読みを避け、shared start の位置で読み取りを区切ってから状態を保存します。

## 値と判定

値の内容は parse されません。`std::getenv()` が null かどうかだけで判定します。

| 設定状態 | `start_stop` |
|---|---|
| 未設定 | false |
| 空文字を含む、何らかの値を設定 | true |

したがって `STRATA_DS4_PREFIX_STOP=0` や `false` も有効です。数値変換、値域検査、無効値時の fallback はありません。CLI 引数や別の設定でこの判定を上書きする処理も確認できません。

## 有効になる条件

値が設定されていても、次の条件がそろう場合に限り読み取り経路に影響します。

- DS4 サーバーの prompt 読み取り (`prompt_piece`) を実行する。
- `m.marks_cap() > 0` で、共有 start の mark が prompt にある。shared mark はリクエストの `shared=`、または `pin=` から作られる。
- `STRATA_DS4_PREFIX_KEEP` が 0 より大きい（未設定時の既定値は 2）。
- 読み取り開始位置 `from` が 0、次の mark が最初の mark、mark が shared、位置が `STRATA_DS4_PREFIX_MIN` 以上（未設定時の既定値は 1024）。
- さらに、read-piece の残り全体を一度に読む最適化が候補になる場合（最後の window 専用読み取りではなく、`piece >= rest` かつ `rest <= m.feed_unit()`）。このとき `start_stop` が真だと、そのまとめ読みを抑止する。

`STRATA_DS4_PREFIX_KEEP` が 0 以下、marks が使えないモデル、開始位置が 0 以外、shared mark がない、または上記の読み取り最適化が候補でない場合、変数を設定してもこの分岐による違いはありません。OS/backend/build macro による値判定の違いはこの箇所にはありません。

## 実行時の詳細

`prompt_piece` 内の `static const bool start_stop` は、関数が最初にこの読み取り位置へ到達したときに一度だけ初期化され、以後のリクエストでも同じ値を使います。プロセス起動後に環境を書き換えても反映されません。

通常、読み取り loop は次の cut の位置で token 数を区切ります。しかし、読み取り残りを一度に処理できる場合は `feed_marks()` で複数の mark をまとめて処理できます。対象条件下で変数が設定されていると `start_kept` が真になり、この `feed_marks()` のまとめ読み分岐に入らず、shared start で読み取りを止めます。到達した mark を `m.mark()` で記録し、shared start が適格なら `prefix_keep()` で状態を保存します。設定されていない場合はまとめ読み側で shared start の状態を別途保存し、後続 token の読み取りを続けられます。

この変数固有の警告・終了・失敗経路はありません。prefix の保存に失敗すると stderr に `ds4: keeping the shared start failed (...)`、保存に成功すると `ds4: kept a ...-token shared start (...)` が出ます。これらは prefix 保存処理のログで、変数の値自体を表示しません。

## 根拠

- `src/dsv41/ds4_main.cpp:791-806` — shared prefix 保存の用途、関連設定の既定値、prefix 上限・最低長。
- `src/dsv41/ds4_main.cpp:824-856` — 保存対象の最低長判定、slot 保存の失敗・成功ログ。
- `src/dsv41/ds4_main.cpp:1146-1183` — request の `shared=` / `pin=` から marks を作る条件。
- `src/dsv41/ds4_main.cpp:1228-1268` — 読み取り時の cut、`start_stop` と `start_kept` 判定、まとめ読みの抑制、読み取り中の prefix 保存。
- `src/dsv41/ds4_main.cpp:1296-1304` — cut 到達時の mark と shared prefix 保存。
- `src/dsv41/ds4_main.cpp:1349-1352,1781-1787` — 単一会話と複数会話の prompt 読み取りから `prompt_piece` を呼ぶ経路。
