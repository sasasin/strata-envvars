# `STRATA_PIPELINE_SPEC_DEPTH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の layer-split decode で、先行 window の判定を待たずに後続 window B を投機実行する front stage の上限を指定します。対象は pipeline decode の診断・調整用フックで、通常利用者向けの独立した pipeline 有効化設定ではありません。`STRATA_PIPELINE_DEBUG` が有効な場合だけ値が読み取られます。

指定値 `k` は、B を投機実行する front stage の先頭 `k` 段を許可します。たとえば `k=1` なら stage 0 のみ、`k=2` なら stage 0 と stage 1 までです。実際の上限は front stage 数（全 stage 数から最後の stage を除いた数）でも制限されます。未設定時は `1 << 20` が使われ、実在する front stage 数の範囲内で全段が対象になります。

## 値と判定

環境変数の値は `std::atoi` で変換され、その結果と 1 の大きい方が使われます。文字列全体の妥当性は検査しないため、`atoi` が先頭から整数として読める部分だけを変換します。

コードに上限 clamp はありません。`int` で表せない数値文字列は `atoi` の範囲外であり、実装上の安全な値としては扱えません。

| `STRATA_PIPELINE_DEBUG` | `STRATA_PIPELINE_SPEC_DEPTH` | 結果 |
|---|---|---|
| 無効 | 任意（未設定を含む） | helper が `nullptr` を返し、未設定時の既定値 `1 << 20` と同じ扱い |
| 有効 | 未設定 | 既定値 `1 << 20`（全 front stage を許可） |
| 有効 | 正数 `k` | `k`（最初の `k` 個の front stage まで） |
| 有効 | `0`、負数、整数として読めない値、空文字 | 1（`atoi` の結果が 1 未満の場合の下限） |
| 有効 | 整数の後ろに文字が続く値 | `atoi` が読んだ先頭の整数を適用し、1 未満なら 1 |

`STRATA_PIPELINE_DEBUG` は未設定、空文字、または先頭文字が `0` のとき無効です。それ以外の設定値（例: `1`, `true`, `false`）で有効になります。空白、大文字小文字、数値としての妥当性は検査されません。したがって `STRATA_PIPELINE_DEBUG=false` も有効です。`STRATA_PIPELINE_SPEC_DEPTH=0` 自体は投機実行を全停止せず、下限 clamp により 1 段を許可します。

根拠: `src/program/generate.cpp:251-257,11750-11755`。

## 有効になる条件

この値が実際に使われるのは、CUDA/HIP 側の `src/program/generate.cpp` にある pipeline decode ループです。pipeline 自体が要求・利用可能である必要があります。コード上、少なくとも `--serve`、別 GPU に配置された layer split、MTP drafter と `--spec >= 2`、非 batch、peer device なし、helper cache なしが必要です。また投機 decode は `--pipeline-windows 2` 相当（`pl_pw >= 2`）かつ GDN snapshot の確保成功時に限られます。これらを満たさない要求では serial decode 等へ進み、この深さ値は動作に影響しません。

`--pipeline-windows` が自動設定の場合、コードでは HIP のみ gfx12 世代かつ stage 数などの条件に応じて既定で有効化し、CUDA では自動では有効化しません。明示要求時も上記条件に合わない場合は stderr に `strata generate: --pipeline-windows ... is off: ...` を出して pipeline を無効にします。

SYCL 側の `sycl/src/program/generate.cpp` には `STRATA_PIPELINE_SPEC_DEPTH` の読み取りも、この深さ clamp もありません。SYCL 実装へ本変数が適用される根拠は確認できません。

根拠: `src/program/generate.cpp:647-652,3391-3431,7471-7475,11305-11324,11748-11755`; 比較: `sycl/src/program/generate.cpp:293-298`。

## 実行時の詳細

共通 helper `pipe_dbg_env()` は `STRATA_PIPELINE_DEBUG` を関数内 static bool として一度だけ判定し、無効ならこの helper 経由の pipeline tuning/test 値に対して `nullptr` を返します。`STRATA_PIPELINE_SPEC_DEPTH` の数値結果も関数内 static const int に保存されます。そのため両判定が初期化された後にプロセス環境を変更しても再評価されません。深さ値の初期化は投機 decode ループ内で行われるため、そのループに入らなければ候補変数の値は読み取られません。

ループでは各 tick に B の front-stage 番号 `B.fr` を見て、`B.fr < pl_nf` かつ `B.fr < pl_spec_depth` の間だけその stage で B を投機実行します。したがって値は可能な front stage 数を増やさず、先頭から何段を対象にするかだけを狭めます。stage 0 では加えて draft chain の推定 `p_on >= theta` と context 上限の条件を満たす必要があります。後続 front stage はこの特別な確率 gate を使いません。

## 文書との照合

`docs/MULTI_GPU.md` は `SPEC_DEPTH` を含む `STRATA_PIPELINE_*` tuning/test variables が `STRATA_PIPELINE_DEBUG=1` のときのみ読み取られると説明しており、helper の実装と一致します。資料中の pipeline 性能値は本変数の個別効果を測った値ではないため、ここでは `STRATA_PIPELINE_SPEC_DEPTH` の性能効果を記載しません。

根拠: `docs/MULTI_GPU.md:311-315`; `src/program/generate.cpp:251-257,11750-11755`。
