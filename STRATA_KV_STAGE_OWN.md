# `STRATA_KV_STAGE_OWN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

KV streaming を使う prefill の GPU staging pool を、expert cache から借りた領域に置かず、独立した device allocation にします。コメント上の用途は A/B 比較です。borrowed buffer を使うとき、streaming 側の prompt path が resident 側と同じ数の expert cache slot を借りるようにし、CPU で処理する expert の配置差が KV 配置の比較に混ざるのを避けます。prompt path が自前 allocation を使う場合、pool は既定でも個別 allocation されるため、主な実行時の差は borrowed buffer から外す点です。

対象実装は CUDA と SYCL の prefill です。どちらも同じ環境変数判定と配置方針を持ちます（CUDA: `src/prefill/prefill.cpp`、SYCL: `sycl/src/prefill/prefill.cpp`）。

## 値と判定

| 環境変数 | 動作 |
|---|---|
| 未設定 | staging pool を通常の `Alloc` に割り当てる。borrowed region がある場合はその領域から取り、自前 allocation の場合は他の buffer と同様に個別 allocation する |
| 設定あり | 値を調べず有効。空文字、`0`、`false` を含め、存在すれば borrowed region から pool を外して独立 allocation する。自前 allocation の場合は実行時の割り当て方は既定と同じ |

数値変換や文字列比較はありません。`stage_own()` の関数内 `static const bool` に最初の判定結果が保存されるため、同一プロセスでは最初の呼び出し以降に環境を書き換えても反映されません。最初の呼び出しは実際の prefill 初期化とは限らず、`bytes_needed()` / `bytes_needed_owned()` による領域サイズ計算から起きる場合もあります。

根拠: `src/prefill/prefill.cpp:865-878,1819-1837`、`sycl/src/prefill/prefill.cpp:741-754`。

## 有効になる条件

- QSA の primary session state が `kv_mode == 1`（KV streaming）の場合だけ staging pool を作ります。その他の K/V mode では `take_stage()` が直ちに戻るため、この変数による配置差はありません。
- `STRATA_KV_STAGE_OWN` が設定され、`take_stage()` が実 allocation を行うとき、staging pool 用の `Alloc` は borrowed region の `base` を持たず、元と同じ owned pointer list を使います。そのため各 pool buffer は独立して確保・追跡されます。
- 設定はコード上で CUDA / SYCL のどちらにも適用されます。変数名とコメントは A/B 用途を示しますが、実装に特定の A/B 起動モードや CLI 条件の検査はありません。

根拠: `src/prefill/prefill.cpp:871-895,1298-1304`、`sycl/src/prefill/prefill.cpp:747-772,1243-1247`。

## 実行時の詳細

pool の要素数は `n_pages * n_head_kv * page_size` 行で、primary QSA state の保存形式に応じた K/V buffer を確保します。通常形式は FP16 K/V、INT8 は K/V と scale、Q4 は K/V、hybrid は INT8 K と scale および Q4 V です。設定ありの場合も同じ `KvHostPools` のフィールドに同じ形式・サイズの buffer を割り当てます。CUDA では `cudaMalloc` した各 pointer が `m.owned` に登録され、`Prefill::release()` で解放されます。

prefill の各 streaming QSA layer では、この pool に host 側の KV prefix を読み込み、chunk の新しい K/V を staging pool と host copy（および resident block）へ書きます。変数が選ぶのは pool の割り当て先であり、prefix の読み込みや append の呼び出し方は同じです。特別なログ出力はありません。独立 allocation に失敗した場合は `carve()` が失敗し、呼び出し側が通常の `prefill: device buffers ... do not fit` エラーを返します。

領域計算では `stage_own()` が有効かつ `Alloc::count_only` のとき `take_stage()` は pool を数えずに戻ります。したがって borrowed buffer 要求から staging pool 分が除外されます。また同じ処理は `bytes_needed_owned()` にも使われ、独立 allocation の pool 容量はその返却値にも含まれません。`STRATA_OWNED_PRICE=exact` と併用した場合、その値を使う cache 見積りはこの追加 pool 分を見積りません。

根拠: `src/prefill/prefill.cpp:369-395,867-895,915-942,1823-1884,2647-2662,2674-2695,4788-4799`。KV streaming の利用者向け説明は `docs/DETAILS.md:79-84` にありますが、同資料は `STRATA_KV_STAGE_OWN` を説明していません。

## 根拠

- `src/prefill/prefill.cpp:867-895`: 環境変数の判定、count-only 時の扱い、pool の形式別 allocation。
- `src/prefill/prefill.cpp:1282-1304,1819-1884`: `carve()` と `bytes_needed` 系からの呼び出し。
- `src/prefill/prefill.cpp:2244-2268,2647-2695`: streaming prefill での staging pool の読み込みと書き込み。
- `src/prefill/prefill.cpp:915-942`: owned allocations の解放。
- `sycl/src/prefill/prefill.cpp:742-772,1224-1247,1862-1917`: SYCL 側の対応実装。
- `docs/DETAILS.md:79-84`: KV streaming の概要。`STRATA_KV_STAGE_OWN` 固有の説明や測定値は記載されていません。
