# `STRATA_PIPELINE_LOOKUP_PON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

2 段以上の speculative pipeline で、suffix lookup から作る次 window `B` に付ける「直前 window が採用される」推定値 `B.p_on` を指定します。これは lookup の一致判定や token 自体を変える値ではなく、`B` を先行実行するかどうかの閾値判定に使われます。CUDA 実装と SYCL 実装の両方に読み取りがあります。

この名前は候補一覧だけでなく、両実装の実行コードから `pipe_dbg_env("STRATA_PIPELINE_LOOKUP_PON")` として読まれます。読み取りは `STRATA_PIPELINE_DEBUG` による debug helper のゲートを通ります。

## 値と判定

| 状態 | `pl_lookup_pon` | 結果 |
|---|---:|---|
| `STRATA_PIPELINE_DEBUG` が無効 | 0.75 | 対象変数は helper から見えず、設定値を使わない |
| debug 有効、対象変数 unset | 0.75 | 既定値 |
| debug 有効、対象変数が数値文字列 | `(float) std::atof(value)` | `atof` の変換結果を float にして使用 |
| debug 有効、空文字または数値に変換できない文字列 | 0.0 | `atof` の結果が 0 となり、lookup 由来の `B` は作られない |

`std::atof` を使い、値全体の検証、エラー報告、範囲 clamp はありません。数値の後ろに余分な文字があっても数値部分が変換されます（例: `0.6junk` は 0.6）。負数・0 は `pl_lookup_pon > 0.0f` を満たさず、lookup 由来の `B` を無効にします。正数は 1 を超えてもそのまま `B.p_on` に入り、0〜1 に制限されません。

`STRATA_PIPELINE_DEBUG` は未設定・空文字・先頭文字が `0` の場合は無効です。それ以外の非空値なら有効であり、`1` という文字列に限定されません。helper 内のこの判定は `static` で初回に cache されます。対象値の読み取り結果も `pl_lookup_pon` の `static const float` に cache されるため、実行中に環境を書き換えても再評価されません。

根拠: CUDA `src/program/generate.cpp:461-467,16316-16321`、SYCL `sycl/src/program/generate.cpp:300-303,11328-11333`。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。無効なら対象変数の設定値は無視され、0.75 が使われます。
- `--serve` で起動し、pipeline windows が有効であること。`--pipeline-windows` は明示指定でき、未指定時の自動選択もあります。CUDA は異なる GPU 上の layer split を使い、pipeline の実体が 2 段以上である必要があります。SYCL の `pipe` は別 GPU のちょうど 2 段を要求します。指定された pipeline が `--serve`、MTP drafter と `--spec >= 2`、batch や helper cache 等の制約を満たさない場合は、stderr に `strata generate: --pipeline-windows ... is off: ...` を出して無効化します。CUDA は 3 段以上にも対応し、SYCL はこの pipeline 実装では 2 段に限られます。
- decode の pipeline-window loop が実際に選ばれること。CUDA/SYCL とも `pl_want` が pipeline、`pl_pw >= 2`、snapshot の準備を要求します。反復 penalty (`hist_n > 0`) または coupled draft sampling の request は serial decode に回ります。
- `pick_lookup` が呼ばれた上で、`--suffix-draft` が正、window が先頭でなく、suffix lookup が一致し (`k > 0`, 最初の lookup token が chain の先頭 token と一致)、`DraftPolicy` が lookup を選ぶこと。さらに lookup の window `A` より先に続く token が 1 個以上 (`rest >= 1`) 必要です。

CLI の `--pipeline-windows` は pipeline 自体を選びますが、この変数の値を上書きする CLI 引数はありません。`STRATA_PIPELINE_SWITCH` のファイルから各 request で読める項目は `pw`、`theta`、`force_miss`、`short_read` であり、この変数は含まれません。

根拠: CUDA `src/program/generate.cpp:4970-5020,10000-10005,16079-16100`、SYCL `sycl/src/program/generate.cpp:3420-3463,7325-7329,11029-11049`、両実装の `pick_lookup` 条件は CUDA `src/program/generate.cpp:16322-16349`、SYCL `sycl/src/program/generate.cpp:11334-11360`、switch は CUDA `src/program/generate.cpp:14777-14801` と SYCL `sycl/src/program/generate.cpp:10428-10451`。

## 実行時の詳細

pipeline の loop に入る際に `pl_lookup_pon` を初回評価します。lookup で `A` の後続部分が得られた場合、値が正で `b_done` が false なら、残りの lookup token から `B` を作り、`B.p_on` にこの値を設定して `B.ready` と `B.made` を立てます。0 以下ならこの経路で `B` を作りません。

作られた `B` も必ず実行されるわけではありません。stage 0 では `B.p_on >= theta` かつ `B.p + B.T <= o.max_context` が launch 条件です。CUDA は複数の front stage がある場合、後続 stage (`st > 0`) ではこの `p_on` 閾値を再確認せず進めます。CUDA の `STRATA_PIPELINE_PRESTAGE` が有効なら stage 0 の pre-stage にも同じ閾値が使われます。誤った speculative window は後で判定され、該当する speculative 処理を巻き戻す経路があります。

`STRATA_PIPELINE_LOG` が有効な場合、stderr に `strata pipeline: chain ... B T=... p_on ...` が出ます。pipeline trace を指定している場合は `CD` event に `B.p_on * 1000` を整数化した値が記録されます。採用率の calibration は `B.made` の window について計数し、decile の添字は 0〜9 に clamp します。対象値が無効・不正でも専用の警告や終了経路はなく、前述の `atof` 結果と launch gate に従います。

根拠: CUDA `src/program/generate.cpp:16337-16349,16496-16505,16522-16560,16603-16609`、SYCL `sycl/src/program/generate.cpp:11349-11360,11504-11513,11526-11562`。helper の cache は CUDA `src/program/generate.cpp:464-466`、SYCL `sycl/src/program/generate.cpp:300-302`。

## 根拠

- 全完全一致参照は CUDA `src/program/generate.cpp:16316,16319` と SYCL `sycl/src/program/generate.cpp:11328,11331`。いずれも読み取り実装であり、他の helper 呼び出し箇所にこの名前を動的に渡すものはありません。
- `docs/DETAILS.md` にこの変数名の説明は見つかりませんでした。候補一覧 `docs/envvars/000_envvers.md` には名前がありますが、挙動の根拠は上記ソースコードです。
