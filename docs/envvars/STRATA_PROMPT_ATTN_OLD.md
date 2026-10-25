# `STRATA_PROMPT_ATTN_OLD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA 層の prompt prefill で使う attention の実装を切り替えます。通常は `qsa_prompt_attn_batch()` が利用可能なら prompt 向けの batch kernel を使い、利用できないときは各 query を `qsa_decode_attn_batch()` に渡します。この変数が設定されていると前者を呼ばず、後者に切り替えます。decode / verify の attention 経路にはこの変数の参照がありません。

CUDA/HIP 側と SYCL 側の prompt 実装に同じ分岐があります。SYCL 側では prompt batch kernel が XMX kernel なので、この変数を設定すると `STRATA_PROMPT_ATTN_XMX` が有効でも XMX prompt kernel を呼ばず decode kernel 側へ進みます。

## 値と判定

値の内容は parse せず、`std::getenv("STRATA_PROMPT_ATTN_OLD") != nullptr` だけを判定します。

| 環境変数の状態 | `old_attn` | 動作 |
|---|---:|---|
| 未設定 | false | batch prompt kernel を試す。利用不可なら decode kernel へ fallback |
| 設定済み（空文字を含む） | true | batch prompt kernel を呼ばず、decode kernel を使う |

したがって `=0`、`=false`、空文字も有効化と同じ扱いです。値の大文字小文字や数値としての妥当性は検査しません。

## 有効になる条件

- 実行中の prompt に QSA 層があり、該当する QSA prefill 分岐に到達した場合に作用します。QSA 層でない処理や decode / verify window の経路には適用されません。
- CUDA/HIP 側では `old_attn` が true の場合に `qsa_prompt_attn_batch()` を短絡し、`qsa_decode_attn_batch()` の query batch loop を実行します。未設定時も prompt batch kernel が shape、pool、デバイス条件などを満たさず `false` を返す場合は同じ fallback です。
- SYCL 側でも `old_attn` が true なら prompt XMX kernel を呼びません。未設定時は `qsa_prompt_attn_batch()` が XMX kernel を試し、未対応・未使用なら decode kernel に fallback します。
- 参照箇所は通常の `src/` と `sycl/src/` のソースにあります。ビルドに含まれる backend と実行デバイスがその QSA prefill 経路を使う場合に限り効果があります。

## 実行時の詳細

両方の prompt 実装で、QSA attention の直前に関数内 `static const bool old_attn` として判定結果を初期化します。最初にこの行へ到達したときの設定有無がプロセス内に保存され、以後環境変数を変更しても再評価されません。値による専用ログ出力はありません。

CUDA/HIP 側は `old_attn || !qsa_prompt_attn_batch(...)` の条件です。`old_attn` が true なら左辺で短絡するため batch kernel を呼ばず、`m.attn_batch` 単位の loop で `qsa_decode_attn_batch()` を実行します。batch kernel を試す場合も、同関数が false を返せば同じ loop に入ります。SYCL 側も同じ呼び出し構造で、prompt batch 関数の実装は `qsa_prompt_attn_xmx()` を試します。フォールバックは query を `m.attn_batch` ごとに処理し、出力後の処理（必要な場合の FWHT、attention gate、projection）へ続きます。

## 文書との照合

`docs/NVIDIA_V100.md` は V100 の QSA prompt attention について、通常時の `prompt_attn_v70_kernel` と `STRATA_PROMPT_ATTN_OLD=1` 時の decode kernel を区別しています。同ページの記載では、V100-PCIE-32GB、i9-7960X、Unsloth `UD-IQ4_XS`、int8 KV、MTP `--spec 2` の random-word prompt 測定で、通常の prompt kernel が 7,194 / 28,650 / 114,338 token の各条件で 1,164 / 1,251 / 1,123 tok/s、old attention path が 1,010 / 1,063 / 973 tok/s でした。これはその記載条件での結果であり、他のデバイスやモデルでの速度差は示しません。同ページは decode が影響を受けなかったとも記載していますが、環境変数の読み取り箇所自体も decode 経路にはありません。

`docs/OLDER_GPUS.md` は `STRATA_PROMPT_ATTN_OLD=1` を prompt で decode kernel を使う A/B switch と説明しており、実装の分岐と一致します。`docs/DETAILS.md` にはこの変数固有の説明や測定値を確認できませんでした。

## 根拠

- `src/prefill/prefill.cpp:2654-2665,2862-2878` — QSA prefill の分岐、設定有無判定、batch kernel から decode kernel への fallback。
- `sycl/src/prefill/prefill.cpp:3157-3164,3184-3192` — SYCL 側の同じ判定と fallback。
- `include/strata/kernels/qsa_prompt_attn.hpp:27-30` — prompt batch kernel が非対応条件で false を返し caller が旧 kernel を使う契約。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2007-2010` — SYCL prompt batch 側が XMX kernel を試し、利用されなければ false を返す処理。
- `sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:364-383` — SYCL prompt batch kernel の値・device memory 条件と XMX dispatch。
- `docs/NVIDIA_V100.md:28-35,47-58`; `docs/OLDER_GPUS.md:98-100` — V100 の kernel 選択と条件付き測定、switch の説明。
