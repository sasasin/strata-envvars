# `STRATA_DF2_GATE`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

DFlash2 が提案した draft の確率から verify window の幅を選ぶ際、固定の `--draft-conf` 閾値による選択を、request 中に観測した draft 生存率と token あたりの所要時間に基づく gate に置き換えます。これはウィンドウ幅の選択を変える設定です。

対象となるのは、DFlash2 が有効な CUDA/HIP build の逐次 serve request loop です。DFlash2 実装は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` の build で `STRATA_HAVE_DFLASH2` として有効になります。Metal/SYCL build にはこの DFlash2 機能がありません（`CMakeLists.txt:465-472`）。

## 値と判定

| `STRATA_DF2_GATE` の値 | gate の値 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

文字列全体の比較や数値変換はせず、`getenv()` の結果が null でないことと `e[0] == '1'` だけを判定します。空白の trim、大文字小文字、残りの文字列の検証はありません。判定結果は関数内の `static const bool` に初回評価時保存され、その後の環境変更は同一プロセスでは反映されません（`include/strata/spec/window_rule.hpp:118-121`）。

## 有効になる条件

値が有効でも、以下の経路でなければ window の選択には影響しません。

- DFlash2 を含む CUDA/HIP build である。
- DFlash2 drafter が起動に成功し、当該 request で DFlash2 が選択されている（`req_df2`）。`--draft auto` では request ごとに MTP と DFlash2 のどちらを使うかを決めます（`src/program/generate.cpp:15810-15852`）。DFlash2 の初期化に失敗し MTP fallback へ移る場合、その request では gate は使われません（`src/program/generate.cpp:11660-11689`）。
- 初回 window ではなく、draft が有効である。
- 通常の window-rule 分岐に入っていること。gated proposal 経路は別分岐です（`src/program/generate.cpp:18870-18890`）。

通常の非-serve `strata generate` の decode loop には `df2_gate_on()` の呼び出しがなく、この変数はその経路の window 選択を変えません（同 loop の DFlash2 draft 処理: `src/program/generate.cpp:20820-20863`）。batch slot の専用処理にもこの gate の呼び出しはありません。serve request loop 内では、suffix lookup が選ばれた window は gate が決めた幅から lookup 側の幅に置き換わる場合があります（`src/program/generate.cpp:18892-18909`）。

## 実行時の詳細

serve request ごとに `AdaptiveGate` を作り、その request 内で観測値を蓄積します（`src/program/generate.cpp:18020-18022`）。各非初回 DFlash2 window の候補幅を選ぶとき、DFlash2 の最大 window 幅 `S_mtp` を上限として、累積 draft 確率 `C_j` と、位置 j・確率 bucket ごとの観測生存率を使います。生存率は prior `C_j^1.3`（重み `prior_n=3`）と、その request で観測した成功数/試行数の平滑化値です。`survival × ms_per_tok` が次の verify row のコスト `row_ms` 以上である間、window に次の row を足します。最初の時間観測までは `ms_per_tok=9 ms`、row コストの初期値は `3 ms` です（`include/strata/spec/window_rule.hpp:77-99`）。

各 timed DFlash2 round の終了時に、lookup 由来でない draft window について draft 生存数を更新し、committed token 数に対する round 時間を token あたり時間の EMA（前回値 0.9、新値 0.1）として記録します。committed token が 1 未満なら時間更新を行いません。値は request ごとの `AdaptiveGate` に保持され、別 request には引き継がれません（`include/strata/spec/window_rule.hpp:101-115`; `src/program/generate.cpp:19343-19346`）。

row コストは別環境変数 `STRATA_DF2_ROW_MS` で設定できます。空または未設定なら 3.0、非空なら `std::atof` の結果を使い、値域 clamp や parse 成功の確認はありません。この値も static cache されます（`include/strata/spec/window_rule.hpp:122-124`; 初回設定: `src/program/generate.cpp:18021-18022`）。`STRATA_DF2_GATE` 自体には CLI 引数による上書きはありません。`--draft-conf` は gate が無効な場合に既存 window rule が使う別の閾値であり、gate が有効で条件を満たす場合は、その rule の `T` を `AdaptiveGate::choose()` の結果で置き換えます（`include/strata/spec/window_rule.hpp:57-70`; `src/program/generate.cpp:18881-18890`）。

この環境変数に固有のログ、警告、エラー終了経路はありません。DFlash2 自体の開始失敗は serve stderr に理由を出し、MTP fallback がない `--draft-fallback none` では開始を終了します（`src/program/generate.cpp:11674-11682`）。

## 根拠

- 読み取り・値判定・static cache: `include/strata/spec/window_rule.hpp:118-121`。
- adaptive survival、window 幅選択、request 内観測: `include/strata/spec/window_rule.hpp:77-115`。
- serve loop での state 作成、row cost 設定、DFlash2 時の gate 適用: `src/program/generate.cpp:18020-18022,18881-18890`。
- gate の timed round 観測更新: `src/program/generate.cpp:19343-19346`。
- DFlash2 を含む build 条件: `CMakeLists.txt:465-472`。
