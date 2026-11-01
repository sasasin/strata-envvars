# `STRATA_PREFILL_LAYER_MAJOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

長い prompt を従来の chunk-major 方式で全 layer に通す代わりに、複数 chunk 分の super-chunk を layer ごとに処理する layer-major prefill を選びます。各 layer の routed expert を super-chunk ごとにまとめて処理するため、expert の読み込み回数が減ります。routed expert の加算順序と MMQ の row grouping は従来経路と異なるため、出力は bitwise 同一ではありません。

環境変数は `Prefill::run()` の経路選択に使われます。ソース内の `std::getenv("STRATA_PREFILL_LAYER_MAJOR")` は `lm_env_text()` の一箇所です。ほかの一致箇所は説明コメントや kernel/build の注釈で、追加の読み取りではありません。

## 値と判定

`lm_env_text()` は最初に呼ばれた時点で `getenv()` の返したポインタを static に保持します。値は `prefill_layer_major_resolve()` に渡され、空でない文字列は `std::atoi()` で変換し、結果が 0 なら OFF、0 以外なら ON です。文字列全体の検証はありません。

| 環境変数の値 | 判定 |
|---|---|
| 未設定 | backend・stage 数・`STRATA_DEFAULTS` に応じた既定値 |
| 空文字 | 未設定と同じ既定値 |
| `1`, `2`, `-1`, `1tail`, ` 1` | `atoi()` が 0 以外を返すため ON |
| `0`, `00`, `0tail`, `off`, `  ` | `atoi()` が 0 を返すため OFF |

数値の範囲、後続文字、大文字小文字は別途検証しません。非空の明示値は既定値と `STRATA_DEFAULTS=026` より優先します。したがって `STRATA_PREFILL_LAYER_MAJOR=1` は `STRATA_DEFAULTS=026` の下でも選択を許可し、`=0` は既定 ON を止めます。CLI option による値の上書きはありません。

## 有効になる条件

値判定で ON になっても、layer-major の実行準備が成功しなければ実行されません。

- 未設定または空文字の場合、既定 ON は CUDA build で stage 数が 2 以上、かつ `STRATA_DEFAULTS=026` でない場合だけです。単一 GPU、HIP build、`STRATA_DEFAULTS=026` では既定 OFF です。
- 非空の値が ON なら、単一 GPU でも選択を試みます。ただし HIP build は `STRATA_LM_HIP=1` も必要です。この別変数が未設定または先頭文字が `1` 以外なら準備を断り、従来経路になります。`STRATA_LM_HIP` は先頭文字だけを確認します。
- Metal の `Prefill::run()` はこの判定より前に Metal prompt 経路へ return するため、この変数を使いません。
- 引き継ぎ中の chunk hand-off、peer GPU/helper、画像 prompt、DFlash2 prompt taps、`STRATA_KVA` が有効、chunk 境界で yield する batch read、`--prefill-pipe` が chunk を固定する場合は適用できません。
- `STRATA_EXPERT_NIBBLE` の nibble slot が有効、routing/row debug dump が設定されている場合、必要な expert/MMQ/FP16/MoE buffer や対応 expert plan がない場合、WMMA 専用 layer、APR/Hadamard-folded layer、NVFP4 layer、fused expert layout でも準備を断ります。
- prompt が短すぎる場合も従来経路になります。通常は少なくとも `2 * m.T` tokens、`STRATA_PREFILL_LM_TOKENS` が正数なら `m.T` tokens が必要です。`STRATA_PREFILL_LM_FORCE=1` は最小長を 1 にします。
- super-chunk 用の VRAM が足りない、routing table または residual rows 用 pinned RAM が確保できない、device buffer / copy event を作れない場合も準備失敗です。layer split では各 stage が共通の super-chunk サイズを確保できることも必要です。

ここに挙げた `STRATA_PREFILL_LM_*`、`STRATA_LM_HIP` などは、layer-major 経路の準備条件・サイズ決定に使う関連変数です。個別の値仕様はそれぞれの実装に従います。

## 実行時の詳細

`Prefill::run()` が `hand_in_ == nullptr` かつ実装状態が初期化済みの場合、環境値を解決して `lm_prepare_chain()` を試します。既定で有効になった場合は process 内で一度だけ、stderr に `strata prefill: layer-major prefill is on for this layer split ...` を出します。準備に成功すると layer-major 実行後に pipeline を drain し、buffer を解放して結果を返します。

super-chunk の目標は既定 ON のとき 32,768 tokens、明示 ON または既定 OFF 条件下での opt-in では 8,192 tokens です。正数の `STRATA_PREFILL_LM_TOKENS` はこの目標を置き換えます。実際のサイズは chunk 単位に丸められ、prompt 長・stage 間の共通サイズ・利用可能な VRAM に合わせて縮小されることがあります。

準備が失敗した場合は理由別の stderr `strata prefill: layer-major off for this prompt: <理由>` を出し、通常の `run_impl()`（chunk-major）に進みます。同じ理由のログは繰り返しません。未設定時の既定 ON で短い prompt の場合は、この OFF ログを抑制します。したがって、明示 ON でも prompt/model/resource 条件を満たさなければ自動的に従来方式へ戻ります。

`lm_env_text()` と `STRATA_DEFAULTS` の判定は static cache されます。`Prefill::run()` ごとに resolver は呼ばれますが、初回評価後にプロセス環境を変更しても値は再読み込みされません。適用可否や必要メモリは prompt ごとに準備時に確認されます。

準備成功後の layer-major 実行または pipeline drain が失敗すると `Prefill::run()` は false を返します。通常の generate 呼び出し元は stderr に `strata generate: <error>` を出して終了コード 1 を返します。

## ログと測定値

release note は、2 枚の RTX A4000 (各 16 GB)、Qwen IQ3_XXS、RAM から多くの expert を stream する条件の 5 paired runs について、32K prompt の first word が 141.8 秒から 27.7 秒、20K が 98.8 秒から 17.5 秒、8K が 41.8 秒から 15.2 秒になったと報告しています。同資料は decode 38.6 対 38.4 tok/s、needle 12/12、quick suite 18/19、first-token probability の KL 差 0.0007〜0.009（各確認で top choice は同じ）も記載し、layer-major は加算順序が異なるため文面が変わり得るとしています。これらは同資料に記載された条件での結果です。

## 根拠

- `src/prefill/prefill.cpp:5894-5898` — 環境値の読み取りと static cache、空文字判定。
- `include/strata/core/sm120_series.hpp:107-120` — 既定値と `atoi()` による明示値判定。
- `src/prefill/prefill.cpp:2499-2503,7222-7271` — stage 数、Metal 早期 return、選択、既定 ON/OFF ログ、準備失敗後の fallback。
- `src/prefill/prefill.cpp:5955-6114,6117-6168` — backend 条件、適用不可条件、短い prompt、super-chunk の目標と確保、stage 間の調整。
- `src/prefill/prefill.cpp:5880-5892,6176-6182` — layer-major の処理概要と実行開始。
- `src/program/generate.cpp:17794-17798` — prefill 失敗時の stderr と終了。
- `include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS=026` の認識方法と static cache。
- `docs/release-notes-0.2.7.md:20` — 上記測定・適用条件のリリース資料。
