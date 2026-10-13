# `STRATA_PIPELINE_DOOM_SKIP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の speculative/pipelined decode で、推測が外れて破棄される `D` window の残りの layer を空の計画で処理するかを制御します。既定ではスキップし、CPU expert pool の仕事と GPU の expert 処理を省いて stage 0 と pool を早く解放する意図です。無効にすると `D` を通常どおり最後まで処理します。`D` の出力は採用されず、正しい window の状態へ戻されます。

## 値と判定

`STRATA_PIPELINE_DOOM_SKIP` の値は `std::atoi` に渡されます。文字列全体の妥当性検査はなく、変換結果が 0 なら無効、0 以外なら有効です。環境変数が未設定なら既定で有効です。設定が空、数字で始まらない文字列、または `0`（例: `0junk`）なら無効です。`1`, `-1`, `2tail` は変換結果が非ゼロなので有効です。`atoi` の整数範囲外の入力に対する結果は、コードで別途定義・検査されていません。

この変数を読む `pipe_dbg_env()` は、`STRATA_PIPELINE_DEBUG` が有効な場合に限り指定された環境変数を返します。同変数が未設定、空、または先頭文字が `0` なら helper は `nullptr` を返すため、`STRATA_PIPELINE_DOOM_SKIP` 自体を設定していても設定は無視され、既定の有効になります。debug gate は最初の helper 呼び出し時に static cache され、スキップ値も `pump0` の初回実行時に static cache されます。したがって、プロセス起動後に環境を変更しても反映されません。

| `STRATA_PIPELINE_DEBUG` の初回判定 | `STRATA_PIPELINE_DOOM_SKIP` | スキップ設定 |
|---|---|---|
| unset / 空 / 先頭が `0` | 任意 | 有効（既定） |
| 有効 | unset | 有効（既定） |
| 有効 | `atoi` 結果が 0 | 無効 |
| 有効 | `atoi` 結果が非 0 | 有効 |

## 有効になる条件

- speculative な `--pipeline-windows 2` の decode 経路で動作します。通常の serial decode や pipeline window の speculative decode でない経路では `D` を処理するこの分岐に入りません。
- `D` が起動済みで、直前の window の検証結果により speculative guess が誤り（または終了）と判断され、`doomed` 状態になった場合にだけ有効です。`D` 自体が起動していないとき、または誤り判定前にはスキップしません。
- CUDA と SYCL の `generate.cpp` に同じ判定と `pump0` 分岐があります。HIP 側の別実装はこの環境変数の直接参照検索では確認できません。
- `STRATA_PIPELINE_DEBUG` は他の `STRATA_PIPELINE_*` 調整用環境変数の共通 gate です。無効時、この変数を含む調整値の読み取りは既定値へ戻ります。

## 実行時の詳細

誤った speculative guess の window `B` は `D` に移され、`doomed` が true になります。以後 stage 0 が `D` を pump するとき、スキップが有効なら `Verifier::service()` に null pool を渡します。service は CPU pool callback を呼ばず、host 側で plan が未公開のときは空 plan（counts/start をゼロ）を公開して GPU の layer hand-off を進めます。これにより `D` の残りを空の計画で通します。無効なら通常の `drive_pool_split` callback を渡します。

`D` が終了すると、その window の結果は破棄され、実装は保存した GDN snapshot を戻し、正しい window の commit を再適用して undo を完了します。このためスキップ対象の出力は生成結果に採用されません。ソースコメントは省略によって stage 0 と pool を早く解放すると説明していますが、性能向上の測定値は今回確認した資料にはありません。診断ログをこの変数が直接出す処理もありません。

## 根拠

- `src/program/generate.cpp:251-257` — `pipe_dbg_env()` と `STRATA_PIPELINE_DEBUG` の gate、および調整用変数の説明。
- `src/program/generate.cpp:11419-11434` — `pump0` の static 値判定、null pool / 通常 pool の選択。
- `src/program/generate.cpp:11875-11888` — speculative window を誤り時に `D` として doom 状態にする。
- `src/program/generate.cpp:11618-11619,11630-11650` — doomed window の処理と snapshot/commit の復元。
- `src/core/verify.cpp:3281-3283,3340-3368` — CUDA verifier の pool callback、空 plan の hand-off。
- `sycl/src/program/generate.cpp:293-298,10613-10627,11085-11095` — SYCL 側の同じ gate、判定、doom 処理。
- `sycl/src/core/verify.cpp:3713-3716,3772-3805` — SYCL verifier の pool callback と空 plan hand-off。
- `src/program/generate.cpp:11314` — speculative pipeline loop の有効条件（`pipe && pl_pw >= 2 && pl_snap_ok`）。`src/program/generate.cpp:1883` では CLI の `--pipeline-windows` 値を 0..2 に制限します。
- `docs/DETAILS.md:170-179` — `--pipeline-windows 2` と適応 tier の関連説明。この範囲に `STRATA_PIPELINE_DOOM_SKIP` 固有の説明・測定値はありません。
