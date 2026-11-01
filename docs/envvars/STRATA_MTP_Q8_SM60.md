# `STRATA_MTP_Q8_SM60`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP drafter が使う Q8_0 重みの一部を、Pascal 向け Q8_0 GEMV の登録形式へ変換する opt-in です。対象は `dense.bin` の drafter projection 9 個と、所有する draft head の語彙 subset です。projection は別領域へパックし、draft head は可能なら既存領域内でパックします。これにより MTP の Q8_0 行列を `native_mmvq` 経由で Pascal GEMV に渡せるようにします（`src/core/mtp.cpp:77-85,349-371,782-787`; `src/kernels/cuda/native_mmvq.cu:2824-2854,2890-2920`）。

この変数単独では Pascal 経路を有効にしません。基盤側の `STRATA_Q8_SM60` も文字列全体が `"1"` である必要があります（後述）。

## 値と判定

MTP 側は `std::getenv()` の結果について、未設定でなく先頭文字が `'1'` かだけを確認します。文字列全体の parse、数値変換、大文字小文字変換はしません（`src/core/mtp.cpp:80-85`）。

| 値 | MTP 側の判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| `1` | ON |
| `10`, `1anything` | ON（先頭文字だけで判定） |
| `0`, `true`, `false`, ` 1` など | OFF |

有効な値でも、Q8_0 以外の重みやパック条件を満たさない形状は対象になりません。パック処理が失敗した場合は、その重みについて GGUF の元レイアウトを維持する fallback があります（`src/core/mtp.cpp:356-371,782-787`; `src/kernels/cuda/native_mmvq.cu:2824-2847,2890-2919`）。

## 有効になる条件

- MTP drafter がロードされる必要があります。CLI では `--mtp` が指定され、`--spec` が 2 以上でなければ MTP は無効化されます。`--mtp` のロードが失敗すれば `strata generate` はエラーを stderr に出して終了コード 1 を返します（`src/program/generate.cpp:6281-6298`）。
- 実際の Q8_0 Pascal パッキングは CUDA 実装です。HIP 側の `q8_sm60_on()` と pack 関数は常に false を返し、Metal の `MtpDrafter::load()` は Metal drafter のロードへ早期 return するため、この MTP 判定を使う処理に進みません（`src/core/mtp.cpp:265-273`; `src/kernels/cuda/native_mmvq.cu:2466-2478,2824-2829,2890-2895`）。
- `STRATA_Q8_SM60` がちょうど `"1"` であることも必要です。値が未設定、空、`10`、`1anything` などは基盤側で OFF です。したがって `STRATA_MTP_Q8_SM60` の prefix 判定とは異なります（`src/kernels/cuda/native_mmvq.cu:2464-2477`）。
- projection は `shared == nullptr` かつ `dense4_ == nullptr` の場合に限りパックを試みます。9 個の必須 projection のうち、存在し `q8_0` 型で、native pack helper の対象形状・割り当て条件を満たすものだけが登録されます。`--mtp-q4` によって `dense4_` ができた場合、projection の Q8_0 パック分岐は通りません（`src/core/mtp.cpp:349-371`; `src/kernels/cuda/native_mmvq.cu:2802-2805,2824-2840`）。
- draft head は `dhead_type_ == GGML_Q8_0`、この drafter が head を所有していること、行バイト数が `n_embd / 32 * 34` と一致すること、および native pack 条件を満たすことが必要です。共有 drafter では `owns_draft_head_` が false なので、slot drafter ごとに head を再パックしません（`src/core/mtp.cpp:282-293,782-787`; `src/kernels/cuda/native_mmvq.cu:2802-2805,2890-2900`）。
- `src/core/mtp.cpp` の環境変数 helper 自体は GPU 世代を調べません。SM60 対応コードを含む CUDA build と対応する実行環境が必要ですが、この環境変数の読み取り箇所だけから build のアーキテクチャ設定や実 GPU の可否を追加で保証することはできません。

## 実行時の詳細

`mtp_q8_sm60()` は関数内 `static const bool` に判定結果を保存します。最初の評価後にプロセス環境を書き換えても再判定されません。通常は MTP の `load()` 内で projection パッキング条件を調べる際に最初に呼ばれます。head の分岐も同じ cache を使います（`src/core/mtp.cpp:80-85,356-357,782-785`）。

projection 側では `fc_embedding.weight`, `fc_hidden.weight`, `self_attn.{q,k,v,o}_proj.weight`, `mlp.shared_expert.{gate,up,down}_proj.weight` の 9 tensors を順に調べます。pack helper が成功した数と追加 VRAM を `vram_` に加算し、成功数が 1 以上なら stderr に `strata mtp: N of 9 projections on the Pascal Q8_0 GEMV ...` を出します。成功数 0 の場合、この MTP 集計ログは出ません（`src/core/mtp.cpp:349-371`）。

draft head は同じ環境条件のもとで in-place pack を試み、成功時に `strata mtp: the draft head on the Pascal Q8_0 GEMV (STRATA_MTP_Q8_SM60=1)` を stderr に出します。helper はメモリ条件や 16-byte alignment によって別領域 pack に切り替えることがあり、VRAM 不足、読み書き失敗時には `strata q8 sm60: ...` の stderr ログを出して失敗を返します。元 layout を維持または復元できない旨を含むログもあります（`src/core/mtp.cpp:782-787`; `src/kernels/cuda/native_mmvq.cu:2833-2847,2890-2919`）。

MTP の projection は `record_rest()` などから `native_mmvq()` に渡されます。登録に成功した重みは、native MMVQ の Pascal 分岐で Q8 SM60 kernel に渡されます。Pascal kernel がその呼び出しを受けられないとき、実装は条件に応じて exact packed kernel または通常 GGUF layout の経路を残します（`src/core/mtp.cpp:1041-1085`; `src/kernels/cuda/native_mmvq.cu:2587-2614`）。draft head の subset も `native_mmvq()` で読む経路に限られ、コメント上、prompt path はこの packed subset を読まず GGUF layout を使います（`src/core/mtp.cpp:782-785,1242`）。

## 根拠

- 環境変数の読み取り、prefix 判定、static cache: `src/core/mtp.cpp:77-85`。
- drafter projection の対象と pack / 成功ログ: `src/core/mtp.cpp:349-371`。
- draft head の対象、所有条件、成功ログ: `src/core/mtp.cpp:782-787`。
- MTP 起動条件、load 失敗時の stderr と終了: `src/program/generate.cpp:6281-6298`。
- 基盤変数 `STRATA_Q8_SM60` の完全一致判定、HIP の no-op、ログ: `src/kernels/cuda/native_mmvq.cu:2464-2478`。
- Q8 pack 対象形状、割り当て・pack 失敗 fallback: `src/kernels/cuda/native_mmvq.cu:2794-2805,2824-2854,2890-2920`。
- 登録重みの native MMVQ 分岐: `src/kernels/cuda/native_mmvq.cu:2587-2614`。
