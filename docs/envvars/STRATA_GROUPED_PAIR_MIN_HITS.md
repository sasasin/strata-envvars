# `STRATA_GROUPED_PAIR_MIN_HITS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

per-hit の grouped S2 expert カーネルで、新しい「2行を1 warp で処理する」カーネルを使い始める hit capacity の下限を指定します。capacity が閾値未満なら、従来の「1行を1 warp で処理する」カーネルを選びます。デフォルトの閾値は 0 なので、他の条件を満たす限り新しいカーネルを選びます。

対象は `moe_hit_grouped_s2`、`moe_hit_grouped_s2_dev`、`moe_hit_grouped_s2_multi` の per-hit 経路です。`moe_grouped_s2` は `new_grouped()` で別に判定され、この閾値を参照しません。

## 値と判定

値は `std::atoll` で読み取ります。文字列全体の検証や範囲 clamp はありません。

| 環境変数の値 | 閾値 | 判定への影響 |
|---|---:|---|
| 未設定 | 0 | 正の capacity は閾値以上 |
| 空文字、数字で始まらない文字列 | 0 | `atoll` の変換結果は 0。正の capacity は閾値以上 |
| 数字で始まる文字列 | 先頭の符号付き 10 進数部分 | 数字の後ろは変換に含まれず、capacity がその値以上なら新カーネル候補 |
| 負数 | 負の閾値 | 通常の正の capacity は閾値以上 |

たとえば `3tail` は閾値 3、`  +3` も閾値 3、`off` は閾値 0 になります。`STRATA_GROUPED_PAIR_MIN_HITS=0` は新カーネルを無効にしません。実際の条件は `cap >= pair_min_hits()` です。

## 有効になる条件

閾値以上であることに加え、次の条件をすべて満たす必要があります。

- 旧カーネルが強制選択されていない。
- activation `x_q8_0` と scratch のアドレスが 4-byte aligned。
- expert blob の先頭アドレスが 8-byte aligned で、blob サイズも 8 の倍数。

いずれかを満たさなければ従来カーネルを使います。`moe_hit_grouped_s2_dev` と `moe_hit_grouped_s2_multi` では、判定に使う `cap` は予約された capacity です。デバイス上の実 hit 数 `d_count` ではありません。

`moe_grouped_select_old()` が `0` または正数でカーネル選択を強制している間は、`STRATA_GROUPED_PAIR_MIN_HITS` は無視されます。強制値 0 は新カーネルを選び、正数は旧カーネルを選びます。引数が負数なら環境変数による選択へ戻ります。環境変数 `STRATA_OLD_GROUPED` は旧カーネル選択に使われ、設定値の先頭文字が `1` なら旧カーネルを選択します。

## 実行時の詳細

CUDA 実装と SYCL 実装の両方に同じ閾値判定があります。環境変数は `pair_min_hits()` 内の function-local `static` として初回評価時に一度だけ読み取られます。初回呼び出し時にカーネル選択が強制されていると、関数は閾値を読む前に 0 を返します。その後、選択を環境変数へ戻して初めて閾値を評価する場合があります。一度 static 値が初期化された後は、プロセス内で環境を書き換えても再読込されません。

閾値条件は per-hit の gate/up と down のカーネル選択に使われます。新旧カーネルの選択自体による数値出力は同じ、という実装コメントがありますが、この調査では実行や測定による照合はしていません。環境変数を読むことによる専用ログは確認できません。各経路の起動エラーは既存の `check()` によるエラー処理に従います。

## 根拠

- 値の読み取り、`atoll`、既定値 0、強制選択時の早期 return、`cap >= threshold` 判定: `src/kernels/cuda/s2_expert_grouped.cu:533-560`; SYCL 版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:743-770`。
- per-hit 実装で `new_hit(..., cap)` の判定結果を gate/up と down の両方へ渡す: `src/kernels/cuda/s2_expert_grouped.cu:611-649,715-742,752-779`; SYCL 版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:1047-1087,1112-1152`。
- grouped 経路が `new_grouped()` を使い、当該閾値を参照しないこと: `src/kernels/cuda/s2_expert_grouped.cu:550-561,1131-1149`; SYCL 版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:760-770,1577-1622`。
- 強制選択 API と環境変数選択の仕様: `src/kernels/cuda/s2_expert_grouped.cu:516-531,596-598`; API コメント `include/strata/kernels/s2_expert_grouped.hpp:113-121`。
- `docs/DETAILS.md` および関連設計資料には、この閾値の追加仕様や測定条件を確認できませんでした。上記の挙動は現行ソースの分岐に基づきます。
