# `STRATA_HIP_WMMA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバーの環境変数は対象外。

## 役割

HIP ビルド専用の opt-in スイッチ。prompt 経路の QSA attention を RDNA4/RDNA3 の行列コア（WMMA）カーネルで実行するか、portable な FP32 カーネルのままにするかを決める。加えて prefill の expert ring のスロット数を変える。出力ビットは既定カーネルと一致しない（末尾の丸めで差が出る）ため、既定は OFF で、ユーザーが明示的に有効化する。CUDA ビルドではこの経路を通らない（tensor-core 側を使う）。

環境変数を読む実装箇所は次の 3 つ（SYCL ビルドには同一ロジックのミラーがある）。

1. `src/kernels/cuda/qsa_prompt_attn.cu:1402-1424` の `hip_wmma_usable()` — カーネル選択。
2. `src/prefill/prefill.cpp:281-285` の `ring_slots()` — prefill ring のスロット数。
3. `src/program/generate.cpp:4554` — 起動時の hint 表示。

## 値と判定

読み取りは `std::getenv` の結果の**先頭文字 `e[0]` だけ**を `'1'` と比較する。文字列全体や数値は parse しない。

| 状態 | `hip_wmma_usable` / `ring_slots`（機能） | generate の hint |
|---|---|---|
| 未設定（`nullptr`） | 無効 | 条件が揃えば hint を表示 |
| 空文字 `""` | 無効（`e[0]` は `\0`） | 表示しない（設定済みとみなす） |
| 先頭文字が `1`（`1`, `10`, `1anything`） | 有効 | 表示しない |
| それ以外（`0`, `true`, `false`, `2` など） | 無効 | 表示しない |

大文字小文字・空白・数値妥当性は検査しない。hint の判定は「未設定かどうか」（`== nullptr`）で、機能の判定とは別。`STRATA_HIP_WMMA=0` は機能を有効化しないが、hint は黙らせる。

根拠: `qsa_prompt_attn.cu:1404-1405`、`prefill.cpp:282-283`、`generate.cpp:4554`。

## 有効になる条件

機能（カーネル launch）が効くには、値判定に加えて次が必要。

- ビルドが HIP（`#if defined(__HIPCC__)`）。CUDA ビルドでは `hip_wmma_usable` 経路そのものが呼ばれない。
- 実行デバイスが gfx12（`__gfx1200__`/`__gfx1201__`）または gfx11 の WMMA 対象（`gfx1100/1101/1102/1150/1151`）。判定は `hip_wmma_usable()` の `arch[dev]`（`strncmp(gcnArchName,"gfx12",5)` または `gfx_arch_is_gfx11_wmma`）。カーネル自体もこれらのターゲットマクロでのみコンパイルされる（`qsa_prompt_attn.cu:1139-1149`）。
- int8 KV の pool が揃っていること（`k_q`/`v_q`/`k_scale`/`v_scale` が非 null、`k_q4`/`v_q4` が null）、`head_dim==HD`、`n_head==G*n_head_kv`、`cap>0`、`ids`/`steps`/`page_table` が有効。条件不足なら portable カーネルに fallback（`qsa_prompt_attn.cu:1487-1491`）。

docs の `AMD_HIP.md:329` は「gfx12 only」と書くが、コードの `hip_wmma_usable` と `gfx_arch_is_gfx11_wmma` は gfx11 ターゲットも受け付ける（`qsa_prompt_attn.cu:1400` の注釈も gfx12 と gfx11 を挙げる）。generate の hint 表示だけは gfx12 限定（`generate.cpp:4554`）。この食い違いは現状コードが gfx11 を有効化する、docs が gfx12 と説明する、という点である。

## 実行時の詳細

### カーネル選択（`hip_wmma_usable`）

`want` は `static const bool` で、プロセス内で最初に呼ばれたとき一度だけ環境を読む。その後の環境変更は再評価されない。`arch[dev]` もデバイスごとに初回計算後キャッシュ。有効かつアーキテクチャ一致のとき `qsa_prompt_attn_batch` は `launch_wmma` を呼ぶ。`launch_wmma` 内で `STRATA_PA_FAST`（先頭文字 `1`）が有効なら masked variant の代わりに fast variant を使い、`STRATA_PF_SWITCH_MIN_T` の `atoll` 値で分岐する（`qsa_prompt_attn.cu:1431-1440`）。

### prefill ring（`ring_slots`）

`wmma` は `static const bool` で初回判定後キャッシュ。`STRATA_PREFILL_RING` が未設定かつ `g_ring_override <= 0` かつ有効のとき、`T >= stream_all_min()` なら 96、そうでなければ `STAGE` を返す（`prefill.cpp:285`）。明示的な `STRATA_PREFILL_RING` があればそちらが優先される。

### 観測できる出力

- 機能判定の初回評価時、stderr に一度だけ:
  `strata: STRATA_HIP_WMMA: the prompt attention on matrix cores on (<arch>)` または `... unavailable (<arch>)`（`qsa_prompt_attn.cu:1419-1420`）。
- 起動時の hint（未設定・HIP・gfx12・`--kv int8` のときだけ、stderr）:
  `strata generate: hint: STRATA_HIP_WMMA=1 reads prompts about 30% faster on this card with --kv int8 ... Nothing was enabled.`（`generate.cpp:4555-4557`）。

## 相互作用

- `STRATA_PA_FAST`（先頭文字 `1`）: WMMA launch の kernel variant を変える。
- `STRATA_PF_SWITCH_MIN_T`（`atoll`）: fast variant を使う最小トークン数。
- `STRATA_PREFILL_RING`: 設定があれば ring のスロット数を上書き（WMMA の 96 より優先）。
- `STRATA_GFX1151_DEFAULTS`: gfx1151 の既定テーブル。`STRATA_HIP_WMMA` はビットを変えるスイッチとして opt-in 扱い（`arch_defaults.hpp:7-10`）。ユーザーが何かに設定すれば上書きされない。

## 測定値（資料に記載）

`docs/AMD_HIP.md:331-334` の記載（資料中の主張であり、本調査で計測器動作を独自確認した事実ではない）: portable カーネルの 7.2–7.5 倍。R9700 prompt 4K 1,784→2,427 tok/s、16K 1,797→2,700（TheRock 7.10 のユーザー測定、+29–34%, #432）。bitwise ではなく greedy text が token 約 50 以降で差が出る。ring 96 の効果: 9070 XT 4K 718→1,211、16K 1,518→2,032。hint の「about 30% faster」は R9700・PR #1318 由来（`generate.cpp:4551-4552`）。

## 根拠

- 機能の読み取り: `src/kernels/cuda/qsa_prompt_attn.cu:1402-1424`（`hip_wmma_usable`）、`src/prefill/prefill.cpp:281-285`（`ring_slots`）。
- hint の読み取り: `src/program/generate.cpp:4554-4557`。
- アーキテクチャ判定: `include/strata/kernels/gfx_arch.hpp:23-26`（`gfx_arch_is_gfx11_wmma`）、`qsa_prompt_attn.cu:1139-1149`（ビルドマクロ）。
- SYCL ミラー: `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1919-1934`、`sycl/src/prefill/prefill.cpp:201`。
- docs 照合: `docs/AMD_HIP.md:329-334`。テスト（`src/kernels/qsa_prompt_attn_parity.cpp`、`src/core/arch_defaults_test.cpp`）は環境変数を設定する手掛かりだが、実装根拠にはしていない。
