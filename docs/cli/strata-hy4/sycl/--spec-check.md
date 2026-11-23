# `--spec-check`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--spec-check` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

DFly2 による speculative decoding の greedy 検証後、受理された各行を1トークンずつ再計算し、バッチ検証で得た logits とビット単位で比較する診断用フラグです。通常の生成結果を検査するため、speculative decoding が有効な実行で使います。parser は `SpecCfg::check` を `true` にするだけで、引数値や回数の validation はありません（`engine/src/hy4flash/sycl/sy_main.cpp:180-189`、`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。

## 使い方

```sh
# 単体生成で DFly2 を有効にして照合する
strata-hy4-sycl --model model.strata --tokens prompt.ids --draft dfly2 --gen 32 --spec-check

# serve モードで DFly2 を指定して照合する（入力は engine line protocol）
strata-hy4-sycl --serve --native model.strata --draft dfly2 --spec-check
```

## 値と既定値

値は不要です。未指定時は `SpecCfg::check` の初期値 `false` で、指定すると `true` になります。繰り返し指定しても同じ真偽値を設定するだけです。直後の引数を値として消費しません（`engine/src/hy4flash/sycl/sy_main.cpp:105-116,180-185`、`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。

## 実行時の動作

単体実行では、`--spec-check` によって `HY4S_VRAM_STATIC=1` が設定され、VRAM expert cache の adaptive 動作が無効になります（`engine/src/hy4flash/sycl/sy_main.cpp:298-304`、`engine/src/hy4flash/sycl/sy_vram_cache.h:793-797`）。speculative decode に入るのは `--draft dfly2` かつ `--gen` が正の場合です（`engine/src/hy4flash/sycl/sy_main.cpp:279-280,379-381`）。

照合は speculative 検証で受理された経路について行われます。実装はその経路の各行を1行ずつ再計算し、バッチ検証で得た logits と `memcmp` で比較します。テンソル tap も記録し、logits に差があった場合は最初に差を検出した tap 名と差分数を添えます（`engine/src/hy4flash/sycl/sy_spec.h:239-264,355-388`）。この再計算中は `r.dfly_cap` を一時的に無効化し、終了後に元の値へ戻します。また `cfg.check` が真のときは、plain・speculative 経路とも VRAM cache の適応更新コミットを行いません（`engine/src/hy4flash/sycl/sy_spec.h:355-390,191-198,220-230,398-408`）。

serve モードでは parser の設定が `ServeOpts::spec` に渡り、DFly2 の `Spec` に適用されます（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:303-308`）。照合が走るのは実際に speculative 経路を使うリクエストに限られ、DFly2 が有効で、生成上限が正、画像入力がない場合です（`engine/src/hy4flash/sycl/sy_serve.h:248-279,464-472`）。さらに `Spec::run` は確率サンプリングモードでは `cfg.check` の照合ブロックを通らないため、greedy 以外のサンプリングや penalty を伴う場合は照合されません（`engine/src/hy4flash/sycl/sy_spec.h:153-161,355`）。

## 適用条件と副作用

- `--draft off`、生成なし、単体実行で `--draft dfly2` 以外、または serve リクエストで speculative 経路が使われない場合、比較処理は行われません。
- 確率サンプリング（greedy でない設定、または penalties 有効）では比較されません。serve では画像リクエストも speculative 経路の対象外です（`engine/src/hy4flash/sycl/sy_spec.h:159,355`、`engine/src/hy4flash/sycl/sy_serve.h:464-472`）。
- 再計算と logits/tap の転送が追加されるため、照合対象の decode 処理が増えます（`engine/src/hy4flash/sycl/sy_spec.h:355-388`）。単体実行では加えて VRAM cache の adaptive 動作を無効にします。
- serve モードでは `HY4S_VRAM_STATIC` をこのフラグから設定するコードは確認できません。ただし `Spec::run` 内の cache commit は `cfg.check` により抑止されます（`engine/src/hy4flash/sycl/sy_spec.h:191-198,220-230,398-408`）。

## 出力とエラー

比較した logits に不一致があれば stderr に `[spec-check] MISMATCH ...` を出力します。20行ごとに確認行数と累積不一致数も stderr に出し、最後に `[spec-check] done (mismatch lines above, if any)` を出します（`engine/src/hy4flash/sycl/sy_spec.h:371-392,414-415`）。不一致そのものは `finish="error"` にせず、専用の失敗終了コードにも結び付けていません。再計算の `forward_chunk` が失敗した場合は `finish="error"` となり、単体実行は `spec: ...` を stderr に出して終了コード 1、serve は `ERR spec: ...` を protocol stdout に出して終了コード 1 になります（`engine/src/hy4flash/sycl/sy_spec.h:360-365`、`engine/src/hy4flash/sycl/sy_main.cpp:386-391`、`engine/src/hy4flash/sycl/sy_serve.h:470-476`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:180-189` — root 引数 parser における `--spec-check` の登録。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30,153-161,355-415` — 既定値、確率モード判定、再計算・bitwise 比較、診断出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,279-300,379-408` — serve への設定転送、単体実行の適用条件と副作用。
- `engine/src/hy4flash/sycl/sy_serve.h:248-279,303-308,464-476` — serve の DFly2 適用条件、設定利用、speculative リクエスト処理。
- `engine/src/hy4flash/sycl/sy_vram_cache.h:793-797` — `HY4S_VRAM_STATIC` が cache の adaptive 状態を決める箇所。
