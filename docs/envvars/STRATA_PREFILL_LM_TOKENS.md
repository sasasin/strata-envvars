# `STRATA_PREFILL_LM_TOKENS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

layer-major prefill が一度に処理する super-chunk の目標 token 数を指定する。値が正なら通常値より大きな単位で各層の routed expert を処理する layer-major walk のサイズに使われ、未設定または正でない値ならコード内の既定目標を使う。この変数自体は layer-major を有効化しない。通常の chunk-major 経路、または layer-major が無効・適用不可の prompt には影響しない。読み取りとサイズ決定は `Prefill::lm_prepare`（`engine/src/prefill/prefill.cpp`）にある。

layer-major 経路では、attention halves と router/shared expert を sub-chunk ごとに進め、routed experts を super-chunk 内の全 token について層ごとにまとめて実行する。したがってこの変数が変えるのは処理単位とバッファ規模であり、生成 token の数を指定するものではない。コードコメントは expert の加算順序と MMQ の row grouping が chunk-major と異なり、FP32 丸め差がありうると説明している（`engine/src/prefill/prefill.cpp:8066-8080`）。

## 値と判定

初回の `lm_tokens_env()` 呼び出し時に `std::getenv` で読み、関数内 `static` に `std::atoll` の結果を保存する。未設定は `0`、空文字も `atoll` の結果が `0` となる。文字列全体の妥当性検査やエラー報告はなく、`atoll` が先頭から数値として読める部分を変換する（`12junk` は 12、`junk12` や `true` は 0）。先頭の空白や符号も `atoll` の規則で扱われる。正値のみ明示目標として採用され、0・負値は既定値へ戻る（`engine/src/prefill/prefill.cpp:8098-8100,8235-8240`）。

| 条件 | unset | 有効になる値（例） | 無効・既定扱いになる値（例） |
|---|---|---|---|
| `lm_prepare` が呼ばれる layer-major 経路 | 目標サイズは既定値 | `1`、`512`、`12junk`（変換結果が正） | 空文字、`0`、`0anything`、`-1`、`true`、`junk12`（変換結果が 0 以下） |
| 通常の chunk-major 経路、または layer-major が適用されない場合 | 参照されない | 参照されない | 値にかかわらず本変数によるサイズ指定は使われない |

正の目標値もそのままのサイズを保証しない。最小値（通常は chunk `m.T` の 1 個分、`STRATA_PREFILL_LM_FORCE` の先頭文字が `1` または複数 prompt の `run_multi` では 1）以上にし、`m.T` 単位へ切り下げ、prompt 全体と layer split の cap で上限を設ける。さらに必要な CUDA バッファが空き VRAM の余裕内に収まらないと、`m.T` ずつ縮める。従って正値が `m.T` より小さくても通常は 1 chunk 分になり、正値が大きくても実際の super-chunk は小さくなることがある（`engine/src/prefill/prefill.cpp:8235-8261`）。

## 有効になる条件

- layer-major 経路そのものが有効であること。通常は `STRATA_PREFILL_LAYER_MAJOR` が空でない値として設定され、`atoi` 結果が非 0 の場合に有効となる。未設定時の現行 `prefill_layer_major_default` は常に false。単一 CUDA GPU の small expert cache の自動経路は、条件を満たすと `STRATA_PREFILL_LAYER_MAJOR=1` を設定する。`STRATA_PREFILL_LAYER_MAJOR=0` など明示的な 0 は自動判定より優先して無効にする（`engine/include/strata/core/sm120_series.hpp:176-191`; `engine/src/program/generate.cpp:12562-12612`）。
- AMD HIP/HIP GFX906 build では、別途 `STRATA_LM_HIP` の先頭文字が `1` でなければ `lm_prepare` が layer-major を断り、chunk-major に戻る。CUDA build にはこの gate がない（`engine/src/prefill/prefill.cpp:8166-8178`）。
- prompt は text prompt でなければならず（image prompt は不可）、KVA が on でなく、chunk 境界で yield する batch read や `--prefill-pipe` の強制 chunk plan でなく、peer GPU の共有や peer helper、実行中の chunk hand-off を使わない必要がある（`engine/src/prefill/prefill.cpp:8182-8200`）。
- `STRATA_EXPERT_NIBBLE` の 4-bit expert slot、routing/row debug dump（`STRATA_DBG_FEAT`、`STRATA_DBG_ROUTE_OVERRIDE`、`STRATA_PREFILL_DUMP_R_ALL`）、未対応の WMMA-only / APR / NVFP4 レイヤー、必要な MMQ・FP16・MoE バッファ不足、fused expert layout などでも layer-major 準備を断り、chunk-major に戻る（`engine/src/prefill/prefill.cpp:8201-8234`）。
- prompt が算出された最小サイズより短い場合や、super-chunk 用の CUDA / pinned host バッファを確保できない場合も適用されない（`engine/src/prefill/prefill.cpp:8235-8237,8273-8313`）。
- この変数に対応する CLI 引数による上書きはない。`--prefill-pipe` はむしろ layer-major を断る条件である（`engine/src/prefill/prefill.cpp:8199-8200`）。

## 実行時の詳細

`lm_tokens_env()` は `lm_prepare` 内の min size と target の計算で参照される。値はその関数の最初の呼び出し時に一度 cache され、実行中に環境を変えても反映されない。正の値は目標 `want` となり、0 以下では `lm_by_default_` が true のとき 32768、false のとき 8192 が目標になる（`engine/src/prefill/prefill.cpp:8098-8100,8120-8122,8235-8240`）。現行の自動 default 判定は false だが、別経路が default-on として呼び出した場合に備え、準備処理には 32768 の分岐も残る（`engine/include/strata/core/sm120_series.hpp:184`; `engine/src/prefill/prefill.cpp:9657-9663`）。

サイズを確定すると、CUDA 空きメモリと margin を見て収まる最大サイズを探す。既定の row placement は VRAM に目標全体が収まる場合に VRAM、そうでなければ pinned host memory へ切り替える。層 split の後段は host 側の residual rows を使う。適合サイズがなければ準備を断り、通常経路へ戻る。layer-major のために CUDA allocation に失敗した場合も理由付きで準備を断る（`engine/src/prefill/prefill.cpp:8249-8285,8287-8313`）。

有効時は `run_layer_major` が `lm_run` を呼び、chunk-major とは異なる層単位の処理を行う。layer-major の実行結果は stderr に実際の token 数・super-chunk 数・最大サイズ・residual の置き場所・streamed expert blob 数などを出す。準備が断られた場合は理由に応じて `strata prefill: layer-major off for this prompt: ...` を出すが、既定で短い prompt の場合はこの理由行を抑制する。失敗して通常 chunk-major に戻った回数が続く場合、16 回ごとに継続中の理由を出す（`engine/src/prefill/prefill.cpp:9673-9705,9566-9574`）。

## ログと測定値

成功時の layer-major ログ形式は `strata prefill: layer-major (layers ...): ... tokens in ... super-chunk(s) of up to ...` で、実際に採用したサイズを確認できる。準備時の拒否理由は `strata prefill: layer-major off for this prompt: ...` に出る。既定で短い prompt の拒否理由は抑制される。ログ文字列・抑制条件は `engine/src/prefill/prefill.cpp:9567-9574,9694-9702`。

ソースコメントには 2x RTX A4000・32K prompt の測定を根拠として default-on 時の目標 32768 が記されるが、測定方法や結果値はここには示されていない。本調査ではその性能値を一般化しない（`engine/src/prefill/prefill.cpp:8120-8122`）。

## 根拠

- `engine/src/prefill/prefill.cpp:8063-8080,8098-8100` — layer-major の処理内容と環境変数読み取り。
- `engine/src/prefill/prefill.cpp:8166-8238` — backend、prompt、機能条件、最小サイズと目標サイズ。
- `engine/src/prefill/prefill.cpp:8239-8313` — 丸め、prompt/cap 上限、VRAM 判定と allocation。
- `engine/src/prefill/prefill.cpp:9566-9574,9657-9705` — 成功ログ、経路選択、拒否ログと fallback。
- `engine/include/strata/core/sm120_series.hpp:176-191` — layer-major の default と明示値の解決。
- `engine/src/program/generate.cpp:12562-12612` — small expert cache における自動有効化。
