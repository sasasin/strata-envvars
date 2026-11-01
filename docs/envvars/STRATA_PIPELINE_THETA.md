# `STRATA_PIPELINE_THETA`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`--pipeline-windows 2` の decode で、次の verify window を推測で先行実行する確率しきい値です。直前 window が丸ごと受理される見込み `B.p_on` がこの値以上なら、次 window `B` を stage 0 で speculative に起動します。低い値ほど起動条件を満たしやすく、高い値ほど満たしにくくなります。`STRATA_PIPELINE_DEBUG` が有効でない場合、この環境変数は無視され、しきい値は既定値になります。

## 値と判定

| 状態 | しきい値 |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効 | `0.2`（`STRATA_PIPELINE_THETA` は参照しない） |
| debug 有効、`STRATA_PIPELINE_THETA` 未設定 | `0.2` |
| debug 有効、設定あり | `(float) std::atof(value)` |

値全体の検証や範囲 clamp はありません。空文字や数値に変換できない文字列は `atof` により 0 になります。数値の後ろに文字があれば数値部分を変換します（例: `0.4tail` は 0.4）。負数もそのまま使われ、NaN は比較 `B.p_on >= theta` を成立させません。したがって負値は通常の有限 `B.p_on` に対してゲートを通しやすく、1 を超える値は `B.p_on` が通常取り得る確率範囲ではゲートを通しません。

## 有効になる条件

- `pipe_dbg_env()` が `STRATA_PIPELINE_DEBUG` を有効と判定すること。判定は未設定・空文字・先頭文字 `0` で無効、それ以外の先頭文字で有効です。文字列全体の真偽値 parse はしません。
- パイプライン decode が選択されること。CUDA/HIP 実装では `pipe && pl_pw >= 2 && pl_snap_ok`、SYCL 実装では `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` が必要です。
- 当該 request がキャンセルされておらず、生成上限に達していないこと。また、repetition penalty が設定されている request と coupled draft sampling の request は、パイプライン decode でなく serial decode に回ります。

パイプライン自体は `--serve` と layer split、MTP drafter などを必要とします。NVIDIA 側は `--pipeline-windows 2` の指定が必要です。AMD gfx12 および対応する Intel Arc B-series には条件付き既定有効経路がありますが、条件を満たさない構成ではこのしきい値を設定してもパイプラインは起動しません。詳細なパイプライン条件は `docs/MULTI_GPU.md:181-197` と `src/program/generate.cpp:4970-5020` にあります。

## 実行時の詳細

CUDA/HIP と SYCL の `generate.cpp` は同じ判定を実装しています。`pipe_dbg_env(name)` は `STRATA_PIPELINE_DEBUG` の判定を関数内 `static const bool` に一度だけ cache し、有効時だけ `getenv(name)` を返します。従ってプロセス開始後に `STRATA_PIPELINE_DEBUG` を変えても判定は変わりません。一方、`pl_theta` は request の処理箇所で初期化されるたびに helper 経由で環境値を読み、`std::atof` で float に変換します。

`STRATA_PIPELINE_SWITCH` が debug 有効時に設定され、ファイルを開けた場合、そのファイル内に `theta=` があれば `std::atof` の値で `pl_theta` を上書きします。したがって切替ファイルの `theta=` が環境変数の値より優先します。ファイルパスの環境値ポインタは static 初期化で一度取得されますが、ファイル本文は各 request で開き直されます。CLI に独立した theta 引数はありません。

しきい値は CUDA/HIP の speculative window 起動判定（`B.p_on >= theta`）に加え、debug の `STRATA_PIPELINE_PRESTAGE` が有効な場合の prestage 判定にも使われます。ゲートを下回ると `B.ready` を false にし、below-gate カウンタを増やしてその speculative window を起動しません。SYCL でも speculative 起動条件に同じ比較を使います。

この変数専用の警告・終了経路はありません。`STRATA_PIPELINE_SWITCH` ファイルを開けて値を読めた場合は stderr に `strata pipeline switch: ... theta=...` が出ます。`STRATA_DECODE_TIMING` が有効なら decode の統計行に `below the gate` の件数と `theta` が表示されます。通常の pipeline setup / 実行失敗は `STRATA_PIPELINE_THETA` の値に固有ではありません。

## 根拠

- 候補名の全参照（本番コード）は `src/program/generate.cpp:14782` と `sycl/src/program/generate.cpp:10433`。両箇所とも `pipe_dbg_env` を経由し、他の参照はありません。
- helper の debug 判定、cache と値の取得: `src/program/generate.cpp:461-467`, `sycl/src/program/generate.cpp:298-303`。
- 既定値 `0.2`、`atof` 変換、force miss の隣接設定、switch-file による上書きとログ: `src/program/generate.cpp:14777-14801`, `sycl/src/program/generate.cpp:10428-10452`。
- パイプライン decode の起動条件と request 単位の除外: `src/program/generate.cpp:16079-16100`, `sycl/src/program/generate.cpp:11029-11053`。
- CUDA/HIP の確率ゲート、prestage、ゲート不成立時の処理: `src/program/generate.cpp:16496-16499,16522-16560`。SYCL の speculative 起動ゲート: `sycl/src/program/generate.cpp:11526-11532`。
- decode timing の `theta` と below-gate 件数の出力: `src/program/generate.cpp:16713-16718`。
- パイプライン tuning/test 変数が `STRATA_PIPELINE_DEBUG=1` のときだけ読まれること、および対応条件: `docs/MULTI_GPU.md:181-197`。
