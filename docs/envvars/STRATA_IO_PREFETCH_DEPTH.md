# `STRATA_IO_PREFETCH_DEPTH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

RouterLookahead が現在の層の入力から先読みする層数を指定する。予測した層ごとに router の BF16 重みで expert 候補を計算し、GPU またはホスト RAM にない候補を `ExpertSource::warm`（スコア付き経路では `warm_scored`）へ渡す。これは予測した expert の読み込みを先行させる機能であり、実際に計算する expert の選択は変えない（`engine/include/strata/core/expert_source.hpp:319-343`、`engine/src/core/expert_source.cpp:3740-3758,3789-3792`）。

この変数は RouterLookahead が開始できた場合にだけ深度を変える。主な経路は CUDA/HIP の `generate.cpp` にある GPU 生成・serve 実装で、通常の file tier の prefetch に加え、Foresight swap や lookahead 統計が有効な経路でも lookahead が起動すれば適用される（`engine/src/program/generate.cpp:10292-10338`）。

## 値と判定

コードは `std::getenv` で値を取得し、設定されていて `std::atoi(dv) > 0` の場合だけ `std::atoi(dv)` の結果を `set_depth` に渡す。`atoi` は文字列全体の厳密な数値検証をせず、先頭の空白と符号の後の数字列を変換し、数字列の後ろは無視する。数字に変換できない場合は 0 となる。`set_depth` は受け取った整数を 1〜4 に clamp する（`engine/src/program/generate.cpp:10323-10326`、`engine/include/strata/core/expert_source.hpp:341-344`）。

| 条件 | unset | 設定時に深度が明示される値 | 非正数・変換できない値 |
|---|---|---|---|
| lookahead 開始時。file tier の `src.io_prefetch()` が有効、または `--ssd-experts` の場合 | 既定深度 2 | 正の `atoi` 結果。1 は 1、2 は 2、4 以上は 4 | 明示値としては使わず、条件が満たされれば既定深度 2 |
| lookahead 開始時。上記条件を満たさない場合 | `RouterLookahead` の初期値 1 | 正の `atoi` 結果。1〜4 に clamp | 深度 1 のまま |
| GPU cache 全常駐で file-tier 既定 lookahead を外し、後に再接続する場合 | `STRATA_IO_PREFETCH` が有効なら深度を 2 に設定 | 深度値を再 parse せず、lookahead の現在の深度を保つ | 設定ありとして扱われるため、再接続時の既定深度 2 設定を抑止し、現在値を保つ |

空文字は未設定とは異なり、`getenv` は非 null を返すものの `atoi("")` は 0 なので明示値にはならない。`true` や `false` も数値変換できず 0。`0anything` は 0、`2abc` は 2、`  +5tail` は 5 として扱われ、深度 4 に clamp される。負数は正値判定を通らない。桁あふれなど `atoi` が `int` で表せない入力の結果はこのコードで検査・規定されていない（`engine/src/program/generate.cpp:10323-10326`、`engine/include/strata/core/expert_source.hpp:343`）。

## 有効になる条件

- `RouterLookahead::start` が成功し、`drive.d.lookahead` に lookahead が接続される必要がある。router が全層分取得でき、各 router の重みが期待する BF16 形式・サイズであることなどが必要。取得失敗時は lookahead は開始されず、深度は使われない（`engine/src/program/generate.cpp:10302-10338`）。
- 主な file-tier 経路では `srcp == &src` かつ `src.warms()` が必要。unbuffered read では `warms()` が false になるため、この経路では起動条件を満たさない。Foresight swap (`STRATA_FS_SLOTS` と `STRATA_FS_AHEAD`) または `STRATA_LOOKAHEAD_STATS` による別の起動条件もある（`engine/src/program/generate.cpp:10296-10302`、`engine/include/strata/core/expert_source.hpp:1000-1002`）。
- `STRATA_LOOKAHEAD=0` は lookahead の起動条件を止める。ただし `STRATA_LOOKAHEAD` が未設定の場合、通常 file-tier warming、Foresight swap、統計のいずれかが有効なら起動判定に進む（`engine/src/program/generate.cpp:10288-10303`）。
- 深度 2 の既定条件は、file tier の `src.io_prefetch()` が有効であるか、`--ssd-experts` が指定されていること。どちらもなければ既定深度は 1（`engine/src/program/generate.cpp:10323-10326`）。Linux file-tier I/O prefetch が既定有効になる条件や、`STRATA_IO_PREFETCH` による明示設定は別変数・source 条件で決まるため、この変数だけでは prefetch 自体を有効化しない（同 `generate.cpp:8688-8724`）。
- read-ahead gate が閉じている間、worker は深度設定にかかわらず次の 1 層だけを予測する（`engine/src/core/expert_source.cpp:3700-3702`）。
- 全 expert が GPU cache に常駐して file-tier の既定動作が停止していると、既定 lookahead は切り離され、常駐状態が崩れると再接続される。`STRATA_LOOKAHEAD=1`、Foresight swap、統計有効時などは停止条件が変わる。停止・再接続は `STRATA_FILE_TIER_IDLE` と cache 状態にも左右される（`engine/src/program/generate.cpp:10275-10303,10341-10377`）。

## 実行時の詳細

深度は lookahead の初期化時、`RouterLookahead::start` が成功した直後に環境から読み、`set_depth` へ設定する。環境値そのものや parse 結果を static cache する helper はなく、この設定値はその lookahead インスタンスの状態として保持される。予測の dispatch ごとに `submit` が入力を worker に渡し、worker は `depth_` 回まで層を進めて予測・warming する。先読み先がモデルの層数を越える場合は層数で止まる（`engine/src/program/generate.cpp:10319-10327`、`engine/src/core/expert_source.cpp:3554-3573,3700-3702,3789-3792`）。

GPU cache 全常駐時の再接続経路は `STRATA_IO_PREFETCH_DEPTH` の数値を読み直さず、`getenv` が null かどうかだけ確認する。unset で I/O prefetch が戻った場合は深度 2 を設定し、設定済みなら既に保持している深度を変えない。この存在確認は再接続時に実行されるため、プロセス稼働中に環境を書き換える外部手段があれば再接続時の既定深度設定を抑止し得るが、数値の再 parse はされない（`engine/src/program/generate.cpp:10363-10373`）。

## ログと測定値

この変数の値や設定深度を直接表示するログはない。lookahead 開始時には `strata generate: routing-aware prefetch on ...`、開始失敗時には `strata generate: routing-aware prefetch off (...)` が stderr に出る。GPU cache 全常駐で lookahead を一時的に切り離す場合は `strata generate: routing-aware prefetch off (every expert is in the GPU caches; STRATA_LOOKAHEAD=1 runs it)`、状態変化による停止・再開では `strata serve: ...` のログが出る（`engine/src/program/generate.cpp:10328-10338,10359-10377`）。

lookahead が接続されている場合、終了時の標準出力には `routing prefetch` 行として warmed expert 数・file-tier read のうち warming 済みだった数・predictor 時間・busy 中に skip した層数が表示される。これは深度値そのものを示す計測ではない（`engine/src/program/generate.cpp:25348-25354`）。`docs/DETAILS.md` は `STRATA_IO_PREFETCH_DEPTH` の既定を 2 と記すが、現行コードでは I/O prefetch または `--ssd-experts` 条件下の既定が 2 で、それ以外は 1。実測値は同資料の該当行にこの深度変数固有の条件付き測定として記載されていない（`docs/DETAILS.md:304-317`、`engine/src/program/generate.cpp:10323-10326`）。

## 根拠

- `engine/src/program/generate.cpp:10288-10338` — lookahead の起動条件、全 router 取得後の深度値読み取り、既定値と開始ログ。
- `engine/src/program/generate.cpp:10341-10377` — GPU cache 常駐に伴う lookahead 停止・再接続と、再接続時の環境変数有無確認。
- `engine/include/strata/core/expert_source.hpp:319-344` — lookahead の目的、深度の意味、1〜4 の clamp と初期値。
- `engine/src/core/expert_source.cpp:3554-3573,3700-3702,3789-3792` — 入力の submit、実際の先読み反復、予測 expert の warming。
- `engine/src/program/generate.cpp:25348-25354` — lookahead 接続時に出力する routing prefetch の統計。
