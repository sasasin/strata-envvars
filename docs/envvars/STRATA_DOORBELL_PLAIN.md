# `STRATA_DOORBELL_PLAIN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の doorbell がホスト可視メモリへ payload（activation、expert ID、routing weight）を書き込むとき、通常のストアを使うか、L1/L3 を uncached にする書き込みヒント付きストアを使うかを選びます。doorbell の sequence/ring flag の書き込み方式はこの変数では切り替わりません。

## 値と判定

`sycl/include/strata/sycl_doorbell.hpp` の `doorbell_plain_payload()` は `std::getenv()` の結果が未設定かどうかを先に調べます。設定されていれば文字列全体や数値としては parse せず、先頭文字が `'1'` かだけを比較します。

| 値 | 関数の結果 |
|---|---|
| 未設定 | `intel_gpu_driver() == "i915"` の場合だけ true。それ以外（`xe`、空文字＝不明を含む）は false |
| 空文字 | false（設定済みなので driver 既定値を使わない） |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | true |
| その他（例: `0`, `true`, ` 1`, `2`） | false |

大文字小文字や後続文字は解釈されません。結果は関数内の `static const bool` に保存されるため、初回評価後にプロセス環境を変更しても再評価されません。driver 判定も `intel_gpu_driver()` 内の static 値として `/sys/class/drm` から一度だけ取得されます。

## 有効になる条件

- この判定は `sycl/include/strata/sycl_doorbell.hpp` と `sycl/src/kernels/cuda/elementwise.dp.cpp` にある SYCL doorbell 実装で使われます。CUDA/HIP のネイティブ doorbell 実装には、この変数を読む参照はありません。
- 通常経路では、設定値または既定値が true のとき payload の書き込みに通常ストアを使い、false のとき uncached L1/L3 書き込みヒントを使います。
- verifier の stepped capture 中は別の一時フラグ `g_plain_payload` があり、`capture_segments()` が `!window_host_uncached()` を設定します。このため、環境変数が false でも stepped window の payload は通常ストアになります。`window_host_uncached()` は `g_stepped` が false なら true、stepped 時は `STRATA_VERIFY_HOST_UNCACHED` が有効なら true です。capture 終了時に一時フラグは false に戻ります。
- `STRATA_VERIFY_HOST_UNCACHED` の有効判定そのものは別変数の実装に従います。この文書では相互作用のみを記載します。

## 実行時の詳細

`doorbell_publish()`、`doorbell_publish_value()`、`doorbell_publish_res()` の各 host launcher が `doorbell_plain_payload()` と stepped capture の一時フラグを OR し、その bool を SYCL kernel に渡します。kernel は payload の activation、ID、weight の各要素について `sys_store_mapped(plain, ...)` を呼びます。`plain` が true なら `*p = v`、false なら uncached L1/L3 write hint の `annotated_ptr` を通して書きます。どの publish variant もこの値を使います。

この切り替えは payload に限られ、doorbell ring と sequence の公開は別の `sys_store()` 経路で行われます。Strata の実装コメントは、i915 では通常ストアが使える一方、xe では host USM の payload を kernel 実行中にホストが読むため uncached hint が必要だと説明しています。また stepped verifier では payload 読み取りを segment 完了後に行うため、uncached hint を省く一時 override が設けられています。これらはソースコメントに記載された設計根拠であり、この調査で性能を測定したものではありません。

## 根拠

- `sycl/include/strata/sycl_doorbell.hpp:100-112` — 通常ストアと uncached store の選択、環境変数の先頭文字判定、i915 既定値。
- `sycl/include/strata/sycl_queue.hpp:101-115` — `/sys/class/drm` からの Intel GPU driver 判定と static cache。
- `sycl/src/kernels/cuda/elementwise.dp.cpp:628-635,637-709` — payload store が `plain` を使う箇所と stepped capture 用一時フラグ。
- `sycl/src/kernels/cuda/elementwise.dp.cpp:735-796` — 各 doorbell publish launcher が環境判定と一時 override を合成して kernel に渡す箇所。
- `sycl/src/core/verify.cpp:218-227,1687-1693` — stepped window の uncached memory 条件と capture 中の一時 override。
- `sycl/src/core/verify.cpp:1335-1359` — verifier からの doorbell publish 呼び出し。
- `docs/DETAILS.md` および `docs/INTEL.md` — doorbell 関連の説明を確認。`STRATA_DOORBELL_PLAIN` 固有の値判定や挙動の説明は見つからず、上記の値と条件は実装コードを根拠とした。
