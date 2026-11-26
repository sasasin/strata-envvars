# `STRATA_DBG_FEAT_LAYERS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MoE prefill の研究用 feature dump で、router 入力 hidden state（bf16）も記録する層を選びます。対象層の routed ids と weights は `STRATA_DBG_FEAT` の dump 対象なら引き続き記録されますが、この変数はその dump のヘッダーにある feature flag と hidden-state の追加書き込みだけを選び、routing や生成結果を変更しません。実装は `Prefill::run_impl` の MoE 処理です（`engine/src/prefill/prefill.cpp:5577-5589, 5625-5639`）。

この変数だけでは hook は動きません。`STRATA_DBG_FEAT` または `STRATA_DBG_ROUTE_OVERRIDE` が設定されて hook のブロックに入ったときに初めて読み取られます。hidden state をファイルへ書くには加えて `STRATA_DBG_FEAT` のファイルを開ける必要があります。`STRATA_DBG_ROUTE_OVERRIDE` だけの場合は layer 選択の値を初期化しますが、feature file はなく hidden state も書きません（同 `5588-5603, 5625-5639`）。

## 値と判定

値全体を検証する parser ではなく、カンマで分けた各部分文字列を `std::atoi` で整数化し、結果が `0..63` の範囲ならその番号を選択します（`engine/src/prefill/prefill.cpp:5596-5603`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/src/prefill/prefill.cpp` の hook に到達し、`STRATA_DBG_FEAT` または `STRATA_DBG_ROUTE_OVERRIDE` が設定済み | `3,4,15,16,27,28,39,40` を選択 | カンマ区切りの各項目が `atoi` で `0..63` になればその層を選択。例: `0`, `63`, `3,4`, `3tail`（数値 prefix の `3`） | 空文字列は項目がなく何も選択しない。`64`, `-1`, `true`, `false` は `atoi` の結果が範囲外または 0 となる（`true` / `false` や空項目は `atoi` が 0 にするため、実際には層 `0` を選択）。 |

各項目で文字列全体の数値妥当性、大文字小文字、空白の除去、エラーは検査しません。`atoi` が認識する先頭の符号・空白と数字 prefix が使われ、変換できない項目は 0 になります。したがって `1,garbage,63` は 1、0、63 を選択し、`,2` や `2,,4` も空項目由来の 0 を選択します。空文字列全体は `while (i < s.size())` のループに入らないため何も選択しません。各変換後の整数を `0 <= v && v < 64` で範囲確認します。整数変換のオーバーフロー時の値はこのコードで別途定義・検査されていません（同 `5598-5602`）。

## 有効になる条件

- hook は MoE 層を処理する `run_impl` 経路にあり、`STRATA_DBG_FEAT` または `STRATA_DBG_ROUTE_OVERRIDE` のいずれかが設定されていないと対象変数を読みません。対象変数単独では有効化されません（`engine/src/prefill/prefill.cpp:5577-5598`）。
- hidden state の dump には `STRATA_DBG_FEAT` が必要で、さらにそのパスを `fopen(..., "wb")` で開ける必要があります。開けなければ `ff == nullptr` となり、ids / weights と hidden state の書き込みブロックは実行されません。失敗理由のログはこの箇所にありません（同 `5592-5595, 5625-5639`）。空文字でも `STRATA_DBG_FEAT` は設定済みとして hook に入りますが、空のパスを開けない場合は dump されません（同 `5592-5595`）。
- `STRATA_DBG_ROUTE_OVERRIDE` だけを設定した場合も hook と対象変数の初期化には到達しますが、`ff` は null なので feature dump は行われません。routing override の読み込み・適用は別変数の動作です（同 `5593-5594, 5606-5621, 5625-5645`）。
- layer-major prefill が選ばれ、`lm_prepare_chain` が成功すると `run_layer_major` が使われます。この walk は routing debug hook を持たず、対象変数だけでは layer-major を止めません。そのため対象変数単独設定時にこの経路が使われれば値は読まれません。一方 `STRATA_DBG_FEAT` または `STRATA_DBG_ROUTE_OVERRIDE` が設定されると `lm_prepare` が layer-major を断り、`run_impl` に進みます（同 `8205-8209, 9657-9705`）。
- Metal の `Prefill::run` はこの共通 `run_impl` へ進む前に Metal prompt 実装を呼んで return します。この変数の読み取り箇所は `engine/src/prefill/prefill.cpp` のみで、`engine/sycl` 側に同名参照はありません。したがって Metal / SYCL 経路にこの hook があるとは確認できません（同 `9633-9650`。リポジトリ全体の同名参照検索では `engine/src/prefill/prefill.cpp` の実読み取り 1 箇所とそのコメント、設定レジストリ項目のみ）。

## 実行時の詳細

対象変数は debug block 内の function-local `static` vector `featl` の初期化 lambda から読み取られます。最初にその宣言へ到達したときに unset なら既定リストを、設定済みならその時点の文字列を parse し、その後の prefill / chunk では vector を再利用します。同じ block の `feat_path`、`ovr_path`、`ff`、routing override map も static です。実行中に環境を変更しても、対象変数やこれらの cached 値は再評価されません。宣言自体は `STRATA_DBG_FEAT` または `STRATA_DBG_ROUTE_OVERRIDE` の guard 内なので、その guard に一度も入らないプロセスでは対象変数の読み取りも初期化もされません（`engine/src/prefill/prefill.cpp:5591-5609, 5641`）。

選択判定は `featl[l & 63]` です。モデルの層番号を 64 で折り返した位置で判定し、dump header には実際の層 `l`、chunk 内の開始位置 `pos`、行数 `T`、feature flag を記録します。`STRATA_DBG_FEAT` の file が開けている場合、各 MoE layer/chunk の ids と bf16 weights を出力し、flag が 1 の層だけ router 入力 `m.mixed_bf` の bf16 値も続けて出力します。これは既存の routing 後の値を記録する処理で、対象変数による routing 上書きはありません（同 `5622-5639`）。

対象変数自身に CLI 引数、設定ファイル、別変数との値優先順位はありません。値を読むかどうかは `STRATA_DBG_FEAT` / `STRATA_DBG_ROUTE_OVERRIDE` の設定有無で決まり、file dump の有無は `STRATA_DBG_FEAT` と `fopen` の結果で決まります。layer-major の選択は `STRATA_PREFILL_LAYER_MAJOR` 等によりますが、debug dump 変数が設定されると `lm_prepare` はその walk を断ります（同 `8205-8209, 9657-9705`）。

## ログと測定値

対象変数の parse、選択層、feature flag に関する stdout / stderr ログはありません。hook は `fwrite` の戻り値を検査せず、ファイルを開けなかったときの警告も出しません（`engine/src/prefill/prefill.cpp:5595, 5625-5639`）。この変数に関する測定値は該当しません。

## 根拠

- `engine/src/prefill/prefill.cpp:5577-5603` — MoE の router 処理後にある debug hook、設定有無の guard、対象変数の直接読み取り、既定値、comma split・`atoi`・範囲判定。
- `engine/src/prefill/prefill.cpp:5622-5639` — 層番号の `& 63` 判定、dump header、ids / weights と選択層の router-input hidden state の書き込み。
- `engine/src/prefill/prefill.cpp:8205-8209, 9657-9705` — debug dump 設定時の layer-major 不適用と、通常 `run_impl` への経路。
- `engine/src/prefill/prefill.cpp:9633-9650` — Metal prefill が共通 `run_impl` の分岐より前に return する経路。
