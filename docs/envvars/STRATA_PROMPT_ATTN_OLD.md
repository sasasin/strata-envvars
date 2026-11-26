# `STRATA_PROMPT_ATTN_OLD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

QSA モデルの prompt prefill で、新しいバッチ型 prompt attention（CUDA/HIP の matrix-core / tensor-core 経路、SYCL の prompt kernel）を選ばず、旧 attention 経路へ進ませる診断・A/B 用スイッチです。`1` だけでなく環境変数が存在すれば有効です。QSA 層のないモデルや、prompt の QSA attention に到達しない処理には影響しません。CUDA/HIP 側では旧経路へ進んだ後に `STRATA_PATTN_SM60` の専用経路が使われる場合があります。(`engine/src/prefill/prefill.cpp:5533-5570,9459-9472`; `engine/sycl/src/prefill/prefill.cpp:3846-3895`)

## 値と判定

CUDA/HIP の prefill 実装に 2 箇所、SYCL 実装に 1 箇所あり、いずれも `static const bool old_attn = std::getenv("STRATA_PROMPT_ATTN_OLD") != nullptr;` で判定します。値の parse、数値変換、空白除去、大文字小文字変換はありません。(`engine/src/prefill/prefill.cpp:5540,9462`; `engine/sycl/src/prefill/prefill.cpp:3853`)

| 実装経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP prefill の両 QSA 経路、SYCL prefill | 新しい attention 経路を試す | 空文字、`0`、`1`、`false`、任意の文字列（環境変数が存在するすべての場合） | 該当なし。未設定だけが無効 |

このスイッチ自体に数値の境界や無効値はありません。CLI 引数や設定ファイルからこの値を読む実装は見つからず、別の値で上書きされません。

## 有効になる条件

- 該当エンジンが CUDA/HIP または SYCL の prefill 実装を使い、QSA 層の attention 分岐に入ることが必要です。設定があっても、その処理に到達しなければ読み取り箇所は実行されません。CUDA/HIP のコードは QSA attention の計算後に出力 gate と投影へ続きます。(`engine/src/prefill/prefill.cpp:5533-5575,9459-9479`; `engine/sycl/src/prefill/prefill.cpp:3846-3903`)
- CUDA/HIP では `old_attn` が真だと `gated` は偽になり、`qsa_prompt_attn_batch` を呼ばずに fallback へ進みます。通常の旧 fallback は `qsa_decode_attn_batch` を `m.attn_batch` 件ずつ呼びます。(`engine/src/prefill/prefill.cpp:5540-5544,5556-5569,9462-9472`)
- ただし CUDA/HIP の最初の prefill 経路では、`STRATA_PATTN_SM60` が有効で、ビルドに sm_6x kernel が含まれ、GPU が対応し、バッファ条件を満たすと `qsa_pattn_batch` が先に試されます。成功すればその専用 kernel が使われ、非対応・拒否・起動失敗なら通常の decode attention に戻ります。`STRATA_PATTN_SM60` が存在するだけでなく、`atoi` の結果が 0 でないことが必要です。ビルドに kernel がなければ警告して通常経路を使います。(`engine/src/prefill/prefill.cpp:5556-5569`; `engine/src/kernels/cuda/qsa_pattn.cu:25-50,402-448`)
- SYCL では `old_attn` により `qsa_prompt_attn_batch` を呼ばず、fallback の query chunk ループへ進みます。その中で `STRATA_SYCL_TLA_ATTN=1`、chunk が 32 query、`m.cap == 2051` なら TLA kernel が先に試されます。それ以外では `STRATA_ATTN_PERCELL` が未設定または先頭文字が `0` 以外なら per-cell kernel、先頭文字が `0` なら `qsa_decode_attn_batch` が使われます。したがって SYCL でこの変数が有効でも、後段の条件次第で decode kernel 以外の旧 fallback kernel が選ばれます。(`engine/sycl/src/prefill/prefill.cpp:3873-3895`)
- 通常の CUDA/HIP kernel batch が未設定時に使えるかは GPU、KV format、形状、ビルドにも依存します。例えば CUDA の Q4_0 KV は `STRATA_PROMPT_ATTN_Q4`、Volta/Turing の条件などで batch kernel が拒否され得ます。`STRATA_PROMPT_ATTN_OLD` を設定すると、それらの対応可否判定より前に batch kernel を迂回します。(`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2534`)
- Metal の prefill 実装にこの名前の読み取りはありません。CUDA の `qsa_pattn` 経路も Metal ではコンパイル対象外です。(`engine/src/prefill/prefill.cpp:5558-5564`)

## 実行時の詳細

各 `old_attn` は関数内 `static` で、該当コード経路が初めて実行されたときに環境を読み、その後はプロセス内で値をキャッシュします。CUDA/HIP の 2 箇所は別々の static 変数なので、それぞれ最初に通った時点の値を保持します。通常の起動時設定では実行中の変更は反映されません。子プロセスへの転送や上書き処理はこの読み取り箇所にはありません。(`engine/src/prefill/prefill.cpp:5540,9462`; `engine/sycl/src/prefill/prefill.cpp:3853`)

スイッチが変えるのは QSA prompt attention の kernel 経路です。選択済み cell や KV をこの分岐で書き換える処理はなく、attention 出力を計算して後続の gate・projection に渡します。旧 kernel と新 kernel の数値的一致や出力品質は、このソース分岐だけからは保証できません。新 kernel の説明では decode kernel と bitwise 一致しない旨が記載されていますが、それは本変数の実行時測定結果ではありません。(`engine/src/prefill/prefill.cpp:5533-5575`; `engine/sycl/src/prefill/prefill.cpp:3846-3903`; `engine/include/strata/kernels/qsa_prompt_attn.hpp:1-18`)

## ログと測定値

- CUDA/HIP の最初の prefill 経路では QSA 層処理で一度、`strata prefill: QSA layers: norm + rope in one pass %s, attention gate in the attention epilogue %s\n` を stderr に出します。この変数が設定されていると `gated` が偽なので、2 つ目の値は `off` です。これは gate fusion の状態を示すログで、old attention kernel を選んだことを直接示すメッセージではありません。(`engine/src/prefill/prefill.cpp:5542-5551`)
- 本変数を有効にしたこと自体に対するログや警告はありません。通常の decode fallback で不正な形状・バッファが渡ると `qsa_decode_attn_batch: unsupported geometry or missing buffers` を出して `exit(1)`、kernel 起動エラーでは `qsa_decode_attn_batch: <CUDA error>` を出して `exit(1)` します。sm_6x 専用経路の起動失敗は一度だけ警告し、通常 attention に戻ります。(`engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1147`; `engine/src/kernels/cuda/qsa_pattn.cu:438-446`)
- 性能測定値は記載しません。関連する `docs/bench-results/2026-10-03-v100-prompt-attn/README.md` は旧 commit `99f3dbd` と特定の V100 環境の測定であり、今回の HEAD の測定ではありません。現行 `docs/NVIDIA_V100.md:43-44` の記述（Volta で変数設定時に decode kernel）とは現行ソースの分岐が一致します。(`engine/src/prefill/prefill.cpp:5537-5569`; `engine/sycl/src/prefill/prefill.cpp:3850-3895`)

## 根拠

- 全参照検索では値を読む本番ソースは上記の CUDA/HIP 2 箇所と SYCL 1 箇所です。その他の一致はコメント、`docs/`、`terminal/data/settings-register.json` の設定登録です。ヘルパー経由の読み取りはありません。
- CUDA/HIP の prefill 分岐: `engine/src/prefill/prefill.cpp:5533-5575,9459-9479`
- SYCL の prefill 分岐と追加 fallback 条件: `engine/sycl/src/prefill/prefill.cpp:3846-3903`
- 新 prompt attention kernel の対応条件: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2534`; `engine/include/strata/kernels/qsa_prompt_attn.hpp:27-30`
- sm_6x fallback とログ: `engine/src/kernels/cuda/qsa_pattn.cu:25-50,402-448`
- 旧 decode kernel のエラー・終了経路: `engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1147`
