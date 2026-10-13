# `STRATA_PIPELINE_FORCE_MISS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`--serve` の layer-split パイプライン decode で、次の speculative window の先頭候補 token を意図的に誤らせる診断用フックです。正常な出力を設定するための変数ではありません。CUDA/HIP 実装と SYCL 実装の両方に同じ判定・注入処理があります。

## 値と判定

値は `pipe_dbg_env("STRATA_PIPELINE_FORCE_MISS")` 経由で取得し、存在する値を `std::atoi` で変換した後、`std::max(0, ...)` で負値を 0 にします。文字列全体の検証はありません。

| 状態 | `pl_force_miss` |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効、または FORCE_MISS が未設定 | 0 |
| 空文字、整数 prefix を含まない文字列 | 0 |
| 正の整数として読める文字列 | その整数（例: `2`, `2tail` は 2） |
| 0 または負数 | 0（負数は clamp） |

`atoi` は先頭の空白と符号を許し、最初の数字列の後ろは無視します。小数や基数接頭辞の parse、大小文字の判定はありません。数値として変換できない文字列をエラーにはせず 0 にします。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。実装上は unset、空文字、または先頭文字が `0` の場合は無効で、それ以外の非空値は有効です。したがって `STRATA_PIPELINE_DEBUG=1` に限らず `true` などもゲートを開きます。
- layer split の `--serve` でパイプライン decode が実際に走り、draft chain から次の window `B` が作られること。通常の serial decode、パイプラインを使わない実行、`--pipeline-windows 1` の短い prompt-read 経路では token の注入は起きません。
- `STRATA_PIPELINE_SWITCH=<file>` が有効で、パイプラインが稼働中にそのファイルを開ける場合、ファイル内の `force_miss=<値>` が環境変数から得た値を上書きします。このフィールドも `atoi` 後に 0 未満を 0 にします。

## 実行時の詳細

`pipe_dbg_env` は `STRATA_PIPELINE_DEBUG` の有効・無効を関数内の `static const bool` に初回呼出し時キャッシュします。その呼出し後にゲート変数を変更しても反映されません。一方、`STRATA_PIPELINE_FORCE_MISS` 自体は request ごとのローカル値として読み、request 中に値を変更してもその request の値は変わりません。

パイプラインの chain から次 window `B` を作るたびに、`B` が作成可能ならカウンター `pl_fm` を増やします。`pl_force_miss > 0` かつカウンターがその倍数になる場合、`B.tok[0]` を `0` なら `1`、それ以外なら `0` に置き換えます。つまり値 `k` は、作成できた `B` のうち k 個ごとに一個、先頭候補を強制的に不一致にします。`pl_fm` は decode pipeline の実行ごとに初期化されます。

この候補は verifier に渡されます。直前 window の verdict と候補が一致しないと、speculative な `B` の出力を採用せず、実行済み stage の snapshot を戻して直前 window の commit を実際の受理数で再実行します。変数は rollback 経路を試す目的であり、この経路が正常に完了すれば強制した誤候補自体は出力されません。カウンター集計は `--decode-timing` 時に `rolled back` として stderr に表示されます。`STRATA_PIPELINE_SWITCH` ファイルを開けた場合は stderr に `strata pipeline switch: ... force_miss=<値> ...` が出ます。

## 文書との照合

`docs/MULTI_GPU.md` は、この値を `STRATA_PIPELINE_DEBUG=1` で読む test/tuning 変数として説明し、全 guess を誤らせた試験例を記録しています（同文書の測定条件では `STRATA_IQ_MT_MIN=1 --pcie-frac 0 --adapt-every 0`）。ただし、値の現行 parse とゲートの厳密な条件は以下のコードを根拠とします。資料中の試験結果を今回再測定したものではありません。

## 根拠

- `src/program/generate.cpp:251-257`: debug gate と環境変数取得 helper。
- `src/program/generate.cpp:10655-10678`: request ごとの値取得、switch-file による override とログ。
- `src/program/generate.cpp:11305-11314,11345-11352,11445-11460`: pipelined decode の実行条件、counter、候補 token の反転。
- `src/program/generate.cpp:11805-11829,11875-11885,11937-11946`: verifier verdict、採用判定、rollback と timing ログ。
- `sycl/src/program/generate.cpp:293-298,9905-9929,10514-10516,10638-10653`: SYCL 側の対応する helper、値取得、override、候補 token の反転。
- `docs/MULTI_GPU.md:302-312`: パイプラインと forced-miss 試験、および tuning/test 変数についての説明。
