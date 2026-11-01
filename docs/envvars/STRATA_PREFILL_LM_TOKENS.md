# `STRATA_PREFILL_LM_TOKENS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

layer-major prefill が一度に処理する super-chunk の目標 token 数を指定します。layer-major は各 layer の attention/router を sub-chunk ごとに進め、同じ super-chunk 内の expert 計算をまとめて実行する経路です。この変数は経路を有効化しません。通常の `Prefill::run()` では `STRATA_PREFILL_LAYER_MAJOR` などで layer-major が選ばれた後、また複数 prompt の co-read では `run_multi()` が layer-major 準備を行う際にサイズ決定へ使われます（`src/prefill/prefill.cpp:6188-6198,7222-7255`）。

## 値と判定

値は `std::getenv()` で取得し、`std::atoll()` で符号付き整数に変換します。環境変数を未設定なら 0、設定値が空文字または数値として読めない文字列でも `atoll` の変換結果は 0 です。先頭の空白や符号は数値変換の規則に従い、数値の後ろにある文字列は検査されません（例: `4096tail` は 4096 として扱われます）。正の値だけが明示目標として使われ、0 以下は既定値に戻ります。文字列全体の妥当性検査、エラー通知、独自の数値範囲検査はありません（`src/prefill/prefill.cpp:5910-5913,6024-6029`）。

| 変換結果 | サイズ決定 |
|---|---|
| `> 0` | 指定値を目標にする。通常の prompt では最小サイズを `m.T` とし、目標を `m.T` の整数倍へ切り下げたうえで、少なくとも `m.T` にする。 |
| `0` または `< 0` | `lm_by_default_` が true（何も明示せず通常経路の既定で layer-major が選ばれた状態）なら 32768 token、それ以外は 8192 token を目標にする。通常の prompt では最小サイズは `2 * m.T`。 |

`m.T` はモデル/実行構成における prefill chunk の token 数です。目標は厳密な上限ではありません。計算後のサイズは prompt 長に合わせて切り上げた chunk 境界で制限され、GPU メモリに収まらなければ `m.T` 単位で縮小されます。layer split では stage 間で共通のサイズに制限されます。複数 prompt co-read は `lm_force_` により最小サイズ判定を 1 token まで緩めます（`src/prefill/prefill.cpp:6024-6032,6044-6048,6117-6168,6195-6198`）。

## 有効になる条件

- 通常の `Prefill::run()` では、layer-major 自体が選択され、初期化済みで、chunk hand-off 中でないことが必要です。`STRATA_PREFILL_LAYER_MAJOR` が非空なら `atoi` が 0 以外で opt-in、0 なら opt-out です。未設定または空文字の場合は CUDA の 2 stage 以上で既定 ON（ただし `STRATA_DEFAULTS=026` では OFF）、単一 GPU と HIP では既定 OFF です（`src/prefill/prefill.cpp:5894-5898,7233-7243`; `include/strata/core/sm120_series.hpp:112-120`）。
- HIP build では layer-major の準備時に `STRATA_LM_HIP` の先頭文字が `1` でなければ chunk-major に戻ります（`src/prefill/prefill.cpp:5955-5967`）。Metal build は `Prefill::run()` の冒頭で Metal engine に委譲し、この CUDA/HIP layer-major 選択処理を通りません（同 `:7222-7237`）。
- 通常 prompt の layer-major は、image prompt、peer GPU、未対応の layer split 状態、DFlash2 prompt taps、`STRATA_KVA`、chunk 境界で yield する batch read、`--prefill-pipe` が chunk 数を固定する場合、未対応の expert format/layout、必要 buffer 不足、短い prompt などで準備を見送ることがあります。4-bit expert nibble が build に含まれる場合、その slot を使う layer も対象外です（`src/prefill/prefill.cpp:5971-6026`）。
- 複数 prompt の co-read は `run_multi()` から `lm_prepare_chain()` を直接呼ぶ別経路です。そこでは layer-major opt-in 判定を経ず `lm_force_` を立てますが、chunk hand-off 中や buffer 準備失敗なら co-read を辞退し、呼び出し元が通常の prompt read に戻ります（`src/prefill/prefill.cpp:6188-6198`; `src/program/generate.cpp:15204-15224`）。

## 実行時の詳細

`lm_tokens_env()` の値は関数内の `static const int64_t` に保存されます。したがってプロセス内で最初にサイズ判定した後に環境を変更しても再読込されません。読み取り箇所はこの helper の `getenv` 1 箇所で、候補名の完全一致検索でも他の参照はありません（`src/prefill/prefill.cpp:5910-5913`）。この値は CLI 引数で上書きされず、CLI の `--prefill-pipe` はサイズ指定ではなく通常 prompt の layer-major 経路を辞退させます（同 `:5988-5989`）。

正の目標値は buffer の必要量を見積もる初期サイズです。残り VRAM（既定余白を差し引く）に収まる最大 super-chunk まで縮小され、指定目標全体が入らない場合は pinned host RAM 側の残差行配置も試されます。最小サイズまで確保できない場合は準備失敗です（`src/prefill/prefill.cpp:6027-6059`）。

通常 prompt で layer-major を選択した後、準備失敗の理由は stderr に `strata prefill: layer-major off for this prompt: ...` と出て、chunk-major 経路が続きます。ただし既定 ON 時の短い prompt はこのログを抑制します。成功すると処理完了時に `strata prefill: layer-major ... tokens in ... super-chunk(s) of up to ...` が stderr に出て、実際に採用したサイズや VRAM/pinned RAM 配置などが示されます（`src/prefill/prefill.cpp:7254-7271,7159-7167`）。実行中の CUDA 処理や同期が失敗した場合は `run_layer_major()` の error を返し、通常 prompt では `Prefill::run()` が false を返します。複数 prompt の準備失敗は `prefill: multi-prompt read declined: ...` となり、co-read 呼び出し元がその prefix を検出して通常 read に fallback します（同 `:6188-6206,7254-7263`; `src/program/generate.cpp:15218-15224`）。

## 根拠

- 候補名の読み取り、変換と cache: `src/prefill/prefill.cpp:5910-5913`。
- 目標値、既定値、最小値、chunk 境界への丸め: `src/prefill/prefill.cpp:5932-5934,6024-6032`。
- VRAM に合わせた縮小と準備失敗: `src/prefill/prefill.cpp:6034-6060`。
- layer-major 選択条件および既定の解決: `src/prefill/prefill.cpp:7233-7255`; `include/strata/core/sm120_series.hpp:112-120`。
- 適用除外と実行時エラー理由: `src/prefill/prefill.cpp:5955-6026,7254-7271`。
- 成功ログ、複数 prompt co-read の fallback: `src/prefill/prefill.cpp:7159-7167,6188-6206`; `src/program/generate.cpp:15218-15224`。
