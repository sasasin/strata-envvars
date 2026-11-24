# `STRATA_INK_TIER_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA の Inkling-2 hybrid 実装で adaptive expert tier が有効になったとき、GPU/host の expert 使用状況を集計して配置を見直す round の起動間隔を、MoE を通った token row 数で指定する。既定は 4 row。設定値は `tier_round_rows` に入り、expert の選択や生成 token 自体を直接指定するものではなく、使用状況の snapshot と配置更新の周期を変える（`engine/src/inkling2/cuda/ink_hybrid.cuh:2169-2171, 2288, 2361-2385`）。

この値は adaptive tier 自体を有効化しない。tier の有効化には別環境変数 `STRATA_INK_TIER` とモデル配置・RAM/VRAM 条件が関係する（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2187`; `engine/src/inkling2/cuda/ink_runner.cuh:470-480, 1342-1352`）。

## 値と判定

`tier_alloc()` 内で `getenv` が非 null の場合だけ `std::atoi` で変換し、結果を `std::max(1, value)` で下限 1 に丸める。未設定ならフィールド初期値 4 を使う。空文字も設定済みとして `atoi("") == 0` となり 1 row になる。`atoi` は数値としての文字列全体の妥当性を検査せず、先頭の空白と符号を受け入れ、数字の後ろの文字は無視する。したがって `"  +3tail"` は 3、`"0anything"`、`"true"`、`""`、`"-2"` は 1 になる。正の数値 prefix はその値になり、例として `"4"` は 4。大文字小文字の扱いは適用されず、非数値の先頭は変換値 0 として下限 1 になる。`atoi` の `int` で表現できない値は C/C++ の変換規則上の保証がないため、サポートされる境界値として扱えない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2169-2171, 2288`）。

| 実行条件 | 未設定 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| `tier_alloc()` が呼ばれ、adaptive tier の割り当てに成功 | 4 | `atoi` の変換結果が 1 以上（例: `1`, `4`, `" 8rows"`） | 独立した無効値扱いはない。0 以下および数値 prefix のない文字列は 1 に丸められる |
| adaptive tier が呼ばれない、または割り当てに失敗 | 適用されない | 適用されない | 読み取り自体が行われないか、読み取った値が使われない |

CLI 引数や他の環境変数による `STRATA_INK_TIER_ROWS` 自体の上書きはこの実装にない。`STRATA_INK_TIER=0`（値の先頭文字が `0`）は tier 選択を止める別設定であり、この変数との優先順位より前に適用される（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2187`; `engine/src/inkling2/cuda/ink_runner.cuh:473, 1346`）。

## 有効になる条件

- Inkling-2 の CUDA hybrid runner で adaptive tier 候補となり、`STRATA_INK_TIER` が設定されていないか、設定値の先頭文字が `0` 以外であること（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2187`; 呼び出し元 `engine/src/inkling2/cuda/ink_runner.cuh:473, 1346`）。
- 通常の配置経路では host expert があり、SSD expert がなく、VRAM に expert があり、`ssd_experts` が false であること（`engine/src/inkling2/cuda/ink_runner.cuh:470-480, 1342-1352`）。別の配置経路では `ls_active` と `ep2_active` がともに false であることも条件（同 `1342-1347`）。
- tier 用の追加 host copy が利用可能 RAM に収まり、`tier_plan()` が空でない pool を計画すること。RAM 不足時は tier を有効化せず、理由を `[InkTier] off: the host copy ... does not fit ...` と stderr に出す（`engine/src/inkling2/cuda/ink_runner.cuh:473-480, 1346-1352`）。
- `tier_alloc()` で `active` と `d_use_cnt` が有効で、slot pool が空でなく、pool の `cudaMalloc` が成功すること。満たさず false を返す場合、呼び出し元は tier を止め、`[InkTier] off: the card has no room for the slot pool (...)` を stderr に出す（`engine/src/inkling2/cuda/ink_hybrid.cuh:2268-2271`; `engine/src/inkling2/cuda/ink_runner.cuh:504-522, 1383-1401`）。
- 有効な tier の実行中に `step_after()` が呼ばれること。probing 中や inactive 時は処理を進めず、tier が無効なら既存の `step_promote()` 経路に戻る（`engine/src/inkling2/cuda/ink_hybrid.cuh:2364-2371`）。

## 実行時の詳細

環境変数は `tier_alloc()` の成功経路で一度読み、`tier_round_rows` メンバーに保存される。関数内 static cache ではなく engine instance のフィールドであり、各 decode step では環境変数を再読しないため、プロセス実行中に環境を変更しても既存 engine には反映されない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2164-2171, 2268-2295`）。

初期化時の stderr ログは `[InkTier] adaptive expert tier on: ...; a round every %d tokens, %d swaps` の形式で、設定後の row 間隔を表示する（`engine/src/inkling2/cuda/ink_hybrid.cuh:2291-2296`）。tier 中は MoE decode step の row 数を `tier_rows_since` に加算し、閾値以上かつ前の snapshot が pending でなければ device counter を非同期コピーし、event を記録してカウンターを 0 に戻す。後続 step で snapshot が利用可能になってから policy round と slot swap を行うため、環境変数は round の起動間隔に作用し、snapshot の完了待ちは後続処理で行われる（`engine/src/inkling2/cuda/ink_hybrid.cuh:2361-2385`）。`step_after()` は通常の decode のほか、tree verify / batched 経路からも呼ばれる（`engine/src/inkling2/cuda/ink_runner.cuh:3684-3695, 3813, 3860-3864`）。

この変数を子プロセスへ転送する処理は、Strata ソース内の参照では確認できない。索引・設定レジストリは名前を列挙するが、値の読み取りは `ink_hybrid.cuh` の上記箇所だけである（`terminal/data/settings-register.json:17783-17793`）。

## ログと測定値

初期化成功時、上記のとおり round 間隔を含む `[InkTier] adaptive expert tier on: ...` を stderr に出す。停止時には `[InkTier] %llu rounds, %llu swaps` を stderr に出す（`engine/src/inkling2/cuda/ink_hybrid.cuh:2293-2296, 2389-2395`）。`STRATA_INK_TIER_LOG` が設定されている場合は、64 round ごとに `[InkTier] round %llu: %d swaps (total %llu)` も出る（`engine/src/inkling2/cuda/ink_hybrid.cuh:2355-2358, 2289-2290`）。この調査対象変数について、測定結果を示す資料上の実測値は確認していない。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:2164-2171, 2185-2187, 2268-2296, 2361-2395`
- `engine/src/inkling2/cuda/ink_runner.cuh:470-522, 1342-1401, 3684-3695, 3813, 3860-3864`
- `terminal/data/settings-register.json:17783-17793`
