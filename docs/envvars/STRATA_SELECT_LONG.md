# `STRATA_SELECT_LONG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査対象 checkout は `## main...origin/main` で、作業ツリーに未コミット変更はなかった。

## 役割

CUDA 検証器の QSA 選択で、長い context の decode window に別の block-score / top-k 経路を使う opt-in スイッチ。通常経路と選択 ID・スコア bit は同じとソースコメントに記されている。値を有効にすると閾値以上の window 用に別の CUDA graph 群を保持するため、閾値未満の window は通常 graph のまま。対象は検証器の window decode で、batch-row の選択は明示的に通常の one-CTA 経路を使う。`STRATA_SELECT_LONG` 自体は CLI 引数ではなく、`Verifier` の共通 env 読み取り関数で評価される（`engine/src/core/verify.cpp:195-212,2266-2276,4684-4689`）。

## 値と判定

`std::getenv` の結果が null でなく、かつ先頭文字が `'1'` のときだけ要求を有効とする。文字列全体の比較や数値変換はしない。したがって空文字、`0`、`true`、`01` は無効だが、`1`、`10`、`1anything` は要求として有効。空白を含む場合も先頭文字だけを見るため、` 1` は無効。設定有無だけで動かす判定ではない（`engine/src/core/verify.cpp:200-210`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| 通常の読み取り | `select_long_on()` は false | `1`, `10`, `1anything` | 空文字、`0`, `true`, `01`, ` 1` |
| `select_long_on()` が呼ばれる build に `STRATA_EXPERIMENTAL_SM60` がない（HIP など） | false、警告なし | `1` で要求を検出するが無効化し、警告を一度出す | 上段と同じく false、警告なし |
| 同一 compute capability の NVIDIA GPU 群が sm_70 で、起動時に `STRATA_SM70_PERF=0` / `STRATA_DEFAULTS=026` 等で既定セットを除外していない | 既定設定処理が unset を `1` にする | ユーザーが設定した値はそのまま上段の規則で判定 | ユーザーが空文字や `0` を設定すれば無効 |

## 有効になる条件

- `STRATA_SELECT_LONG` が上記の先頭文字判定を通ること。関数内 `static` に結果をキャッシュするため、実行中に環境を変更しても再評価されない（`engine/src/core/verify.cpp:200-212`）。
- `qsa_topk_multi_scratch_ints(1) > 0` であること。multi-CTA カーネルを含む CUDA build（`STRATA_ENABLE_CUDA` かつ CMake の `STRATA_EXPERIMENTAL_SM60`）でなければならない。非対応 build では要求が無視される（`engine/cmake/strata_gpu_engine.cmake:14-16`; `engine/src/kernels/cuda/qsa_select.cu:3219-3227`）。
- window の終端 cell `pos0 + T` が `STRATA_SELECT_LONG_AT` 以上であること。閾値は別の環境変数で、未設定または空文字なら 65,536、非空なら `std::atoll` で変換する。`0` は常時対象、負値も比較上すべての通常 window を閾値以上にする。変換不能文字列は `atoll` の結果 0 となる。これは long switch が有効なときだけ window 選択に使われる（`engine/src/core/verify.cpp:213-219,3710-3714,3837-3839`）。
- 検証器が通常の単一 window QSA 経路を実行すること。batch capture 中は `sel_long_ = 0` とし、batch rows では長文脈分岐を通らない（`engine/src/core/verify.cpp:2200-2276,4677-4690`）。
- 長経路 wrapper 内の高速カーネルにも条件がある。top-k multi-CTA は `STRATA_TOPK_OLD` が未設定、呼び出しが 1〜`MT_MAXQ` query、active count なし、QSA block 幅・選択容量の条件を満たす必要がある。`STRATA_TOPK_MULTI=0` なら無効、正の整数ならカード条件を問わず有効、unset / 空文字なら compute capability 6.x（または `sm70_default_on`）で register kernel の到達範囲を超える場合に有効。これらを満たさない場合は通常 top-k に戻る。`STRATA_TOPK_MULTI_N` は multi-CTA kernel を選んだ場合の CTA 数を指定し、正値を最大数まで clamp する（`engine/src/kernels/cuda/qsa_select.cu:3174-3196,3200-3205,3230-3245`）。
- shuffle-free score kernel は `STRATA_SCORES_MULTI` の `atoi` 結果が非ゼロであること（unset は有効、空文字や数値変換結果 0 は無効）、QSA shape が一致し query 数が `MQ` 以下であることが必要。`STRATA_SCORES_DX=0` は無効、非ゼロならどの CUDA card でも有効、unset / 空文字なら CC 6.x または `sm70_default_on` の GPU で有効。条件不成立なら通常 score kernel に戻る（`engine/src/kernels/cuda/qsa_select.cu:1607-1609,3108-3132,3248-3257`）。
- 同一 compute capability の可視 NVIDIA GPU 群が sm_70 の場合、起動時の `apply_nv_defaults` がユーザー未設定の環境変数に限り `STRATA_SELECT_LONG=1` を設定する。明示設定は空文字を含め維持される。`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` などで表を除外するとこの既定設定は適用されない。混在 compute capability ではこの一括既定設定を適用しない（`engine/src/program/generate.cpp:4425-4449`; `engine/src/core/nv_defaults.cpp:136-163,222-234`）。

## 実行時の詳細

`select_long_on()` は初回呼び出し時に環境値と build capability を一度評価して static cache する。対応しない build で値が先頭 `1` の場合、stderr に `strata verify: STRATA_SELECT_LONG=1 needs the CUDA build with STRATA_EXPERIMENTAL_SM60; ignored` を一度出して false を cache する（`engine/src/core/verify.cpp:200-212`）。GPU の architecture 判定自体はこの変数では行わず、実際に DX scorer / multi-CTA top-k を使うかは各 wrapper の別条件と `STRATA_SCORES_DX`・`STRATA_TOPK_MULTI` が決める。

対応 build では verifier arena に scratch を確保し、window 終端が閾値以上なら long graph variant を選択する。QSA 選択時には `qsa_block_scores_long` と `qsa_block_topk_long` を呼び、両 wrapper は専用条件が成立しなければ通常の `qsa_block_scores` / `qsa_block_topk` へ fallback する。選択結果を後続の attention が使う流れは通常経路と共通（`engine/src/core/verify.cpp:1205-1208,2266-2276,3831-3846`; `engine/src/kernels/cuda/qsa_select.cu:3230-3257`）。

通常 window graph と long window graph を別々に capture するため、グラフ用 VRAM が増える。pipeline 用 `capture_all` も switch 有効時は両 variant を capture し、各 window の context に応じて launch variant を選ぶ（`engine/src/core/verify.cpp:3254-3262,5909-5917,5964-5974`）。CLI 引数がこの環境値を上書きする処理は確認できなかった。sm_70 自動既定はエンジンが switch を読む前に適用される。既定設定の適用時に stderr へ出る一覧ログは、他の適用 switch と同じ行に `STRATA_SELECT_LONG=1` が含まれる（`engine/src/program/generate.cpp:4425-4449`; `engine/src/core/nv_defaults.cpp:222-255`）。

## ログと測定値

非対応 build で先頭 `1` を指定したときの warning は上記のとおり。対応 build で有効になったことだけを示す専用ログはこの読み取り箇所にはない。kernel launch error 時は専用経路で `qsa_block_topk multi: <CUDA error>` または `qsa_block_scores (dx): <CUDA error>` を stderr に出し、`std::exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:3167-3170,3207-3215`）。

`docs/OLDER_GPUS.md` は四枚の GP100、全 expert VRAM resident、`--pipeline-windows 3`、context 115K で 400 token decode の作者測定を 51.0 → 52.5 tok/s と記し、64K 未満では変化なしとしている。また同文書は未測定と明記している。これは文書に記録された測定であり、本調査で再測定していない（`docs/OLDER_GPUS.md:184-191`）。同資料は専用 parity test がランダムデータで同じ ID / score bits を確認すると記すが、テストは本調査では実行していない（同:186-188）。

## 根拠

- `engine/src/core/verify.cpp:195-219` — 値判定、非対応 build 警告、関連閾値の既定値と cache。
- `engine/src/core/verify.cpp:1205-1208,2200-2276,3710-3717,3831-3846,4677-4690,5909-5917,5964-5974` — scratch 確保、通常 / batch / pipeline の window variant 選択。
- `engine/cmake/strata_gpu_engine.cmake:14-16`; `engine/src/kernels/cuda/qsa_select.cu:1607-1609,3108-3132,3174-3257` — build macro と backend wrapper の fallback 条件。
- `engine/src/program/generate.cpp:4425-4449`; `engine/src/core/nv_defaults.cpp:136-163,222-255` — sm_70 の自動既定と明示値の優先。
- `docs/OLDER_GPUS.md:184-191` — 記載済み測定条件・結果と未測定の注記。
