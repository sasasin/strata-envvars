# `STRATA_COPY_ENGINE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

SYCL の prompt prefill で expert のホスト→GPU コピーを、通常の in-order SYCL queue から GPU の専用 copy queue に移すかを制御します。Strata は Level Zero の copy-only command queue group に immediate command list を作成し、それを SYCL queue として包みます。copy-only queue を作れないときは通常 queue を使います。CUDA/HIP の同名機能を切り替える変数ではなく、この実装は `sycl/` のみです。

## 値と判定

`std::getenv()` の文字列全体や数値を parse せず、先頭文字だけを調べます。値の大文字小文字や後続文字は判定しません。

| `STRATA_COPY_ENGINE` | 処理 |
|---|---|
| 未設定 | Battlemage では専用 queue の作成を試みる。それ以外の Intel GPU 世代では作成しない |
| 空文字 | `0` でも `1` でもない。Battlemage では既定どおり試み、それ以外では作成しない |
| 先頭文字が `0`（例: `0`, `0abc`） | 専用 queue を無効化し、通常 queue にする |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | Battlemage 以外でも専用 queue を作成する経路へ進む |
| その他の設定値（例: `true`, `2`, `false`） | 強制有効にはならない。Battlemage は既定の作成対象、それ以外は対象外 |

`STRATA_COPY_ENGINE` の先頭文字が `0` かどうかは、最初の `make_copy_engine_queue()` 呼び出しで `static const bool` に保存されます。その後プロセス内で値を変更しても、この無効化判定は再評価されません。先頭文字 `1` の強制判定は、デバイスごとの queue がまだキャッシュされていない場合に読みます。したがって、環境変数はプロセス起動前に設定する前提で扱うのが確実です。

根拠: `sycl/src/core/copy_queue.cpp:73-94`。

## 有効になる条件

値が専用 queue の作成を許可しても、実際に使われるのは次の条件を満たす場合です。

- SYCL 実装が Level Zero backend を使っている。CUDA/HIP 等、Level Zero 以外の backend では `nullptr` を返します。
- ビルド時に `<level_zero/ze_api.h>` が利用でき、実装が Level Zero loader から `zeDeviceGetCommandQueueGroupProperties` と `zeCommandListCreateImmediate` を取得できる。
- 対象デバイスに、COPY フラグがあり COMPUTE フラグがなく、queue 数が 1 以上の command queue group がある。
- `SYCL_UR_USE_LEVEL_ZERO_V2` の先頭文字が `0` でない。この変数が設定されていないか、先頭が `0` の場合に legacy adapter を選ぶという外部 runtime 側の意味はここでは説明対象外だが、Strata の実装は先頭 `0` を専用 queue 不使用の条件として明示確認します。
- `STRATA_COPY_ENGINE` が `0` で無効化されていない。また Battlemage 以外では、値の先頭が `1` である必要があります。

いずれかを満たさない場合、専用 queue が無いものとして呼び出し元が通常の in-order queue を作ります。専用 queue の作成時に例外が出た場合も同じ fallback です。デバイスごとに最初の作成結果（`nullptr` を含む）が記録されるので、同じプロセスで後から環境値や利用条件を変えても、そのデバイスの判定はやり直しません。

根拠: `sycl/src/core/copy_queue.cpp:8-12,39-53,73-100,105-139`。

## 実行時の詳細

prompt prefill の `m.copy` queue を初期化する際に専用 queue を要求します。取得できなければ `create_queue(true)` で通常 queue を作成し、それも失敗すると prefill のエラー `prefill: copy stream` を返します。専用 queue が作られた場合、expert の DMA が copy queue に投入されます。stager が DMA 完了を示す sequence number を書く経路では、copy-only queue は `fill`（カーネル）を実行できないため、page-locked host memory 上の値を `memcpy` します。通常 queue の経路では `fill` を使います。

copy queue が初めて実際に作成されたとき、stderr に一度だけ `strata: copy engine: ... copies run on the GPU's copy engine (queue group N), not the compute engine (STRATA_COPY_ENGINE=0 turns it off)` を出します。queue 作成の例外は `strata: copy engine queue not available (...): ordinary queue` として出力されます。backend や queue group が条件に合わず `nullptr` となる場合は、この実装から専用 queue の警告は出ません。

根拠: `sycl/src/prefill/prefill.cpp:503-520,987-994`; `sycl/src/core/copy_queue.cpp:57-69,80-138`。

## 文書・測定値との照合

`docs/INTEL.md:808-817` は、Arc Pro B70（Xe、IQ3_S、記載の専門家配置等）の測定として、copy engine 使用時に 4K prompt が 3.82 秒から 3.25 秒、16K が 15.5 秒から 13.5 秒になったと記載し、Battlemage で既定有効、`=1` で他の Level Zero デバイスにも強制、`=0` で無効と説明しています。同節には A750 での測定値と prompt hang の記録もあります。これらは資料記載の測定であり、ここで再測定した値ではありません。`docs/DETAILS.md` ではこの変数の説明を確認できませんでした。
