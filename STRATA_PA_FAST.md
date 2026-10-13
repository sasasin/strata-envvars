# `STRATA_PA_FAST`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の量子化 KV 向けプロンプト注意カーネルで、query と attention probability を表す行列積入力を FP16 の高低2成分で持つ既定経路から、単一 FP16 成分を使う高速経路へ切り替えます。単一 FP16 化で丸めが変わります。この変数だけでは行列コア経路を有効にせず、通常は `STRATA_HIP_WMMA=1` も必要です。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| それ以外（例: `0`, `true`, ` 1`） | 無効 |

実装は文字列全体を parse せず、`getenv()` の結果が非 null かつ `e[0] == '1'` かだけを見ます。判定は `launch_wmma()` の関数内 static 変数に保存されるため、初回評価後にプロセス環境を変更しても再評価されません。隣接する `STRATA_PF_SWITCH_MIN_T` は `atoll()` で読み、未設定時は `0`、設定値が `n_q` 以下のときだけ高速カーネルを選びます。値が空文字や数値でない文字列なら `atoll()` の結果は `0` です。

## 有効になる条件

- HIP ビルドであること。HIP の prompt attention 実装は `STRATA_HIP_WMMA=1` と対応 GPU を確認して `launch_wmma()` を呼びます。対応 GPU は `gfx11` 系の実装対象（`gfx1100/1101/1102/1150/1151`）または `gfx12`（`gfx1200/1201`）です。それ以外ではこの WMMA 経路を使いません。
- 対象となる KV pool が int8 K/V で、Q4 pool ではなく、head dimension・head 数の関係、ページ表などの引数が WMMA 経路の条件を満たすこと。
- prompt 呼び出し元が `STRATA_PROMPT_ATTN_OLD` を設定していないこと。設定されていれば新しい prompt attention kernel を呼ばず、decode attention のバッチ経路へ進みます。
- `n_q >= STRATA_PF_SWITCH_MIN_T` であること。閾値を上げると短い query batch は既定の高低2成分経路に残ります。

通常の CUDA ビルドでは `qsa_prompt_attn_batch()` の CUDA 経路が `launch_wmma()` に進まず、この変数による切り替えはありません。HIP でも `STRATA_HIP_WMMA` が無効、デバイス非対応、pool 条件不一致の場合は適用されません。

## 実行時の詳細

`src/prefill/prefill.cpp` の prompt attention 部は `qsa_prompt_attn_batch()` を呼びます。HIP 側で `hip_wmma_usable()` が有効と判定され、int8 KV 等の条件が揃うと `launch_wmma()` が各 query tile について `STRATA_PA_FAST` と `STRATA_PF_SWITCH_MIN_T` を評価し、`prompt_attn_wmma_kernel<false>`（単一 FP16 成分）または `<true>`（高低2成分）を起動します。変数はカーネル選択に使われ、選んだ経路内で追加ログを出す処理はありません。カーネル起動失敗時は `qsa_prompt_attn_batch (wmma): <CUDA/HIP runtime error>` を stderr に出し、プロセスを終了します。

`docs/STRIX_HALO.md` は、`STRATA_PA_FAST` を丸め方が異なる opt-in の高速設定として記載し、同ガイドの設定例では `STRATA_PF_SWITCH_MIN_T=4096` と組み合わせています。ガイドの節ではこれらのスイッチが既定と異なる丸めになること、および maintainers が KL で評価すると説明していますが、`STRATA_PA_FAST` 単独の測定値や KL 値は示していません。したがって、この文書では速度や品質の定量的効果を断定しません。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:1128-1149` — HIP ビルドと gfx 世代ごとの WMMA 実装範囲。
- `src/kernels/cuda/qsa_prompt_attn.cu:1193-1201` — `<true>` / `<false>` の算術経路の違いと丸めに関する実装コメント。
- `src/kernels/cuda/qsa_prompt_attn.cu:1426-1448` — 値の読み取り、閾値との比較、kernel 選択、起動エラー処理。
- `src/kernels/cuda/qsa_prompt_attn.cu:1483-1491` — HIP 側での WMMA 呼び出し条件。
- `src/prefill/prefill.cpp:2836-2851` — prompt 呼び出し元と `STRATA_PROMPT_ATTN_OLD` による fallback。
- `docs/STRIX_HALO.md:100-116` — 丸めが変わる opt-in 群、設定例と query 長閾値の説明。
