# `STRATA_FS_AHEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

`STRATA_FS_SLOTS` で有効にした Foresight swap space に対し、次層の router look-ahead が予測した expert を先回りして VRAM slot にコピーする経路を制御します。値が無効でも、実際に外れた expert を `note_miss()` で swap space に補充する経路は残ります。したがって、この変数は swap space 自体のオン・オフではありません。

## 値と判定

`src/program/generate.cpp` は generation の初期化時に `getenv()` と `std::atoi()` で判定します。文字列全体の妥当性検査はせず、`atoi` が変換した整数が 0 かどうかで決まります。

| 値 | `fs_ahead` の判定 |
|---|---|
| 未設定 | 有効（ただし `srcp` があり、`STRATA_FS_SLOTS` の `atoi` 結果が正の場合） |
| 空文字 | 無効（`atoi("") == 0`） |
| 数値変換結果が 0 | 無効。例: `0`, `false`, `abc`, `0tail` |
| 数値変換結果が 0 以外 | 有効。例: `1`, `-1`, `2tail`, `1abc` |

`atoi` は先頭の空白と符号を許し、数字列の後ろは判定に使いません。大文字小文字の比較はありません。`STRATA_FS_SLOTS` も同じ箇所で `atoi(v) > 0` として確認されます。

## 有効になる条件

- `srcp != nullptr` であること。
- `STRATA_FS_SLOTS` が設定され、その `atoi` 結果が 1 以上であること。
- `STRATA_FS_AHEAD` が未設定、または `atoi` 結果が 0 以外であること。
- さらに look-ahead 自体には、`STRATA_LOOKAHEAD` が未設定または `atoi` 結果が 0 以外であることが必要です。`STRATA_LOOKAHEAD=0` なら `fs_ahead` が真でも look-ahead の起動分岐に入りません。
- 予測器の起動には全層分の router 重みが `WeightKind::Bf16InF32` で、バイト数が `n_expert * n_embd * 2` に一致することも必要です。不一致時は `routing-aware prefetch off (the routers are not BF16 in the arena)` を stderr に出します。

`STRATA_FS_AHEAD=0` でも、file tier が `src.warms()` を満たす場合はファイル tier の page warming 用 look-ahead が起動し得ます。また `STRATA_LOOKAHEAD_STATS` が有効なら測定用の look-ahead も起動条件になり、`fs_ahead` が偽でも統計モードとして cold source を許可します。

Foresight swap space の初期化は別に行われます。`STRATA_VERIFY_DEVICE_PLAN` が非ゼロなら初期化側が swap space を無効にします。この場合も `fs_ahead` の値は look-ahead の起動判定には使われますが、swap への予測コピーは接続されません。

予測を swap に渡す条件を満たしても、実際のコピー予約には、source 上の expert blob が存在し pinned であること、コピー budget に余裕があること、対象 layer で再利用可能な slot があることが必要です。条件不足では予約が行われず、予測した expert が必ず GPU に載るわけではありません。

## 実行時の詳細

判定は generation の初期化時に `const bool fs_ahead` へ保存され、その generation の間は再読込されません。プロセス内の環境変数を書き換えた場合の反映は、この初期化が再度実行されるかどうかに依存します。

起動した `RouterLookahead` は、各 layer の MoE 入力から次 layer の router を CPU 上で評価し、各 token の上位 `STRATA_LOOKAHEAD_K` 件（未設定時 10、1〜expert 数に clamp）から GPU に常駐している expert を除外して予測対象を集めます。予測対象に対しては `src_->warm()` を呼びます。Foresight swap への連携ポインタが設定されている場合、次 layer（深さを広げても `dj == 0` の層だけ）について `ForesightSwap::predict()` も呼びます。これはコピー候補を予約するだけで、予測が実際の router の選択や出力を変えることはありません。

`STRATA_FS_AHEAD` を無効にすると、cold source だけを理由に通常の先読みが起動することはなく、先読み予測を swap slot に渡しません。swap space が稼働している場合、実際に GPU cache 等にない expert は dispatch 時に `note_miss()` で補充候補になります。コピー完了前の slot は利用されず、実際の生成計画は host pool が決めます。

look-ahead が開始すると stderr に `strata generate: routing-aware prefetch on (the next layer's router, feeding the Foresight swap space)` または `..., file tier)` が出ます。開始条件を満たさない、または router の形式が適合しない場合は `routing-aware prefetch off (...)` が出ます。`fs_ahead` が真であっても、swap space の初期化に失敗・抑止された場合は、開始ログの文言だけでは swap への接続を保証しません。swap space 自体が有効なら終了時の報告は `foresight swap: ... copies (... from the router look-ahead) ...` の形式で、予測コピー数も含みます。

## 根拠

- `src/program/generate.cpp:5488-5524`: `fs_ahead` と関連変数の読み取り、look-ahead の起動条件、router 重みの検査、ログ。
- `src/program/generate.cpp:8181-8199`: swap space の初期化と look-ahead への接続、破棄前の detach。
- `src/core/expert_source.cpp:2172-2180,2183-2199`: source が warm 可能かどうかの検査と `allow_cold_source` 条件。
- `src/core/expert_source.cpp:2333-2412`: router 予測、常駐 expert の除外、source warming と予測先の swap 呼び出し。
- `src/core/expert_source.cpp:3730-3744`: swap slot の hit と miss 補充経路。
- `src/core/expert_source.cpp:4881-4936,4951-4976`: 予測コピー予約、slot と budget 条件、`STRATA_VERIFY_DEVICE_PLAN` による swap 無効化。
- `include/strata/core/foresight_swap.hpp:2-21,73-81`: swap space の目的、予測の役割、安全条件。
- `docs/DETAILS.md:1680-1688`: `STRATA_FS_AHEAD=0` を misses-only とする説明、および同資料に記載された測定の条件と結果。ここに挙げられた値は資料記載の実測であり、この調査で再測定したものではありません。
