# `STRATA_OLD_SAMPLER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA sampler とその SYCL 移植版で、通常の sampled-token 処理に使う kernel 経路を旧 `sampler_kernel` に切り替えます。既定の split top-k 経路より旧実装を選ぶための内部切り替えです。設定が影響するのは sampled（`greedy == false` かつ `temperature > 0`）経路で、greedy / `temperature <= 0` はこの設定を参照せず greedy kernel に進みます。実装コメントでは旧経路を engine 0.1.20 の reference としていますが、ここでは token 出力の同一性や性能を独自に検証していません。

## 値と判定

`env_flag()` は `getenv()` の値が存在し、空文字ではなく、文字列全体が厳密に `"0"` と等しくない場合に true を返します。数値 parse や先頭文字だけの判定ではありません。

| 値 | 旧 sampler の選択 |
|---|---|
| 未設定 | しない |
| 空文字 | しない |
| `0` | しない |
| `1` | する |
| `00`、`0 `、`false`、その他の非空文字列 | する |

大文字小文字を変換せず、空白除去もありません。したがって `false` は false 値として扱われず、旧 sampler を選びます。`STRATA_SAMPLER_ONE_BLOCK` も true の場合は `STRATA_OLD_SAMPLER` の判定が先なので旧 sampler が優先されます。旧 sampler が選ばれない場合、one-block 指定があれば one-block を選び、それもなければ split 経路を選びます（`src/kernels/cuda/sampler.cu:1123-1141`、`sycl/src/kernels/cuda/sampler.dp.cpp:1290-1304`）。

## 有効になる条件

- CUDA sampler 実装（`src/kernels/cuda/sampler.cu`）または SYCL 移植版（`sycl/src/kernels/cuda/sampler.dp.cpp`）が使われる実行ファイルで有効です。両方の `sample_tokens()` は sampled 経路で `sampled_path()` を参照します（`src/kernels/cuda/sampler.cu:1260-1311`、`sycl/src/kernels/cuda/sampler.dp.cpp:1472-1653`）。
- greedy 要求および `temperature <= 0` では sampled-path 分岐より先に greedy kernel が選ばれるため、この環境変数は経路を変えません（同上）。
- speculative verify 用 split sampler は `sampled_path() != Split` の場合に利用不可を返します。通常の verify では呼び出し元が通常の `sample_tokens()` に fallback し、旧経路を使います。計測用 proposal sampler が unavailable で、呼び出し元の `measure` が有効な場合は `verify: proposal sampler unavailable or allocation/copy/launch failed` で失敗します（`src/kernels/cuda/sampler.cu:1368-1412`、`src/core/verify.cpp:3363-3398`）。
- `strata-dsv41` は別の vendored sampler をビルドし、その `sample_tokens()` は greedy 以外では `sampler_kernel` を直接起動します。そこに `STRATA_OLD_SAMPLER` の読み取りはなく、この変数による経路切り替えはありません（`CMakeLists.txt:906-919`、`src/dsv41/vendor/sampler.cu:688-727`）。
- ソースに OS やモデル状態による追加の値判定はありません。CLI 引数や設定ファイルからこの変数を上書きする処理も、候補名の全参照検索では見つかりませんでした。

## 実行時の詳細

設定値の読み取りは `env_flag("STRATA_OLD_SAMPLER")` から行われ、`sampled_path()` の関数内 `static const SampledPath` にプロセス内で一度だけ保存されます。初回の `sampled_path()` 呼び出し以降に環境を変更しても再評価されません。通常の sampled 呼び出しでは、旧経路が選ばれると CUDA は `sampler_kernel<<<...>>>`、SYCL は対応する `sampler_kernel` work-group を起動します。旧経路でなければ、条件を満たすと split top-k、split が使えない場合は one-block kernel に進みます（`src/kernels/cuda/sampler.cu:1137-1141,1285-1318`、`sycl/src/kernels/cuda/sampler.dp.cpp:1299-1303,1534-1662`）。

環境変数そのものについての専用ログ、警告、値の拒否処理はありません。CUDA 側で sampler kernel の launch が失敗すると stderr に `sample_tokens launch: <CUDA error>` を出して `exit(1)` します。null stream の場合は最後に `cudaDeviceSynchronize()` を呼びます（戻り値はこの箇所で検査しません）。SYCL 側は queue に処理を投入し、null stream の場合は queue を wait します（`src/kernels/cuda/sampler.cu:1313-1318`、`sycl/src/kernels/cuda/sampler.dp.cpp:1654-1662`）。

## 根拠

- `src/kernels/cuda/sampler.cu:1123-1141` — `SampledPath`、共通値判定、旧 sampler 優先順位、static cache。
- `src/kernels/cuda/sampler.cu:1260-1318` — CUDA `sample_tokens()` の greedy / sampled 分岐、kernel 選択、launch 失敗時の stderr と終了。
- `src/kernels/cuda/sampler.cu:1368-1412` — speculative split sampler が旧経路では利用不可を返す条件。
- `sycl/src/kernels/cuda/sampler.dp.cpp:1290-1304,1472-1662` — SYCL 版の値判定、cache、経路選択。
- `src/core/verify.cpp:3363-3398` — speculative sampler 不成立時の通常 sampling fallback と計測用失敗経路。
- `CMakeLists.txt:906-919`、`src/dsv41/vendor/sampler.cu:688-727` — DSV41 の別 sampler 経路。この環境変数を参照しない。
