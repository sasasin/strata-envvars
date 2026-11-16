# `STRATA_KVA`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

長い cold prompt の一部で KVA (approximate late-layer state) を有効にする opt-in スイッチ。既定は無効で、オンの場合、条件を満たした prompt の先頭側について split 以降の層を state-only で実行し、末尾 suffix は通常どおり計算する。state-only の層では GDN recurrence / convolution history と KV・indexer cache を進める一方、attention 出力・出力 projection・MoE 半分とその expert 転送を省く。したがって、その prompt の状態と後続 decode の文脈は変わり得る。通常の全層計算と同一の結果を保証する設定ではない。実装は `include/strata/prefill/kva.hpp` の設定・適用条件と `src/prefill/prefill.cpp` の chunk/layer ループにある（`include/strata/prefill/kva.hpp:1-21,69-133`; `src/prefill/prefill.cpp:3996-4015,4174-4180,4734-4752`）。

## 値と判定

`kva_config_from_env()` は `std::getenv("STRATA_KVA")` で読み、unset または空文字を無効とする。値全体や数値としての妥当性は調べず、先頭文字が `'0'` なら無効、それ以外の非空値なら有効 (`on`) かつ `explicit_on` とする。大文字小文字・空白・後続文字も検査しない。したがって `1`, `true`, `false`, `no`, `2`, `-1`, `1abc`, ` true` はオン、`0`, `0anything` はオフ、`TRUE` もオン。設定名だけでオンにはならず、空文字は未設定と同じ。Metal build では `explicit_on` は残るが `kKvaBackend` が false のため `on` は false にされる（`include/strata/prefill/kva.hpp:43-49,77-78,150-156`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Metal 以外の build (`kKvaBackend == true`) | オフ | 非空で先頭文字が `0` 以外 (`1`, `true`, `2`, `1anything`, ` true`) | 空文字、または先頭が `0` (`0`, `0anything`) |
| `STRATA_GPU_METAL` 定義あり | オフ | `on` にはならない。非空で先頭が `0` 以外なら「明示的に要求された」状態 (`explicit_on`) として build 非対応警告の条件になる | unset / 空文字 / 先頭が `0` |

`STRATA_KVA` 自体に整数変換、範囲、負値判定はない。関連する `STRATA_KVA_SPLIT`, `STRATA_KVA_SUFFIX`, `STRATA_KVA_MIN_PROMPT` の parse や clamp は別設定である。CLI の `--set STRATA_KVA=...` は Strata launch の advanced environment setting として渡されるもので、engine 側に `STRATA_KVA` 専用 CLI 引数や別値との優先順位はない（`strata_cli/launch/cmd.py:121-122`; `strata_cli/launch/settings.py:259-284`）。

## 有効になる条件

`STRATA_KVA` がオンでも、各 prompt read が次をすべて満たす場合だけ近似処理に入る（`include/strata/prefill/kva.hpp:104-133`; `src/program/generate.cpp:7622-7643`）。

- build に late-layer state-only path があること。ソースの macro 判定では Metal は非対応、CUDA/HIP は対応と記載されている。Metal で値が明示されていると、起動時に `every prompt is read exactly` と警告し、KVA は無効になる（`include/strata/prefill/kva.hpp:43-49`; `src/program/generate.cpp:7628-7643`）。
- engine が multi-GPU layer split、`--batch` slot、または `--peer-device` を使用していないこと。これらは起動時に process 全体の KVA を block する（`src/program/generate.cpp:7634-7643`）。
- cold read で `pos0 == 0`、全 trunk を読む layer range であること、画像 prompt ではないこと、DFlash2 用 hidden-state taps がないこと（`include/strata/prefill/kva.hpp:115-121`; `src/prefill/prefill.cpp:4002-4004`）。
- prompt の token 数が `STRATA_KVA_MIN_PROMPT` 以上で、かつ `effective_suffix + 64` より大きいこと。既定 `min_prompt` は 4096、suffix は 2048。suffix が残りを覆う短い read は近似しない（`include/strata/prefill/kva.hpp:54-57,85-96,122-129`）。
- 既定ではモデル形状が 48 layers / 512 experts であること。異なる形状は `STRATA_KVA_ANY_MODEL` が有効でなければ exact read へ戻る。`STRATA_KVA_ANY_MODEL` 有効時は近似を許可し、一度だけ警告する（`include/strata/prefill/kva.hpp:130-133`; `src/prefill/prefill.cpp:4002-4011`）。

`STRATA_KVA_SPLIT` は最初に近似する layer (default 36) を指定し、実行時に `[1, n_layers]` へ clamp される。`STRATA_KVA_SUFFIX` は完全計算する末尾長で、負値は 0 に clamp され、unset / 0 は既定 2048 に戻る。`STRATA_KVA_MIN_PROMPT` の unset default は 4096 で、値の clamp はこの helper では行わない（`include/strata/prefill/kva.hpp:54-57,137-159`; `src/prefill/prefill.cpp:4013-4015`）。

## 実行時の詳細

本番経路では `kva_config()` が `kva_config_from_env()` の結果を function-local `static const` に保存する。`generate` 初期化時と prefill から参照され、以後の `getenv` 再評価はないため、プロセス起動後の環境変更は反映されない。`kva_config_from_env()` 自体は毎回読み直す関数だが、通常の本番参照ではなくテストから直接呼ばれている（`include/strata/prefill/kva.hpp:149-195`; `src/program/generate.cpp:7629-7630`; `src/prefill/prefill.cpp:3998-4004,7625`）。

KVA が通ると、各 chunk の最終 position が suffix frontier より前にある場合にその chunk を近似対象とする。split 以上の layer で、既定は state-only のみを進め、`STRATA_KVA_ONLY` があれば GDN/QSA の選択層だけに対象を絞る。`STRATA_KVA_SKIP=moe` は attention half の出力を含めて実行し MoE half のみを省くモードに変える。末尾 suffix は全計算され、後続 continuation read は新しい token を通常計算する（`src/prefill/prefill.cpp:4013-4015,4174-4180,4734-4752`; `include/strata/prefill/kva.hpp:69-96`）。

## ログと測定値

- Metal build で変数が明示的にオンと判定された場合、起動時に `strata generate: STRATA_KVA is set, but this build has no state-only late-layer path; every prompt is read exactly` を stderr に出す（`src/program/generate.cpp:7631-7633`）。
- multi-GPU split / `--batch` / `--peer-device` で process 全体が block された場合、オン要求があれば起動時に `strata generate: KVA (the approximate late-layer prompt read) is off here: <理由>` を出す（理由はそれぞれ `a layer split across GPUs`, `batch slots (--batch)`, `a peer device (--peer-device)`）（`src/program/generate.cpp:7634-7642`）。
- capture または近似実行では `strata prefill: KVA ...` の行に split・suffix・近似 position/chunk 数・mode を出す。実際に position を近似した最初の read では、late layers が保持する近似状態と後続 continuation の exact read について説明する行を process で一度出す（`src/prefill/prefill.cpp:7435-7457`）。
- 有効要求がその read に適用されない場合は、通常の短い prompt / continuation など routine 理由を除き、`strata prefill: KVA configured but NOT applied: ...` と理由・prompt 長・min_prompt・suffix・split を stderr に出す。形状不一致の警告文は `this model's shape (L layers, E experts) is not one KVA was measured on (STRATA_KVA_ANY_MODEL=1 allows it)`（`src/prefill/prefill.cpp:7459-7471`）。
- `docs/KVA.md` は KVA の opt-in と適用条件、品質・速度測定を記載する。本調査ではソース上の分岐を確認し、資料内のベンチマークを再測定していないため測定値は転記しない。

## 根拠

- 候補名の実読み取り、parse、backend 判定、process cache: `include/strata/prefill/kva.hpp:43-49,137-195`
- 適用条件と decline reason: `include/strata/prefill/kva.hpp:104-133`
- 起動時の全体 block / Metal 警告: `src/program/generate.cpp:7622-7643`
- read ごとの形状判定・model override 警告・適用計画: `src/prefill/prefill.cpp:3996-4023`
- chunk / layer での state-only 処理とログ: `src/prefill/prefill.cpp:4174-4180,4734-4752,7435-7471`
- CLI launch `--set` の advanced environment handling: `strata_cli/launch/cmd.py:121-122`; `strata_cli/launch/settings.py:259-284`
- 関連する Strata 説明資料との照合: `docs/KVA.md:1-58`（資料の性能値はソースからの再確認・再測定をしていない）。
