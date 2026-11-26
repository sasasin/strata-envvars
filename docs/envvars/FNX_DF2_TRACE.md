# `FNX_DF2_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

DFlash2 の lane 状態のリセットと drafter の追いつき状況、および drafter 呼び出し時間を stderr に記録する診断フラグ。DFlash2 の計算、draft の選択や生成内容を切り替える分岐ではなく、`df2_forget`、`df2_catch_up`、`df2_draft` のログ出力だけを制御する（`engine/src/split/src/engine_common.cu:1658-1662,1675-1681,1747-1759`）。

## 値と判定

3 箇所とも `static const bool trace = env_flag("FNX_DF2_TRACE")` で判定し、共通 helper は `env_flag` から `env_int(name, 0) != 0` を呼ぶ。未設定なら 0（OFF）。設定時は符号付き base-10 整数として文字列全体を `strtoll` で読み、末尾まで消費され、`long long` 範囲内である必要がある。0 は OFF、それ以外の整数（負数を含む）は ON。空文字、符号だけ、空白、整数以外を含む文字列、範囲外の値は無効であり、例外になる（`engine/src/split/src/env.hpp:15-21,33-39,51-52`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `FNX_DF2` を有効にしてビルドし、対応する DFlash2 経路を実行 | OFF | `1`, `-1`, `+2`, `01`（非ゼロ整数） | `0`, `-0` は有効な整数だが OFF。``, `true`, `0anything`, ` 1`, `1 `, `+`, 整数範囲外は整数として無効 |
| `FNX_DF2` なしでビルド | この変数は読み取られない | 該当なし | 該当なし |

大小文字の概念はなく、`true` / `false` は受け付けない。小数・後続文字・前後空白も受け付けない。別の CLI 引数や環境変数による値の上書きはこの変数の読み取り箇所にはない。なお、`FNX_DF2` なしでは `df2_forget` と `df2_catch_up` が空実装で、`df2_draft` は「this engine was built without DFlash2」を投げるスタブであり、このフラグは読まれない（`engine/src/split/src/engine_common.cu:1762-1767`）。

## 有効になる条件

- `engine/src/split/CMakeLists.txt` で `strata_kernels` と `strata_core` の両 target が存在して `_sp_df2` が ON となり、`strata-split-N` に `FNX_DF2=1` が定義されている build が必要（同ファイル `:104-114,116-150`）。CUDA/HIP の各 split target に対してこの条件分岐がある。
- 実行時に DFlash2 bridge が engine に attach されて `df2_` が設定され、DFlash2 draft 経路が呼ばれる必要がある。batch は MTP draft mode かつ `e_.df2_on()` のとき DFlash2 を draft source として選び、session も `df2_on()` を確認して draft を行う（`engine/src/split/src/batch.cpp:262-267,487-510`; `engine/src/split/src/session.cpp:453-456,565-573`; attach 条件は `engine/src/split/src/engine.cu:1231-1245`）。
- DFlash2 を attach しない実行や、該当メソッドが呼ばれない処理ではログは出ない。DFlash2 の CLI 選択やモデル・pack の用意が runtime 条件だが、この変数自体はそれらを選択・準備しない。

## 実行時の詳細

読み取りはプロセス起動時ではなく、各メソッドの初回呼び出し時に行われる。`df2_forget`、`df2_catch_up`、`df2_draft` にそれぞれ独立した関数局所 `static const bool` があるため、各メソッドは個別に初回評価結果を cache し、その後の環境変更を反映しない。3 箇所の最初の呼び出し前に環境値を変更できる場合は、それぞれの初回値が異なる可能性がある。コード上この変数を設定し直す処理はない（`engine/src/split/src/engine_common.cu:1658-1659,1675-1680,1747-1749`）。

- `df2_forget` は trace が ON のとき、lane を reset する直前に `df2: lane %d forgotten (drafter ring_hi %ld, host ring [%ld, %ld))` を出す。この関数は DFlash2 が attach された場合の state load と reset から呼ばれる（`engine/src/split/src/engine_common.cu:1658-1662,615-637,648-666`）。
- `df2_catch_up` は drafter ring の位置 `have` と次の位置 `pos0` が異なる場合に限り、`df2: lane %d catch-up at %d: drafter ring_hi %ld, host ring [%ld, %ld)` を出す。一致すればログを出さずに戻る。位置の再設定や host ring からの追いつき処理自体は trace の値に関係なく実行される（`engine/src/split/src/engine_common.cu:1675-1697`）。
- `df2_draft` は処理が成功して `last_df2_ms` を算出した後、trace が ON なら呼び出し数と所要時間を lane 数ごとに累積する。400 回ごとに `df2: drafter calls by lanes (mean ms):` に続け、観測した lane 数ごとに平均 wall time と件数を stderr に出す（`engine/src/split/src/engine_common.cu:1722-1759`）。

環境値が非整数の場合、`env_int` は `std::runtime_error` を投げ、例外文言は `FNX_DF2_TRACE: '<値>' is not a whole number`。値を読む各メソッド内にこの例外の処理はない。DFlash2 を利用する `sfnx` の失敗経路では `ERR <例外文言>` と `sfnx: failed: <例外文言>` を出し、終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1094-1103,1121-1135,1160-1166`）。`df2_draft` で初めて不正値を読むのは drafter の処理完了後なので、その呼び出し自体は診断例外で失敗するが、trace OFF のときと同一の結果を返す保証はない。

## ログと測定値

上記の状態ログと400回ごとの平均時間ログは stderr に出る。Strata の資料にはこのフラグの測定値や性能効果は示されていない。`docs/SPLIT_ENGINE.md` は `FNX_DF2_TRACE` をテスター用スイッチとして列挙するのみで、実際の挙動の根拠は上記ソース実装である。

## 根拠

- 値の変換とエラー: `engine/src/split/src/env.hpp:15-21,33-39,51-52`
- 診断ログと DFlash2 無効 build のスタブ: `engine/src/split/src/engine_common.cu:1657-1681,1722-1767`
- build 条件: `engine/src/split/CMakeLists.txt:104-150`
- batch / session の DFlash2 経路: `engine/src/split/src/batch.cpp:262-267,487-510`; `engine/src/split/src/session.cpp:453-456,565-573`
- state load / reset と失敗表示: `engine/src/split/src/engine_common.cu:615-637,648-666`; `engine/src/split/tools/sfnx.cpp:1094-1103,1121-1135,1160-1166`
