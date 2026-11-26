# `STRATA_PLE_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PLE（n-gram 埋め込みを使う層）の key/value 射影を、プロンプト読み込み時にチャンク単位でまとめて計算するか、各 token で計算するかを切り替える。バッチ処理が実際に選ばれるのは、PLE がモデルにあり、対象レイヤーを処理し、native post-ops と重み形式・スクラッチ領域の条件を満たす場合だけ。CUDA/HIP と SYCL のプロンプト経路、および CUDA/HIP・SYCL の speculative verify 経路で読まれる。verify ではさらに複数行の key/value 射影の経路を選ぶ。`engine/src/prefill/prefill.cpp:4327-4333,5012-5064`、`engine/sycl/src/prefill/prefill.cpp:2772-2782`、`engine/src/core/verify.cpp:1698-1717`、`engine/sycl/src/core/verify.cpp:1137-1156`。

## 値と判定

プロンプト経路は `std::getenv` の結果を初回呼び出し時に `static const char*` に保存し、設定値を `std::atoi` に渡して `!= 0` で判定する。したがって空文字は 0、`0anything` も 0、`1anything`・`-1` は非 0。`true`、空白だけの値、整数として読み始められない文字列は 0 になる。`" 1"` は先頭空白の後の `1` が変換されて有効。先頭の空白は `atoi` が読み飛ばし、整数として読める部分の後ろは無視する。大文字小文字の比較はしない。未設定時だけ backend・CUDA toolkit・GPU で既定値が決まる。CUDA 側は `engine/src/prefill/prefill.cpp:94-116` と `engine/include/strata/core/sm120_series.hpp:44-57`、SYCL 側は `engine/sycl/src/prefill/prefill.cpp:2772-2782`。

| 経路・条件 | unset | 有効になる設定値 | 無効になる設定値 |
|---|---|---|---|
| CUDA/HIP prompt prefill | 原則 ON。CUDA 12.8（`CUDART_VERSION` 12080–12089）で compute capability 12.0 のときだけ OFF。HIP build はこの CUDA 12.8 例外の対象外 | `atoi(value) != 0`。例: `1`, `-1`, `1tail`, ` 1` | `atoi(value) == 0`。例: 空文字, `0`, `0tail`, `true` |
| SYCL prompt prefill | ON | `atoi(value) != 0`（例は上と同じ） | `atoi(value) == 0`（例は上と同じ） |
| CUDA/HIP・SYCL verify の `ple_batch_kv` 判定 | ON（設定有無だけを使い、先頭文字が `0` でなければ ON） | unset または先頭が `0` 以外。例: 空文字, `1`, `true`, ` 0` | 先頭文字が `0`。例: `0`, `0tail` |
| CUDA/HIP・SYCL verify の `batched` 判定 | OFF | 先頭文字が `1`。例: `1`, `1tail` | unset、空文字、`0`, `true`, ` 1` など先頭が `1` でない値 |

verify の二つの判定は別々の `static bool` であり、一般的な真偽値パーサーではない。`ple_batch_kv` は未設定または先頭文字が `'0'` 以外、`batched` は設定値の先頭文字が `'1'` のときだけ有効。よって、たとえば `true` は `ple_batch_kv` 判定では許可されるが `batched` 判定では無効。`engine/src/core/verify.cpp:1704-1717`、`engine/sycl/src/core/verify.cpp:1143-1156`。

AMD の通常エンジン起動では、RDNA3 discrete の既定値表が候補値 `1` を環境へ設定するため、ユーザーが明示していない場合に verify 側でも ON になる。既に変数が設定済みなら Strata は上書きしない。`STRATA_GFX11_DEFAULTS=0` または `STRATA_DEFAULTS=026` はこの RDNA3 既定値表を抑止する。`engine/include/strata/core/gfx11_extra.hpp:39-73`、`engine/src/core/arch_defaults.cpp:302-323`、`engine/src/program/generate.cpp:4287-4320`。CUDA の prompt 既定値（CUDA 12.8 / 12.0 例外）はこの arch-default 表とは別に決まる。対象名を直接指定する専用 CLI 引数は見つからなかった。`--gpu` は GPU 選択変数を上書きするだけで、本変数の優先順位には関与しない（`engine/src/program/generate.cpp:3781-3802`）。

## 有効になる条件

- **Prompt prefill:** PLE が ready で、処理範囲が layer 1 を含む必要がある。さらに `ple_native_postops_enabled()`、BF16 key または native key の重み、および式で計算される 64 token 分以上のスクラッチ領域が必要。満たさなければ `ple_batch` は false となり、layer 1 で `ple_block` を token ごとに実行する。CUDA/HIP は通常経路と layer-major 経路の両方で同条件を判定する。`engine/src/prefill/prefill.cpp:4327-4333,5012-5064,8470-8474,9216-9268`、SYCL は `engine/sycl/src/prefill/prefill.cpp:2772-2782`。
- **Verify の `ple_batch_kv`:** `STRATA_DEC_BATCH` に由来する `dec_batch` が有効、グループ行数 `n > 1`、key と value が BF16 重み、native BF16 と native PLE post-ops が有効であることが必要。変数が許可しても条件不足ならこの経路を使わない。`engine/src/core/verify.cpp:1708-1710`、`engine/sycl/src/core/verify.cpp:1147-1149`。
- **Verify の `batched`:** `ple_batch_kv` が成立していないこと、変数の先頭文字が `'1'`、`n > 1`、BF16 または native key 重み、および native BF16 が必要。key/value 射影をまとめた後も、履歴に依存する残りの PLE 処理は各行で実行する。`engine/src/core/verify.cpp:1714-1717,1728-1742,1773-1792`、`engine/sycl/src/core/verify.cpp:1153-1156,1167-1205`。
- verify の `STRATA_DF_PLE` は別の後段 post-projection 最適化を制御する。`STRATA_PLE_BATCH` 単独でその経路は有効にならない。`engine/src/core/verify.cpp:1744-1752`。
- CUDA 12.8 build と compute capability 12.0 の組み合わせでは、未設定時に prompt batching が無効になる。明示値は優先され、非ゼロ値で有効化できる。これは prompt 側の既定値規則であり、verify 側に同じ toolkit/GPU 既定値判定はない。`engine/include/strata/core/sm120_series.hpp:44-57`、`engine/src/prefill/prefill.cpp:94-115`。

## 実行時の詳細

CUDA prompt は最初に `ple_batch_enabled()` が呼ばれた時点で環境文字列へのポインタを static 保存する。unset なら各評価時に現在の CUDA device の compute capability を問い合わせて既定値を解決する（問い合わせ失敗時の major/minor は初期値 0）。CUDA 12.8 / 12.0 で無効になった旨の警告はプロセス内で一度だけ出す。SYCL prompt は関数内 static bool を初回評価時に作り、verify の各経路も static bool に判定結果を保存するため、以降の環境変更は再評価されない。`engine/src/prefill/prefill.cpp:94-116`、`engine/sycl/src/prefill/prefill.cpp:2775-2778`、`engine/src/core/verify.cpp:1704-1714`、`engine/sycl/src/core/verify.cpp:1143-1153`。

Prompt の有効時はチャンク内の PLE key/value 射影と native post-ops をバッチ単位で処理し、無効時や条件不足時は `ple_block` を token ごとに呼び出す。どちらの経路でも変数が直接選ぶのは PLE 計算方法であり、CLI の生成設定そのものではない。`engine/src/prefill/prefill.cpp:5012-5064,9216-9268`、`engine/sycl/src/prefill/prefill.cpp:2772-2782`。

Verify は layer 1 の処理で、該当する射影を multi-row kernel にまとめる。例外が起きると `err` に `verify PLE multi: `、`verify PLE batch: `、または `verify PLE: ` を付けてその処理を失敗で返す。Prompt の PLE 例外は `prefill PLE: ` を設定して false を返す。`engine/src/core/verify.cpp:1718-1742,1773-1791`、`engine/sycl/src/core/verify.cpp:1157-1181,1186-1203`、`engine/src/prefill/prefill.cpp:5046-5063`。

## ログと測定値

CUDA 12.8 build / compute capability 12.0 で未設定のため prompt batching を OFF にしたとき、一度だけ stderr に次の警告を出す。明示的に `0` を指定した場合や他の build/device の場合、この警告条件には入らない。

```text
strata prefill: the batched PLE post-ops are off by default here: this engine was built with CUDA 12.8, whose build faults in the prompt path on a compute capability 12.0 card (issues #220, #224). Use an engine built with CUDA 13.0 or newer; STRATA_PLE_BATCH=1 turns it on anyway.
```

`engine/src/prefill/prefill.cpp:112-115`。verify で例外があった場合のエラー接頭辞は「実行時の詳細」に記載した。ソースコメントは RTX PRO 5000 Blackwell の特定測定で CUDA 13.0 以降の prompt batching が約 23% の prompt speed 改善と述べるが、同コメントには OS・モデル条件・測定回数が揃っていないため、一般的な性能値としては扱わない（`engine/include/strata/core/sm120_series.hpp:44-48`）。

## 根拠

- `engine/src/prefill/prefill.cpp:92-117,4327-4333,5012-5064,8470-8474,9216-9268`
- `engine/sycl/src/prefill/prefill.cpp:2772-2782`
- `engine/src/core/verify.cpp:1698-1792`
- `engine/sycl/src/core/verify.cpp:1137-1205`
- `engine/include/strata/core/sm120_series.hpp:44-57`
- `engine/include/strata/core/gfx11_extra.hpp:39-73`
- `engine/src/core/arch_defaults.cpp:302-323`
- `engine/src/program/generate.cpp:3781-3802,4287-4320`
