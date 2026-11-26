# `STRATA_LOOKAHEAD_STATS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

非ゼロ値を指定すると、生成処理の RouterLookahead を起動して、次層で予測した expert と実際に GPU cache 外へルーティングされた expert を照合する統計を有効にする。予測器は実際の経路にも接続され、通常の top-k 予測で `ExpertSource::warm`（または scored 対応 source の `warm_scored`）を呼ぶ。したがってコード上は計測だけでなく、利用可能な source への先読みも行う。予測結果で実際に計算する expert の選択を置き換える処理はなく、`ExpertSource` の契約も warm は blob の返却値を変えない先読みとしている。実装は `engine/src/program/generate.cpp` と `engine/src/core/expert_source.cpp` にある（`generate.cpp:10300-10333`, `expert_source.hpp:300-311`, `expert_source.cpp:3789-3792`）。

## 値と判定

`generate.cpp` のラムダ内で `std::getenv` し、値が存在して `std::atoi(v) != 0` のときだけ有効になる。未設定は無効、空文字も `atoi` が 0 を返すため無効。数値全体の妥当性検査や末尾文字の検査はしない。たとえば `1`, `-1`, `1x`, ` 1` は非ゼロとして有効、`0`, `0anything`, `true`, `false`, 空文字、数値に変換できない文字列は無効になる。先頭の空白と符号は `atoi` の変換規則に従う。整数型に収まらない値の扱いはこのコードで検査・規定していない（`engine/src/program/generate.cpp:10301`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の generate 経路で `srcp != nullptr` | 統計なし | `1`, `-1`, `1x` | 空文字, `0`, `0anything`, `true` |
| `srcp == nullptr` | 統計なし | なし（環境変数値が非ゼロでも機能条件を満たさない） | すべて |

## 有効になる条件

- `generate.cpp` のこの初期化経路に到達し、`srcp` が設定済みであること。ソース選択はファイル source (`src`) または arena source (`arena_src`) を `srcp` に割り当てる経路がある（`engine/src/program/generate.cpp:8595-8597`, `8742-8745`, `8747-8748`, `8972-8974`）。環境変数判定にサーバー専用の条件はない。
- `STRATA_LOOKAHEAD` が未設定、または `atoi` で非ゼロであること。`STRATA_LOOKAHEAD=0`、空文字、数値に変換できない文字列は初期化条件を止める。これは stats が有効でも同じ（`engine/src/program/generate.cpp:10288-10290`, `10301-10304`）。
- 全層の `ffn_gate_inp.weight` を見つけ、BF16-in-F32 形式と期待 byte 数に合致し、GPU からの `cudaMemcpy` が成功すること。どれかが失敗すると予測器は開始されず、stderr に `strata generate: routing-aware prefetch off (the routers are not BF16 in the arena)` が出る（`engine/src/program/generate.cpp:10304-10318`, `10334-10338`）。
- `STRATA_LOOKAHEAD_K` は予測 top-k を指定する別設定で、未設定時 10、設定時 `atoi` 値を使い、予測器側で 1..`n_expert` に clamp する。0 や負値でも 1 に clamp される（`engine/src/program/generate.cpp:10319-10322`, `engine/src/core/expert_source.cpp:3534-3544`）。
- `STRATA_FS_SLOTS` が `atoi > 0` で、かつ `STRATA_FS_AHEAD` が未設定または `atoi != 0` の場合は Foresight 経路も有効になる。これは stats とは独立の lookahead 起動理由であり、stats が有効なら cold source でも `RouterLookahead::start` を許可する（`engine/src/program/generate.cpp:10296-10303`, `10319-10322`; `engine/src/core/expert_source.cpp:3534-3537`）。
- `STRATA_IO_PREFETCH_DEPTH` が存在し `atoi > 0` なら予測深度を設定し、予測器側で 1..4 に clamp する。そうでなく file source の I/O prefetch または `--ssd-experts` が有効なら深度 2、それ以外は既定の深度 1（次層）となる（`engine/src/program/generate.cpp:10323-10326`, `engine/include/strata/core/expert_source.hpp:341-344`）。
- `STRATA_IO_PREFETCH` は `la_asked` の判定に使われる。空でない非ゼロ値なら lookahead が要求された扱いになるが、空文字・未設定・ゼロ相当は要求扱いにならない（`engine/src/program/generate.cpp:10288-10290`）。stats が有効な場合、GPU cache が全 expert を保持していても `la_stats` 条件により lookahead の接続を外す分岐を通らない（同 `:10328-10333`, `:10359`）。

## 実行時の詳細

環境変数は `engine_main` 内の初期化ブロックで `getenv` から評価され、関数内 `const bool` に保持される。`static` cache ではない。値を再評価するのはこの初期化ブロックが再度実行されたときであり、既に初期化済みの予測器に対するプロセス内の環境変更を反映するコードはない（`engine/src/program/generate.cpp:3668`, `10300-10303`）。

stats が true だと `srcp` が warm を提供しない source でも起動条件に入り、`start(..., fs_ahead || la_stats)` により cold source 許可を渡す。RouterLookahead は router weight をホストへコピーし、起動した worker thread が次層の予測を行う。統計有効時は通常の `k` に加え `k+4` と `k+10` までの予測集合、および各 token の上位予測への投票を記録する。dispatch 側は、実 routing から GPU cache 非 resident の expert 集合を作って予測と照合する（`engine/src/program/generate.cpp:10304-10322`, `engine/src/core/expert_source.cpp:3575-3584`, `3740-3763`, `3765-3787`, `engine/src/core/expert_source.cpp:5436-5442`, `3587-3603`）。

予測 worker は lookahead 対象を `warm_scored` または `warm` に渡す。FileExpertSource は source の設定に応じて先読み stamp、I/O enqueue、または OS のページ先読み要求を行い得る。基底 `ExpertSource::warm` は no-op なので、すべての source で I/O が起きるわけではない（`engine/src/core/expert_source.cpp:3789-3792`, `3467-3505`, `engine/include/strata/core/expert_source.hpp:300-311`）。実際の expert routing は別途dispatchされ、統計はその結果を観測する（`engine/src/core/expert_source.cpp:5436-5442`, `3587-3603`）。

## ログと測定値

予測器の開始に成功すると stderr に `strata generate: routing-aware prefetch on (the next layer's router, file tier)`、または Foresight が有効なら `strata generate: routing-aware prefetch on (the next layer's router, feeding the Foresight swap space)` が出る。router 読み込み・形式・コピー失敗時は前節の `off (...)` 行が出る。GPU cache が全 expert を保持し、stats も Foresight も要求されず lookahead 要求もない場合には「off」の理由行が出るが、stats 有効時はこの切り離し条件を回避する（`engine/src/program/generate.cpp:10320-10338`）。

最後の層まで進んだ verify window が100回ごとに stderr へ `strata lookahead stats:` 行を出す。行には集計 window 数、予測なしの層数、実際の非 resident expert 数、predictor thread 時間、k / k+4 / k+10 の recall・precision・予測数、および投票 top 4/8/12 の coverage が含まれる。100 window に達する前はこの統計行を出さない（`engine/src/core/expert_source.cpp:3643-3667`）。`docs/DETAILS.md:364-368` は100 windowごとの測定と CPU コストを記す一方、現行コードでは上記の通り予測器の接続と source warm も行う。

## 根拠

- `engine/src/program/generate.cpp:10288-10339` — lookahead 関連環境変数、起動条件、router 読み込み、統計初期化、ログ。
- `engine/src/core/expert_source.cpp:3534-3549` — source / router 条件、k の clamp、worker 起動。
- `engine/src/core/expert_source.cpp:3575-3667` — 統計初期化、実 routing との照合、100 window ごとの出力。
- `engine/src/core/expert_source.cpp:3700-3793` — predictor 計算、統計用 top-k、source warm。
- `engine/src/core/expert_source.cpp:5436-5442` — dispatch 時の採点と予測 submit。
- `engine/src/core/expert_source.cpp:3467-3505`, `engine/include/strata/core/expert_source.hpp:300-311` — FileExpertSource の warm 処理と source 共通 warm 契約。
- `docs/DETAILS.md:364-368` — stats の説明。
