# `STRATA_KV_STAGE_OWN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

KV streaming 中に prompt 用 staging pool を借用済みの expert 領域から切り離し、専用の device allocation に置く A/B 用スイッチです。CUDA/HIP 共通実装と SYCL 実装の `take_stage()` が、K/V staging buffer を `Alloc` に割り当てます。通常は prompt の借用領域から同じ pool を切り出しますが、この変数が設定されていると専用 allocator を使います（`engine/src/prefill/prefill.cpp:1748-1779`、`engine/sycl/src/prefill/prefill.cpp:906-937`）。

この変数は KV の形式、ページ数、転送内容、attention の選択を変更しません。変えるのは staging pool の割当先です。借用領域がある経路では expert 用の借用領域を消費せず、pool を別に確保します。ソースコメントは A/B 比較用とし、借用 expert slot の数を resident 実行と揃える意図を記しています（`engine/src/prefill/prefill.cpp:1749-1753`）。借用領域がない経路では通常の allocator も個別に device allocation を行うため、割当先の違いは主にサイズ計算に現れます（`engine/src/prefill/prefill.cpp:1095-1115, 3718-3783`）。

リポジトリ全体の名前検索では、実際の環境読み取りは CUDA/HIP と SYCL の `stage_own()` 各 1 箇所です。ほかはその呼び出しと `terminal/data/settings-register.json` の設定登録データで、動的な env helper 経由の読み取りはありません。

## 値と判定

両実装とも `std::getenv("STRATA_KV_STAGE_OWN") != nullptr` の結果を関数内 `static const bool` に保存します。値の変換や内容の検査はありません。未設定だけが無効で、空文字を含め、設定された値は何であっても有効です（`engine/src/prefill/prefill.cpp:1753`、`engine/sycl/src/prefill/prefill.cpp:911`）。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP prefill、SYCL prefill | 無効 | `1`、`true`、`0anything`、空文字を含む、環境変数が存在するすべての値 | なし。`0`、`false`、空白だけの値も有効 |

## 有効になる条件

- 選択中の QSA state の `kv_mode` が `1`（KV streaming）であることが必要です。それ以外の mode では `take_stage()` が環境変数を評価せず、staging pool も割り当てません（`engine/src/prefill/prefill.cpp:1754-1758`、`engine/sycl/src/prefill/prefill.cpp:912-916`）。
- 通常の main KV streaming は `--kv-resident` に正の値が設定され、resident page 数が全 page 数より少ない場合に選ばれます。`STRATA_KV_MAIN_OFF` が設定されていると main KV は resident のままとなり、この変数による分離は起きません（`engine/src/core/layer.cpp:738-755`）。`--kv-resident` が負の場合は CLI 検証で拒否されます（`engine/src/program/generate.cpp:3907`, `5028-5032`）。
- この変数自体に対応する CLI 引数や別設定からの上書きはありません。`--kv-resident` は KV mode を決める別設定であり、`STRATA_KV_STAGE_OWN` の値判定を変更しません。
- 実装箇所は CUDA/HIP の prefill と SYCL prefill です。Metal 経路では CUDA/HIP 側の `Prefill::init` が Metal 用の処理から先に戻るため、ここにある `take_stage()` の割当は行われません（`engine/src/prefill/prefill.cpp:2443-2454`）。

## 実行時の詳細

`stage_own()` の最初の呼び出しで環境変数の有無を読み、その結果をプロセス内でキャッシュします。呼び出し元は KV mode 1 のときだけこの関数を呼ぶため、最初の評価は `bytes_needed` によるサイズ計算時か、実際の prefill 初期化・再配置時になり得ます。一度キャッシュされた後に環境を変更しても反映されません（`engine/src/prefill/prefill.cpp:1753-1758, 3782-3783`、`engine/sycl/src/prefill/prefill.cpp:911-916, 2492-2494`）。

有効時、`take_stage()` は count-only の `Alloc` から staging pool のサイズを加算せずに戻ります。実割当では既存 allocator の `owned` リストを共有する別の `Alloc` を作り、K/V pool をそこに確保します。CUDA/HIP では `cudaMalloc`、SYCL では `strata::malloc_device_guarded` を通り、借用領域の bump allocation を消費しません（`engine/src/prefill/prefill.cpp:1083-1115, 1754-1778, 3718-3783`、`engine/sycl/src/prefill/prefill.cpp:426-453, 912-937, 2423-2494`）。したがって `bytes_needed` の借用領域サイズにはこの専用 pool の分が含まれず、実行時には別途 device memory が必要です。

専用 pool に割り当てる buffer の種類は state の KV 形式に従います。hybrid 形式では int8 K、scale、Q4 V、Q4 形式では K/V の Q4 pool、int8 形式では K/V と scale、それ以外では FP16 の K/V pool を取ります（`engine/src/prefill/prefill.cpp:1762-1778`、`engine/sycl/src/prefill/prefill.cpp:920-936`）。

## ログと測定値

この変数の有効化を示す専用ログはありません。専用 allocation が失敗すると `take_stage()` は初期化失敗を伝え、CUDA/HIP と SYCL の `Prefill::init` は `err` に `prefill: device buffers for a chunk of ... tokens do not fit (...)` を設定して `false` を返します（`engine/src/prefill/prefill.cpp:1107-1115, 2742-2746`、`engine/sycl/src/prefill/prefill.cpp:446-453, 1613-1632`）。この文言は呼び出し元へ返すエラー文字列です。専用 allocator が保持する `failed_bytes` は外側の `Alloc` にコピーされないため、文中の `failing buffer wanted` は専用 staging pool の失敗サイズを示さない場合があります（`engine/src/prefill/prefill.cpp:1759-1761, 2742-2745`、`engine/sycl/src/prefill/prefill.cpp:917-919, 1627-1630`）。`STRATA_KV_STAGE_OWN` 固有の警告・fallback・性能測定値は確認できません。

## 根拠

- `engine/src/prefill/prefill.cpp:1748-1779` — CUDA/HIP 側の値読み取り、KV mode 条件、専用 pool の割当。
- `engine/sycl/src/prefill/prefill.cpp:906-937` — SYCL 側の同じ処理。
- `engine/src/prefill/prefill.cpp:1083-1115`、`engine/sycl/src/prefill/prefill.cpp:424-460` — 借用領域・count-only・実割当の allocator 動作。
- `engine/src/prefill/prefill.cpp:3718-3783`、`engine/sycl/src/prefill/prefill.cpp:2423-2494` — サイズ見積もりが `take_stage()` を通る経路。
- `engine/src/core/layer.cpp:738-755`、`engine/src/program/generate.cpp:3907, 5028-5032` — main KV streaming の選択条件と `--kv-resident` の検証。
- `engine/src/prefill/prefill.cpp:2742-2746`、`engine/sycl/src/prefill/prefill.cpp:1627-1632` — device buffer 割当失敗時のエラー文字列。
