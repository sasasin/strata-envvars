# `STRATA_KV_RING_OFF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter の K/V を、通常のウィンドウ分だけ保持する ring 方式でなく全 context 分 VRAM に保持する A/B 用スイッチ。CUDA/HIP 共用実装と SYCL 実装の `kv_plan()` が設定有無を判定し、ring state の `mode` と slots 数を決める。main layers の K/V 計画は `STRATA_KV_MAIN_OFF` 側で判定され、この変数では切り替わらない（`engine/src/core/layer.cpp:738-755`、`engine/sycl/src/core/layer.cpp:722-739`）。

## 値と判定

値の文字列や数値は parse せず、`std::getenv(...) != nullptr` だけを見る。したがって未設定は無効、空文字を含む設定済みの値はすべて有効で、`0`、`false`、空白だけの値も ring を無効化する。大文字小文字、数値としての妥当性、文字列末尾は検査しない。判定結果は関数内 `static const bool` に保存される（`engine/src/core/layer.cpp:738-747`、`engine/sycl/src/core/layer.cpp:722-731`）。

| `kv_plan()` に入った状態 | unset | 設定済み（例: `1`, `0`, `false`, 空文字） |
|---|---|---|
| `g_kv_resident <= 0` または `ring_cells < 0` | 先に返るため判定しない | 先に返るため判定しない |
| `g_kv_resident > 0`, `ring_cells > 0`（drafter ring） | 通常の ring 計画。ページ数を丸め、必要なら `mode=2` と ring slots を使う | drafter ring を無効化し、全ページ分の slots を使う `mode=0` のまま返る |
| `g_kv_resident > 0`, `ring_cells == 0`（main state 等） | main 用の判定へ進む | この変数は分岐に使われず、main 用の判定へ進む |

通常の ring 計画でも、丸めた ring slots が全ページ数以上なら `mode=2` にはならず、この変数による実質的な差はない（`engine/src/core/layer.cpp:748-754`、`engine/sycl/src/core/layer.cpp:732-738`）。

## 有効になる条件

- K/V resident 数 `g_kv_resident` が正であること。`--kv-resident N` は parser で読み、値を `qsa_set_kv_resident()` に渡す。負数は `strata generate: --kv-resident must be >= 0` を stderr に出して終了コード 2 で拒否される。0 はこの分岐を有効にしないが、CUDA/HIP の層分割 spill walk が window を下げる経路や、SYCL の自動選択で正の resident 数が設定される場合は有効条件を満たし得る（`engine/src/program/generate.cpp:3906-3908,5028-5032,7466-7484`、SYCL: `engine/sycl/src/program/generate.cpp:1946,2542-2546,4249-4277`）。
- MTP drafter の K/V state が `ring_cells > 0` で作られること。MTP は `window > 0 && window < max_cells` の場合に限り `ring = window + 4 * max_t + 64` を渡し、それ以外は `ring=0` を渡す。よって drafter/window がない場合、window が 0 以下または context 以上の場合にはこのスイッチは drafter state を変えない（`engine/src/core/mtp.cpp:511-526`、SYCL: `engine/sycl/src/core/mtp.cpp:442-460`）。
- `STRATA_KV_MAIN_OFF` は別の静的判定であり、`ring_cells == 0` の main state にはそちらが使われる。この変数は main state の K/V residency を変更しない（`engine/src/core/layer.cpp:744-753`、`engine/sycl/src/core/layer.cpp:728-737`）。
- ソース内の直接読み取りは CUDA/HIP 共用 `engine/src/core/layer.cpp` と SYCL `engine/sycl/src/core/layer.cpp`。Metal の MTP `bind()` は早期 return する実装だが、同じ backend でこの `layer.cpp` が別経路から使われるかはこの読み取り箇所だけでは断定しない（`engine/src/core/mtp.cpp:908-913`）。

## 実行時の詳細

`kv_plan()` は最初に全 context 分のページ数を slots に設定する。streaming が有効で ring が正、かつ本変数が未設定なら、`ring_cells` をページ単位に切り上げ、ring が全ページ未満の場合に `mode=2`、ring slots、`pooled_rows=2` を設定する。本変数が設定済みならその ring 分岐を飛ばし、全ページ slots と `mode=0` を保つ。これにより MTP drafter の K/V を全 context 分の VRAM state として計画する（`engine/src/core/layer.cpp:738-755,788-804`、SYCL: `engine/sycl/src/core/layer.cpp:722-739,758-774`）。MTP の ring は drafter が読む末尾 window と一回の処理で先行して書く分から作られる（`engine/src/core/mtp.cpp:514-519`、SYCL: `engine/sycl/src/core/mtp.cpp:445-450`）。

読み取りは `kv_plan()` 内の関数ローカル static で、最初に `g_kv_resident > 0` かつ `ring_cells >= 0` の呼び出しで評価・cache される。その後の環境変更は同じプロセスでは反映されない。通常は QSA state のサイズを計算する `session_bytes()` が `qsa_state_bytes()` を呼ぶ時点で先に評価され、MTP state のサイズ計算・初期化にも同じ cache が使われる（`engine/src/core/session.cpp:62-65,103-114`、`engine/sycl/src/core/session.cpp:69-72,110-121`）。値に対する CLI 上書きや別環境変数との優先順位はなく、すでに決まった `g_kv_resident` と `ring_cells` が有効条件を決める。

リングを使う通常経路では pinned RAM に drafter K/V copy を置く。初期化に失敗して ring state が非ゼロ mode の場合、MTP は `strata mtp: no pinned RAM left for the draft layer's K/V copy; keeping it in VRAM` を stderr に出し、ring を `-1` にして fully resident で再試行する。本変数が有効な経路は最初から `mode=0` のため、この pinned-copy fallback には入らない。MTP K/V state の device allocation 自体に失敗した場合は `mtp: the K/V state does not fit`、mode 0 の state 初期化が 0 を返した場合は `mtp: state init failed` がエラーになる（`engine/src/core/mtp.cpp:524-535`、SYCL: `engine/sycl/src/core/mtp.cpp:455-475`）。

## ログと測定値

この変数専用の有効・無効ログはない。上記の pinned RAM fallback と MTP state allocation / initialization error は、該当する場合に出る実装上の文言であり、環境変数が設定されたこと自体を示すログではない（`engine/src/core/mtp.cpp:525-535`、`engine/sycl/src/core/mtp.cpp:456-475`）。`docs/DETAILS.md` にこの変数の挙動や条件付き測定値の記載は見つからなかった。

## 根拠

- `engine/src/core/layer.cpp:738-755,788-804` — CUDA/HIP 共用の設定有無判定、K/V plan、state サイズ。
- `engine/sycl/src/core/layer.cpp:722-739,758-774` — SYCL の同等処理。
- `engine/src/core/mtp.cpp:511-535`、`engine/sycl/src/core/mtp.cpp:442-475` — drafter ring の条件、初期化、fallback と失敗経路。
- `engine/src/core/session.cpp:62-65,103-114`、`engine/sycl/src/core/session.cpp:69-72,110-121` — main session state のサイズ計算と初期化。
- `engine/src/program/generate.cpp:3906-3908,5028-5032,7466-7484`、`engine/sycl/src/program/generate.cpp:1946,2542-2546,4249-4277` — `--kv-resident` の読み取り・設定・負数拒否と自動/調整経路。
