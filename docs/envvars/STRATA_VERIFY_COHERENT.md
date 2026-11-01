# `STRATA_VERIFY_COHERENT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

HIP build の verifier が使う mapped host buffer を、通常の guarded mapped allocation ではなく `hipHostMallocCoherent` を含む明示的な coherent allocation で確保する opt-in です。対象は verifier の handshake words / rows と、同じ `mapped()` helper を通る staging・plan 等の host buffer です。CUDA build では `g_coherent` 自体が定義されず、この名前を読みません。

## 値と判定

`env_on()` は `std::getenv()` の結果が null でなく、空文字でもなく、先頭文字が `'0'` でもない場合に true を返します。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
| --- | --- |
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0`（例: `0`, `0anything`） | OFF |
| それ以外の非空文字列（例: `1`, `true`, `false`, `-1`, `2abc`） | ON |

大文字小文字、空白、後続文字は検査しません。CLI 引数や他の環境変数による上書き・優先順位は実装にありません。値は `src/core/verify.cpp` の namespace scope `const bool` 初期化時に一度読み取られます。したがって実行中の環境変更で再評価されません。

## 有効になる条件

- `STRATA_USE_HIP` を定義した HIP build でのみ `g_coherent` を定義し、`mapped()` 内の HIP 分岐で参照します。CUDA build はこの環境変数を読みません (`src/core/verify.cpp:296-306,495-508`)。
- 実際の効果が出るのは verifier の初期化で `mapped()` が呼ばれる場合です。通常の verifier staging / plan allocation がそこで行われます (`src/core/verify.cpp:851-869,918-927`)。Verifier は verify-window 経路で使われ、generate 側にも verifier instance が置かれています (`src/program/generate.cpp:7893-7900,9970-10006`)。
- SYCL verifier (`sycl/src/core/verify.cpp`) にも同じ名前の参照がありますが、`g_coherent` は `STRATA_USE_HIP` 時だけ定義され、SYCL の `mapped()` は `window_host_uncached()` に応じた SYCL host allocation を行います。この helper は `g_coherent` を参照しません。通常の非-HIP SYCL build ではこの名前を読みません。HIP macro を伴う SYCL build でも、確認できる SYCL `mapped()` の allocation 分岐にはこの値による切り替えがありません (`sycl/src/core/verify.cpp:91-100,220-243`)。

## 実行時の詳細

HIP で値が ON のとき、`mapped(bytes, h, d)` は `hipHostMallocMapped | hipHostMallocCoherent`（`peer_portable()` が true なら `hipHostMallocPortable` も追加）を指定します。確保後に host buffer をゼロ初期化し、`cudaHostGetDevicePointer()` で device pointer を取得します。OFF の場合は既定の `host_alloc_guarded()` に mapped flag（必要なら portable flag）を渡す経路です (`src/core/verify.cpp:495-508`)。

明示 coherent allocation または device pointer 取得に失敗した場合、`mapped()` は false を返し、coherent 指定から既定 allocator への再試行はありません。通常の staging allocation 失敗は `verify: mapped staging allocation failed ...`、plan allocation 失敗は `verify: mapped plan allocation failed ...` として verifier 初期化を失敗させます (`src/core/verify.cpp:851-869,918-927`)。trace buffer の allocation は別扱いで、失敗すると trace buffer を無効化します (`src/core/verify.cpp:1005-1011`)。

`STRATA_VERIFY_TRACE` が有効で trace buffer の初期化箇所を通ると、HIP build は stderr に `strata verify trace (#649): on; coherent words explicit` または `... default` と出します。このログの `explicit/default` は `g_coherent` の判定表示です。同じ行に `HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の値も表示しますが、このコードではそれらをこの変数の判定や優先順位には使いません (`src/core/verify.cpp:1005-1019`)。`STRATA_VERIFY_TRACE` が無効なら、この coherent 状態を知らせる専用ログは確認できません。

## 根拠

- 判定 helper、HIP 限定の値保持: `src/core/verify.cpp:296-306`。
- coherent / default の allocator 分岐: `src/core/verify.cpp:495-508`。
- verifier staging・plan allocation と失敗文言: `src/core/verify.cpp:851-869,918-927`。
- trace の任意 buffer と HIP 状態ログ: `src/core/verify.cpp:1005-1019`。
- SYCL 側の参照・allocation 経路: `sycl/src/core/verify.cpp:91-100,220-243`。
- `docs/DETAILS.md` と関連設計資料には、この変数の値判定や効果を説明する記述を確認できませんでした。上記は調査対象 commit の実装に基づきます。
