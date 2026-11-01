# `STRATA_PIPELINE_DOOM_SKIP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の投機 decode で、前の window の検証結果により誤りと判定された投機 window（`D`）の残りの layer を、expert pool に依頼せず空の plan で進めるかを制御します。skip すると stage 0 の処理を早く終え、window の結果を捨ててから GDN snapshot を復元し、確定した window の commit を実行します。誤った投機 window は最終的に使われないため、これはその破棄までの処理量を変える設定です。

## 値と判定

値は `std::atoi()` に渡され、戻り値が 0 かどうかで判定されます。文字列全体の妥当性検査はありません。さらに `pipe_dbg_env()` が `STRATA_PIPELINE_DEBUG` を先に確認します。

| `STRATA_PIPELINE_DEBUG` | `STRATA_PIPELINE_DOOM_SKIP` | `doom_skip` | 結果 |
|---|---|---:|---|
| 未設定、空、または先頭が `0` | 任意（この helper 経由では値を読まない） | true（既定） | doomed window を skip |
| helper の判定が有効 | 未設定 | true（既定） | doomed window を skip |
| helper の判定が有効 | `atoi()` が 0 以外（例: `1`, `-1`, `1abc`） | true | doomed window を skip |
| helper の判定が有効 | `atoi()` が 0（例: `0`, `0abc`, 空文字、`abc`） | false | doomed window も通常どおり serve |

helper の判定は値が未設定・空文字なら無効、先頭文字が `0` なら無効、それ以外なら有効です（`false` も有効）。`atoi()` は先頭の空白と符号を受け付け、先頭の整数部分を変換します。したがって `" 0x1"` は 0、`" 1tail"` は 1 です。数値変換不能の場合も 0 になります。

注意点として、`STRATA_PIPELINE_DEBUG` を無効にすると helper が対象変数を `nullptr` として返すため、この設定は既定の `true` として扱われます。skip を止めるには helper のゲートを有効にしたうえで、対象変数の `atoi()` 結果を 0 にする必要があります。

根拠: `src/program/generate.cpp:461-467,16198-16201`、`sycl/src/program/generate.cpp:298-303,11171-11176`。

## 有効になる条件

- `--pipeline-windows` による pipeline が使われ、decode ループが実行されること。CUDA/HIP 側では `pipe` が有効で、`pl_pw >= 2`、snapshot が利用可能であることが decode pipeline の入口条件です。
- `pl_pw` は通常 `--pipeline-windows` の値ですが、`STRATA_PIPELINE_DEBUG` が有効で `STRATA_PIPELINE_SWITCH` のファイルが開ける場合、そのファイルの `pw=` が request ごとに `pl_pw` を 0〜2 に上書きします。したがって switch file は decode pipeline の入口条件に影響しますが、`STRATA_PIPELINE_DOOM_SKIP` 自体の値判定は別です。
- その request が pipeline を serial に戻す条件に該当しないこと。少なくとも repetition penalty（`penalty_last_n`）がある場合と coupled draft sampling の場合は serial decode になります。また cancel 済み、または生成上限到達済みの request も pipeline に入りません。
- `B` が投機 launch 済みで、検証 window `A` の結果が B の推測と一致しない（または生成終了となる）こと。このとき `B` を `D` とし、`doomed` を立てます。推測が正しく確定した window にはこの skip は適用されません。

この設定に OS 固有または追加の build macro による判定はありません。実装上、CUDA/HIP 用 `src/program/generate.cpp` と SYCL 用 `sycl/src/program/generate.cpp` に同じ判定があります。CLI と switch file は pipeline 経路を選ぶ条件を変えますが、doom skip 値を上書きしません。環境変数値を子プロセスへ転送する処理は確認できませんでした。

根拠: `src/program/generate.cpp:10001,14777-14800,16079-16099,16645-16664`、`sycl/src/program/generate.cpp:10431-10452,11680-11691`。CLI の pipeline 条件と制約は `docs/MULTI_GPU.md:176-197` にも説明があります。

## 実行時の詳細

`STRATA_PIPELINE_DOOM_SKIP` は `pipe_dbg_env()` の名前引数として渡されるため、直接参照は CUDA/HIP と SYCL に各 1 箇所です。両 backend の helper は `STRATA_PIPELINE_DEBUG` を関数内 static bool に一度だけ保存し、ON のときだけ要求された名前を `getenv()` します。`doom_skip` も `pump0()` 内の static const bool で、最初の対象 window の service 時に一度評価されます。以降の request やプロセス実行中の環境変更では再評価されません。

skip 条件が成立すると `Verifier::service()` に null の pool callback を渡します。Verifier は callback を呼ばず、pool が plan を公開しなかった layer について空の plan を設定して次へ進めます。skip しない場合は `drive_pool_split` を呼び、通常の expert service を行います。D が完了すると、その投機結果は出力に使わず、snapshot を戻して確定済み window の commit をやり直します。

この環境変数専用のログや警告はありません。通常の成功経路では `T ...` が確定した token を出力します。Verifier が layer の doorbell を受け取れない場合は `verify: layer ... never rang (...)`、20 秒超の待機では `verify: timed out at layer ...`、window 完了待ちでは `verify: the window never finished` をエラーにし、pipeline loop の失敗処理が stderr に `strata serve: pipelined decode: ...`、stdout に `ERR ...` を出して終了コード 1 を返します。これらは skip 設定固有の失敗ではなく、同じ Verifier / pipeline loop の失敗経路です。

根拠: `src/program/generate.cpp:16193-16208,16392-16424,16651-16664`、`src/core/verify.cpp:4975-5001`、`sycl/src/program/generate.cpp:11168-11183,11396-11432`、`sycl/src/core/verify.cpp:3940-3965`。

## 根拠

- `src/program/generate.cpp:461-467` — `STRATA_PIPELINE_DEBUG` helper の値判定と、ゲート無効時に対象名を読まない動作。
- `src/program/generate.cpp:16079-16099` — CUDA/HIP decode pipeline の入口と serial fallback 条件。
- `src/program/generate.cpp:14777-14800`、`sycl/src/program/generate.cpp:10431-10452` — `STRATA_PIPELINE_SWITCH` による request ごとの `pl_pw` 上書き。
- `src/program/generate.cpp:16193-16208` — doom skip の一度限りの値判定と null pool callback。
- `src/program/generate.cpp:16651-16664,16404-16424` — 推測失敗時の `D` 化、snapshot 復元、確定 window の commit。
- `src/core/verify.cpp:4975-5001` — callback がない場合の空 plan と layer の進行。
- `sycl/src/program/generate.cpp:298-303,11168-11183,11680-11707` — SYCL 側 helper、判定、doomed window の処理。
- `sycl/src/core/verify.cpp:3940-3965` — SYCL 側 callback と空 plan の処理。
- `docs/MULTI_GPU.md:176-197` — pipeline windows の動作、適用条件、debug gate の記載。性能値はこの環境変数の効果として本書では扱っていません。
