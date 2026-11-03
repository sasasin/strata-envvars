# `STRATA_DS4_RAM_SKIP_W`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 (`strata-dsv41`) の decode lane で、route weight が小さい CPU-lane expert を読み飛ばすしきい値です。しきい値は各 token の有効な routed expert の weight 合計に対する割合として扱われます。読み飛ばした expert の weight は残りの expert に再配分されないため、出力が変わる可能性があります。

値を読むのは `src/dsv41/ds4_model.cu` の `Model::Impl` 内だけです。ここで得た値は model implementation のメンバーに保持され、decode 用の `serve_lane()` がルーティングを処理するときに参照されます。索引以外のソース・文書にある同名の別用途や、別の env helper 経由の読み取りは見つかりませんでした。

## 値と判定

`std::getenv()` の結果を `std::atof()` で float に変換し、`std::max(0.0f, ...)` で負値を 0 にします。変換後の値が `0.0f` より大きい場合に限り、読み飛ばし条件が有効です（`src/dsv41/ds4_model.cu:1401-1408,9465`）。

| 環境変数の状態・値 | 結果 |
| --- | --- |
| 未設定 | 既定値 `0`。無効 |
| 空文字、数値に変換できない文字列 | `atof` が `0` とするため無効 |
| `0`、負値 | 0 以下となり無効。負値は 0 に clamp |
| 正の数値 | 有効。route weight 合計に対する比率のしきい値として使う |

文字列全体の厳密な検証や範囲 clamp はありません。`atof` が数値として読める先頭部分を変換するため、例えば `0.1suffix` は `0.1` として扱われます。route weight の比率がしきい値と等しい expert は、比較が `<` なので除外されません（`src/dsv41/ds4_model.cu:1405-1408,9494`）。

## 有効になる条件

- `strata-dsv41` の `src/dsv41/ds4_model.cu` にある decode 用 `serve_lane()` が処理する routed expert が対象です。prompt の chunk/window 処理に対するこの環境変数の読み取りや適用は見つかりませんでした。decode request 用の service thread が `serve_lane()` を起動します（`src/dsv41/ds4_model.cu:3737-3762,9387-9420`）。
- 値の読み取り・判定箇所に OS / backend 用の条件分岐はありません。適用されるのはこの `strata-dsv41` model implementation の decode lane です（`src/dsv41/ds4_model.cu:1405-1408,9387-9420`）。
- MTP layer ではなく、`li >= STRATA_DS4_DISK_SKIP_FROM` かつ `li < g.nl` の layer が対象です。`STRATA_DS4_DISK_SKIP_FROM` の既定値は 0 で、負値は 0 に clamp されます。この変数は RAM skip にも層の開始位置を与えます（`src/dsv41/ds4_model.cu:1409-1412,9460-9465`）。
- weight 合計は、その token の有効な expert id（`0 <= id < l.n_exp`）の routed weight の合計です。正のしきい値がある場合にこの合計を計算します（`src/dsv41/ds4_model.cu:9465-9474`）。
- 対象となるのは `l.slot[e] < 0` の expert、すなわち GPU 常駐 slot に割り当てられていない expert の処理です。GPU 常駐 slot にある expert はこの skip 分岐を通りません。CPU-lane の expert のうち、store の zero-copy slot から GPU が計算するものも分岐前に処理を抜けるため、この変数では除外されません（`src/dsv41/ds4_model.cu:9487-9496`）。
- `STRATA_DS4_DISK_SKIP_W` が未設定または 0 でも RAM skip は独立して有効になり得ます。`STRATA_DS4_DISK_SKIP_AUTO` も RAM skip の gate ではありません。一方、層開始位置は上記の通り `STRATA_DS4_DISK_SKIP_FROM` と共有です（`src/dsv41/ds4_model.cu:1391-1412,9460-9465`）。

## 実行時の詳細

model implementation の構築時に `STRATA_DS4_RAM_SKIP_W` を読み、変換結果を `ram_skip_w` に保存します。リクエストごとに環境変数を再読しません。同じ model implementation が存続している間にプロセス環境を変更しても反映されず、新しい implementation の構築時には改めて読み取られます（`src/dsv41/ds4_model.cu:1405-1408`）。CLI 引数や設定ファイルによる優先順位・上書き経路は見つかりませんでした。

decode の各 layer/token では、各有効 expert の route weight `r.w[t][i]` が `ram_skip_w * wsum` より小さいかを判定します。expert が GPU slot にない場合、store zero-copy の早期 continue に該当しない限り、該当 expert を `picks` に追加せず `st.skipped` を増やします。従って、その expert は後続の CPU 計算や lane への読み出し対象から外れます。除外前に expert profile と heat は更新されます。weight は再正規化されません（`src/dsv41/ds4_model.cu:9465-9508`）。

明示的なしきい値範囲エラー、警告、専用の終了・失敗経路はありません。除外数は `st.skipped` に記録され、decode の集計で `decode left out ... experts a token ...` として stderr に表示されます。また、通常の STAT 行では `skipped=...` が付く場合があります。これらは `STRATA_DS4_DISK_SKIP_W` による除外も同じカウンターで数えるため、表示だけでは RAM skip による数と分離できません。RAM skip は RAM 内かどうかに関係なく適用されるため、この集計文の `not in RAM` という表現は RAM skip 分の実態を必ずしも表しません（`src/dsv41/ds4_main.cpp:993-1000,2788-2814`; `src/dsv41/ds4_model.cu:9494-9496`）。

## 根拠

- 唯一の環境読み取り、変換、既定値: `src/dsv41/ds4_model.cu:1401-1408`
- 共有される層開始設定: `src/dsv41/ds4_model.cu:1409-1412,9460-9465`
- decode service thread と routed expert の weight 合計・skip 条件: `src/dsv41/ds4_model.cu:3737-3762,9387-9420,9460-9508`
- skip 数の stderr/STAT 表示: `src/dsv41/ds4_main.cpp:993-1000,2788-2814`
