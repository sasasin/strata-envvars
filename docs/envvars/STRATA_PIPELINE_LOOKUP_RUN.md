# `STRATA_PIPELINE_LOOKUP_RUN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--serve` の multi-GPU layer split で decode 用 `--pipeline-windows 2` が実際に動くとき、lookup continuation の次に続く speculative window の候補を suffix lookup から作る opt-in です。未設定または無効値では、その位置の候補を MTP chain から作ります。これは speculative window の候補生成経路を切り替える設定で、lookup の有効化そのものではありません。実装は `engine/src/program/generate.cpp` の request 処理内です（20167-20173, 21704-21715, 22361-22405）。

直接の読み取りは `std::getenv` であり、`STRATA_PIPELINE_DEBUG` を介する `pipe_dbg_env` は使いません。したがって、この変数自体に `STRATA_PIPELINE_DEBUG=1` は必要ありません（679-685, 20169-20173）。候補名の全参照は、この読み取りと実装コメント、および `terminal/data/settings-register.json` の登録です。登録は CUDA/HIP backend・`parse: int`・未設定を default とする metadata で、`status` は `research`、追加の runtime read / set / launch は記録されていません（同 JSON 32431-32459）。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果が 0 以外なら有効です。文字列全体の妥当性は検査しません。未設定は false、空文字・数値に変換できない文字列・`0` で始まる数値は false、非ゼロの整数に変換される値（負値を含む）は true です。`atoi` のため、先頭空白や符号を含む数値接頭辞は変換され、後続文字は判定に使われません（例: `" 1tail"` は true、`"0tail"` は false）。`true` / `false` は整数に変換されず、どちらも false になります（20170-20173）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `generate.cpp` の通常読み取り | false | `1`, `-1`, `2tail` | 空文字, `0`, `0tail`, `true`, `false`, `x` |
| `STRATA_PIPELINE_SWITCH` の `run=` 指定が適用された要求 | ファイルに `run=` がなければ上記の値を維持 | `run=1`, `run=-1` | `run=0`, `run=0tail`, `run=x` |

`STRATA_PIPELINE_SWITCH` の `run=` は `std::atoi` の結果で `pl_run` を上書きします。これは `STRATA_PIPELINE_DEBUG` が有効で、switch のパスを得られ、かつ `pipe` が true の場合だけ読み込まれます。ファイルは要求ごとに開き直しますが、switch パスを返す `pipe_dbg_env` の `STRATA_PIPELINE_DEBUG` 判定は関数内 `static` で初回に cache されます（679-685, 20178-20196）。

## 有効になる条件

- `--serve` で各 layer-split stage が別 GPU にあり、multi-GPU split と MTP drafter（`--mtp`）および `--spec` 2 以上が必要です。`--peer-device`、helper cache（`--expert-cache-device1..3` / `--remote-expert-opt`）、非 fallback の DFlash2 draft は併用できません。batch slot 使用時は `STRATA_PW_WITH_BATCH=1` が必要で、その場合も solo request の path に限られます。条件を満たさない明示指定は stderr に `strata generate: --pipeline-windows ... is off: ...` を出して pipeline を無効にします（6556-6576）。
- decode pipeline の分岐は `pipe && pl_pw >= 2 && pl_snap_ok` の場合だけです。`--pipeline-windows 1` ではこの変数の効果はありません。対象要求が penalty history を使う場合、または MTP coupled sampling の場合も serial decode に戻ります（21704-21715）。
- pipeline が GDN state snapshot 用 GPU buffer を確保できない場合も decode は serial のままです。stderr に `strata serve: --pipeline-windows 2: the GDN snapshot of stage ... does not fit; the decode stays serial` を出します（13643-13662）。
- 現在の要求で suffix draft が有効（`o.suffix_draft > 0`）で、lookup が選ばれ、lookup の候補列が続いて lookup B が作られている必要があります。lookup B は `STRATA_PIPELINE_LOOKUP_PON` が正の場合に限り作られます。この別変数は `STRATA_PIPELINE_DEBUG` 経由で読み、未設定時は `0.75` です。`STRATA_PIPELINE_LOOKUP_PON=0` を設定しても debug helper が無効ならその値は読まれず、既定値のままです（21957-21999, 679-685）。
- `STRATA_PIPELINE_LOOKUP_RUN` の既定判定は `STRATA_PIPELINE_SWITCH` の `run=` 値で上書きできます。switch は debug helper 経由なので、その override には `STRATA_PIPELINE_DEBUG` が必要です（20178-20196）。
- パイプライン自動有効化は HIP build に限られ、他 backend では自動で off になります。一方、この変数を読む直接の実装は `engine/src/program/generate.cpp` にだけあります。SYCL 側の `engine/sycl/src/program/generate.cpp` には候補名の読み取りがありません（6532-6544; 候補名の全参照はこの commit の `rg` 走査で確認）。

## 実行時の詳細

値は request 処理内で非 `static` の lambda により読み取られるため、要求ごとに環境を参照し、プロセス内の cache はありません。プロセス実行中に外部から環境を変更した場合の反映は、実行環境自体を変更する仕組みがコードにないため、Strata 側の保証としては確認できません（20169-20173）。

`pl_run` は pipeline decode に入ると `lookup_run` にコピーされます。直前の A 窓が全て受理され、lookup continuation B の先頭候補 token が次の出力 token と一致し、生成が続くとき、true なら `sfx.propose_after(...)` でその lookup の続きから次の候補窓 `nB` を作ります。候補が得られた場合は MTP chain を起動せず `mtp.prefill(...)` で追いつかせ、lookup-run window 数を加算します。false、または lookup-run 候補が作れない場合は、MTP chain を起動して次の窓を構成します（22324-22325, 22361-22405）。

値を読み取る時点はモデル／server の request 処理中ですが、効果は speculative decode 経路に限定されます。pipeline が動かない要求では設定値を読んでも分岐に使われません。コードは pipeline verifier が同じ窓・順序で処理し、通常経路と同じ token を出す旨を記していますが、そこでは `STRATA_IQ_MT_MIN=1` などの条件が明記されています。この文書ではそのコメントの範囲を超えて出力同一性を一般化しません（21700-21705, 22361-22405）。

## ログと測定値

この変数の値が無効・未設定であることを示す専用の警告やエラーはありません。`STRATA_DECODE_TIMING` が設定されている場合、pipeline summary に `lookup-run windows` の件数が stderr 出力されます。この件数は `mtp.prefill` に進んだ lookup-run 窓の数です（21673, 22387-22392, 22476-22488）。snapshot buffer を確保できない場合には、上記のとおり decode が serial に戻る理由を stderr に出します（13656-13662）。

候補窓生成後の `mtp.prefill` または fallback の `mtp.chain_launch` が失敗すると、`die(err)` 経由で通常の pipeline error path に入ります。環境変数自身を理由にした終了経路はありません（22387-22405）。

設定 metadata は、2x RTX A6000、UD-Q4_K_XL、client 1 件、`--pipeline-windows 2`、約 1.9K token の request を 4 件ずつ 3 start した測定として、committed throughput 58.3 tok/s（設定あり）対 58.1 tok/s（未設定）を記録しています。これは register に記録された値で、ここで再測定した結果ではありません（`terminal/data/settings-register.json:32452-32459`）。`docs/MULTI_GPU.md` は pipeline windows の一般的な backend／有効条件を説明しますが、この環境変数の値判定や lookup-run 分岐は記述していません（`engine/src/program/generate.cpp:20167-20169`; `docs/MULTI_GPU.md:182-200`）。

## 根拠

- 候補名と唯一の直接読み取り、整数変換: `engine/src/program/generate.cpp:20167-20173`。
- `pipe_dbg_env` の debug 判定と cache: `engine/src/program/generate.cpp:679-685`。
- switch file による `run=` override とログ: `engine/src/program/generate.cpp:20178-20196`。
- pipeline CLI 条件と無効化ログ: `engine/src/program/generate.cpp:6556-6573`。
- decode pipeline 実行・serial fallback 条件: `engine/src/program/generate.cpp:21704-21715`。
- lookup continuation の生成と lookup-run / chain の分岐: `engine/src/program/generate.cpp:21957-21999`, `22361-22405`。
- timing summary: `engine/src/program/generate.cpp:21673`, `22476-22488`。
- 自動有効化の HIP 条件: `engine/src/program/generate.cpp:6532-6544`。
- 候補一覧 metadata と収録測定条件（実装根拠ではない）: `terminal/data/settings-register.json:32431-32459`。
- 一般的な pipeline windows の文書: `docs/MULTI_GPU.md:182-200`。
