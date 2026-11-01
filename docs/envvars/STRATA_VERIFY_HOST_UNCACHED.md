# `STRATA_VERIFY_HOST_UNCACHED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL verifier が使うホスト共有バッファの割り当て方法と、stepped verify の doorbell payload store を切り替えます。`STRATA_VERIFY_STEPPED` が無効ならこの変数の値にかかわらず uncached 側が選ばれます。stepped verify が有効なときは、この変数も有効にしない限り、通常の host USM と plain payload store を選びます（`sycl/src/core/verify.cpp:94-105,220-229,231-243,1783-1789`）。

## 値と判定

`env_on()` は値を数値や真偽値として parse せず、設定があり、空文字でなく、先頭文字が `0` でないことだけを調べます（`sycl/src/core/verify.cpp:94-97`）。この判定は `window_host_uncached()` 内の `static const bool` に保存されるため、最初の呼び出し以降に環境を変更しても再評価されません（同 `:226-229`）。

| `STRATA_VERIFY_STEPPED` | `STRATA_VERIFY_HOST_UNCACHED` | `window_host_uncached()` |
|---|---|---|
| 無効（未設定、空、または先頭が `0`） | 任意 | `true`（この変数は判定に使われない） |
| 有効 | 未設定、空文字、先頭が `0` | `false` |
| 有効 | 空でなく、先頭が `0` 以外 | `true` |

したがって stepped 時は `1`, `true`, `false`, `2`, `anything` が有効で、`0`, `0anything`, 空文字は無効です。大文字小文字、後続文字、空白、数値としての妥当性は検査しません。CLI 引数や設定ファイルによるこの変数の上書きは実装にありません。

## 有効になる条件

- 対象コードは SYCL verifier (`sycl/src/core/verify.cpp`) です。CUDA/HIP verifier でこの名前を読む箇所はありません。ソース上で `STRATA_VERIFY_STEPPED` は Arc A-series 向け opt-in と記され、stepped mode では doorbell window を segment に分けます（`sycl/src/core/verify.cpp:103-105,1830-1837,2160-2164`）。
- stepped mode で segmented verify を使うのは、all-resident (`ar_on()`) でなく、`STRATA_VERIFY_EAGER` が未設定の経路です（同 `:1830-1837`）。このとき `STRATA_VERIFY_HOST_UNCACHED` は割り当て方式に加え、segment の publish payload を plain store にするかにも作用します。
- `STRATA_VERIFY_EAGER` が設定されている場合や all-resident 経路では `capture_segments()` を通らないため、`PlainPayload` による plain store の切り替えは行われません。ただし `mapped()` は verifier の staging 領域に共通して `window_host_uncached()` を参照します（同 `:231-243,1830-1837`）。
- 実際に Level Zero の uncached host allocation を得るかは、この変数だけでは決まりません。`host_malloc_polled()` は `STRATA_HOST_UNCACHED` が未設定または先頭文字が `0` でないこと、Level Zero 関連ヘッダーがビルド時に存在すること、queue backend が Level Zero であることを条件に `zeMemAllocHost` を試します。それ以外や確保失敗時は `sycl::malloc_host` に fallback します（`sycl/include/strata/sycl_queue.hpp:48-53,63-78`）。
- segmented verify で plain store を使うかは `STRATA_DOORBELL_PLAIN` による既定判定とも合成されます。`doorbell_plain_payload()` は設定時に先頭文字が `1` なら true、その他なら false、未設定時は i915 driver 判定を返し、publish 側はこの値または stepped window が設定する plain flag のどちらかが true なら plain store を選びます（`sycl/include/strata/sycl_doorbell.hpp:100-112`, `sycl/src/kernels/cuda/elementwise.dp.cpp:629-636,736-768`）。

## 実行時の詳細

`Verifier::init()` は token、step、position、doorbell、expert payload、plan などの mapped staging 領域を `mapped()` で確保します（`sycl/src/core/verify.cpp:527-553`）。`window_host_uncached()==true` なら `host_malloc_polled()`、false なら `sycl::malloc_host()` を選びます。前者を選んでも、前節の backend・build・`STRATA_HOST_UNCACHED` 条件により Level Zero 特殊確保が使われない場合があります。確保に失敗すると初期化エラー `verify: mapped staging allocation failed`（plan 領域では `verify: mapped plan allocation failed`）になります。SYCL exception は `exc.what()` とソース位置を stderr に出して `exit(1)` します（同 `:239-249,543-552`）。解放時は同じ補助 API の `host_free_polled()` を使います（同 `:452-455`; `sycl/include/strata/sycl_queue.hpp:79-90`）。

segmented verify では `capture_segments()` の RAII guard が、`!window_host_uncached()` を `doorbell_plain_payload(bool)` に設定し、capture 終了時に false に戻します（`sycl/src/core/verify.cpp:1783-1789`）。この flag は publish kernel の payload store に渡されます（`sycl/src/kernels/cuda/elementwise.dp.cpp:629-640,736-768`）。従って stepped 時に本変数が有効なら、この guard は plain store を強制せず、無効なら segment capture 中に plain store を有効にします。`STRATA_DOORBELL_PLAIN` が独立に plain を選んでいる場合はその設定も反映されます。

本変数自体を理由とするログや警告はありません。コードコメントは、stepped mode が segment の完了後に payload を読み、既定の uncached host memory と uncached payload store を避けられる設計だと説明しています（`sycl/src/core/verify.cpp:220-225`; `sycl/src/kernels/cuda/elementwise.dp.cpp:629-632`）。本変数が直接変えるのはその選択です。環境値による性能効果はこの調査で測定していません。

## 根拠

- 全リポジトリで `STRATA_VERIFY_HOST_UNCACHED` を検索し、実際に環境値を読む箇所は `sycl/src/core/verify.cpp:227` の一箇所と確認しました。もう一つの一致は直前の説明コメント (`:225`) です。helper の値判定は同ファイル `:94-97`、読み取り時期と既定は `:103-105,220-229` です。
- staging の割り当てと失敗経路: `sycl/src/core/verify.cpp:231-249,527-553`; Level Zero 条件・fallback・free: `sycl/include/strata/sycl_queue.hpp:48-90`。
- stepped segmented capture と doorbell payload の連携: `sycl/src/core/verify.cpp:1783-1789,1830-1837`; plain flag と publish 経路: `sycl/src/kernels/cuda/elementwise.dp.cpp:629-640,736-768`; doorbell の既定値: `sycl/include/strata/sycl_doorbell.hpp:100-112`。
