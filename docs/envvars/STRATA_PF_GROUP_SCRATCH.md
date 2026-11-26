# `STRATA_PF_GROUP_SCRATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Prefill の MoE MMQ 経路で使う `GU`（gate/up 出力）、`H`（SwiGLU 出力）、`Hq`（量子化した `H`）の scratch を、チャンク全体の routed row 数ではなく expert group の上限行数に合わせて小さくする opt-in 変数。`Xq` は gate/up がチャンク全体の入力行を読むため全行分を維持する。group の合計行数が上限を超えた場合は、その group を expert の連続した sub-range に分け、各 range の gate/up、SwiGLU、量子化、down の MMQ 処理を順に行う。`engine/src/prefill/prefill.cpp:2210-2214,2333-2338,6506-6521,7307-7351`。

この変数は prefill のチャンク長を直接指定しない。scratch の必要量が減るため、`--prefill auto` の候補を評価する `bytes_needed` にも反映され、他の条件が許せばより大きいチャンクが収まることがある。自動選択の上限や明示した `--prefill N` のチャンク長をこの変数が書き換える処理はない。`engine/src/prefill/prefill.cpp:2333-2338,2348-2371,3707-3718`; `engine/src/program/generate.cpp:4000-4008,11304-11318,11351-11360`。

## 値と判定

`pf_group_scratch()` の関数内 `static` 初期化で `std::getenv` し、未設定なら無効、設定済みなら `std::atoi(v) != 0` を有効とする。したがって厳密な文字列 `1` との比較ではない。`atoi` は先頭の空白と符号を許し、先頭の十進整数部分を変換して後続文字を無視する。数値に変換できる先頭部分がなければ 0 になる。コードには文字列全体の検証や値域制限がない。`engine/src/prefill/prefill.cpp:2215-2217`。

| 値の例 | 判定 | 理由 |
|---|---|---|
| 未設定 | 無効 | `getenv` が `nullptr` |
| 空文字 `""` | 無効 | `atoi` の結果が 0 |
| `0`, `0anything`, `false`, `true`, 空白だけ | 無効 | 変換結果が 0（`true` は数値の先頭部分がない） |
| `1`, `2`, `-1`, `  +1tail` | 有効 | 先頭の整数変換結果が 0 以外 |

符号付き整数の範囲外の文字列について、`atoi` の結果を保証する検査や fallback はありません。境界値の明示的な clamp もありません。`engine/src/prefill/prefill.cpp:2215-2217`。

## 有効になる条件

- 値の判定が有効であること。
- `mmq_plan()` に少なくとも一つ MMQ 層があり、FP16 fallback と `pf_wmma()` の FP16 buffers を使わず、`mp.layer` の全層が MMQ を使うこと。MMQ 未 build、層の一部でも MMQ tile がない場合などは条件を満たさない。`engine/src/prefill/prefill.cpp:2026-2042,2048-2076,2191-2192,2219-2224`。
- `STRATA_MMQ_DIRECT` の direct 読みがいずれの層にも選ばれていないこと。1 層でも `mp.direct` が立つと変数は無視される。`engine/src/prefill/prefill.cpp:2142-2161,2219-2224`。
- 現在の layout が fused buffers を使わないこと。fused layout では `moe_bufs` が通常の fused 用サイズを使い、`m.group_cap` は 0 になるため、この scratch 縮小は適用されない。`engine/src/prefill/prefill.cpp:2267-2269,2333-2346,2786-2792,2913`。
- 実行中に group scratch が設定されているのに、layer が fused path または非-MMQ path に入った場合、その処理は `err` を設定して失敗する。`engine/src/prefill/prefill.cpp:5705-5709`。

scratch 行数の上限は既定で `T + 3 * (T * K * MMQ_GROUP / n_expert)` を 64 行境界へ切り上げた値。別の test knob `STRATA_PF_GROUP_CAP` が正の `atoll` 値なら `max(その値, T)` を使う。これは少なくとも一 expert の最大 routed rows `T` を収める。`engine/src/prefill/prefill.cpp:2233-2239`。

## 実行時の詳細

値は `pf_group_scratch()` が初めて呼ばれた時に一度読み、プロセス内の関数 static に保存する。最初の呼び出し後に環境を書き換えても値は更新されない。機能可否 `ok` も一度決まり、無効化理由の出力はその初回判定時だけ行う。`mmq_plan()` も関数内 static で一度作られる。`engine/src/prefill/prefill.cpp:2026-2028,2215-2229`。

有効時、非 fused layout の `moe_bufs` は `GU` と `H` を上限行数分、`Hq` をその上限の q8 行数分で見積もり、`Xq` は `T * K` 行分のままにする。`bytes_needed` の見積もりと `carve` の実 allocation が同じ `moe_bufs` を使う。`engine/src/prefill/prefill.cpp:2330-2338,2348-2371,2786-2828,3707-3718`。

MMQ 実行時は、通常の group bounds を作り、上限超過 group を連続する expert sub-range に分けて各 range 用 bounds を追加する。各 range では元の MMQ gate/up・SwiGLU・quantize・down 処理を行い、結果行は元の routed row 位置へ書く。bounds table が確保量を超えた場合は失敗する。`engine/src/prefill/prefill.cpp:6496-6527,7307-7351`。

`--prefill auto` はバッファ必要量を使って収まるチャンクを選ぶため、この変数による見積もり減少の影響を受ける。一方、`--prefill auto:N`、`STRATA_PREFILL_AUTO_MAX`、プラットフォーム別 ceiling などの auto 上限決定は別処理であり、本変数による変更は確認できない。明示チャンクもこの値で変更されない。`engine/src/program/generate.cpp:4000-4019,11230-11248,11304-11318,11321-11325,11351-11360`。

## ログと測定値

条件不足で有効化されないとき、stderr に次の prefix と理由を出す（理由文は分岐に応じて以下のいずれか）。

- `strata prefill: STRATA_PF_GROUP_SCRATCH=1 is ignored: the prompt path runs the FP16 path or pf_wmma here, not MMQ`
- `strata prefill: STRATA_PF_GROUP_SCRATCH=1 is ignored: a layer does not take MMQ`
- `strata prefill: STRATA_PF_GROUP_SCRATCH=1 is ignored: STRATA_MMQ_DIRECT is on for a layer (its guard tables are per whole group)`

有効な scratch を layout に適用すると、stderr に `strata prefill: chunk <T> tokens: STRATA_PF_GROUP_SCRATCH on (GU/H/Hq hold <上限> rows, not <T*K>);` を出す。bounds table overflow、上限超過 range、MMQ/fused 条件違反ではそれぞれ `STRATA_PF_GROUP_SCRATCH's bounds table overflowed`、`STRATA_PF_GROUP_SCRATCH: a range of ... rows passes the scratch's ...`、`STRATA_PF_GROUP_SCRATCH needs MMQ on every layer (a layer took the fused or FP16 path)` を error に設定して該当処理を失敗させる。`engine/src/prefill/prefill.cpp:2221-2227,2913-2919,5707-5709,6524-6527,7321-7325`。

`docs/DETAILS.md:1278` は `STRATA_PF_GROUP_SCRATCH=1` と `STRATA_PF_HC_REGION=1` をまとめ、同一チャンクで同じ bits と記載している。これは資料上の説明であり、本調査で性能・出力一致を測定していない。ソースの説明は `engine/src/prefill/prefill.cpp:2210-2214` にあり、実装では group scratch と HC region は別々に判定・割り当てられる（同ファイル `2913-2919`）。DETAILS の表にある速度値は当該資料の記載で、ここでは一般化しない。

## 根拠

- `engine/src/prefill/prefill.cpp:2215-2229` — 値の読み取り、cache、有効条件と理由ログ。
- `engine/src/prefill/prefill.cpp:2233-2239,2333-2338` — group row cap と scratch sizing。
- `engine/src/prefill/prefill.cpp:2913-2919,6496-6527,7307-7351` — layout への適用、分割と MMQ 実処理、失敗経路。
- `engine/src/program/generate.cpp:4000-4019,11304-11325,11351-11360` — CLI の auto 上限と必要量に基づくチャンク選択。
