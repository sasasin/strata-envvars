# `FNX_PF_ROWS`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

sFNX の Flash-Next split engine が prompt prefill を処理するときの最大行数（token rows）を、1 chunk あたりで指定します。指定値は engine 構築時に読み取られ、prompt の分割幅 `pf_c_`、関連する prefill buffer のサイズ、QSA の raw-key ring サイズに使われます。環境変数名を読む本番コードは `src/split/src/engine.cu` の engine constructor に 1 箇所あります。通常の Strata engine 全般の設定ではなく、`strata-split-*` / `sfnx` の Flash-Next split 経路の設定です（`src/split/CMakeLists.txt:1-7,108-136`）。

## 値と判定

`env_int()` は符号付き 10 進整数を文字列全体から `strtoll` で読みます。先頭の `+` / `-` は許可されますが、空文字、空白、末尾の文字、数字でない値、`long long` の範囲外は parse error です。parse を通った値は `16..8192` の範囲かつ 16 の倍数でなければなりません（`MAXT = 16`）。

| build | 未設定時 | 設定時の受理値 | 無効値 |
|---|---:|---|---|
| CUDA (`FNX_HIP=0`) | `FNX_PF_PASS` も未設定なら VRAM に応じて 4096 または 8192。`FNX_PF_PASS` が設定されていれば 8192 | 16 の倍数で 16..8192（例 `16`, `4096`, `8192`, `+32`） | 空文字・非整数・範囲外・16 の倍数でない値 |
| HIP (`FNX_HIP=1`) | 4096 | 16 の倍数で 16..8192 | 空文字・非整数・範囲外・16 の倍数でない値 |

CUDA の自動選択では `FNX_PF_ROWS` と `FNX_PF_PASS` の両方が未設定の場合に、全カード中の最小空き VRAM と K/V pool を使って 8192×4、8192×2、4096×4、4096×2 の順で収まる構成を選びます。どの構成も収まらないときは 4096×2 が選ばれます。どちらかの変数が設定されているとこの自動選択を飛ばし、行数の既定値は CUDA では 8192 です。HIP build ではこの CUDA 用 VRAM 自動選択ブロック自体がコンパイルされず、未設定時は 4096 です（`src/split/src/engine.cu:78-115`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で作る sFNX Flash-Next engine が対象です。split engine は opt-in の別 executable で、CMake は Linux CUDA または Linux HIP の経路を構成します（`src/split/CMakeLists.txt:1-7,108-136`）。
- engine が `prefill()` を実行する場合に chunk 幅として使われます。`FNX_PREFILL=0` の経路など、prompt を通常の window/decode 処理で読んで `prefill()` を呼ばない場合、chunk 分割への効果はありません。ただし環境値の読み取りと値検証は `Engine` 構築時に行われるため、その経路でも無効値なら構築に失敗します（`src/split/tools/fnx_run.cpp:1003-1019`; `src/split/src/engine.cu:111-114`）。
- `FNX_PF_PASS` は別設定です。CUDA のみ、両変数が未設定のときに限り `FNX_PF_ROWS` の自動選択と pass 数選択を一緒に行います。`FNX_PF_PASS` が明示されていて `FNX_PF_ROWS` が unset なら、行数の既定値は CUDA 8192 / HIP 4096 です。`FNX_PF_PASS` は行数の値を上書きしません（`src/split/src/engine.cu:82-114`; `src/split/src/prefill.cu:1063-1071`）。
- CLI 引数から `FNX_PF_ROWS` を上書きする処理は確認できません。`sfnx` は model load 後、server を作る前に `Engine` を構築し（`src/split/tools/sfnx.cpp:1113-1135`）、`fnx_run` も `fnx_run_cmd` 内で `Engine` を構築します（`src/split/tools/fnx_run.cpp:978-988`）。

## 実行時の詳細

`env_int("FNX_PF_ROWS", rows)` は `Engine` constructor ごとに 1 回実行され、`pf_c_` に格納されます。process 起動後に環境値を変えても既存 engine の値は変わりません。新しい `Engine` を作る場合は、その constructor 時点の環境が再度読み取られます。環境値の子 process への転送や上書きはこの設定について見つかりません。

受理された行数は `pf_jobs_` の算出に使われ、`set_prompt_rows()` が QSA ring を `max(2048, 2 * rows)` に設定します。prefill 中は `tokens` を `pf_c_` 行以下の chunks に分割し、各 chunk を順に埋め込み、最大 pass 数 `K` 分ずつ `prefill_pass()` へ渡します。buffer の確保サイズも `pf_c_` に比例します。したがって値は chunk の大きさと関連 buffer のメモリ量を変えます。ユーザー向け CLI の上書きや追加の clamp はありません（`src/split/src/engine.cu:111-117`; `src/split/src/kernels.cu:1306-1311`; `src/split/src/prefill.cu:854-875,1300-1318,1338-1370`）。

無効な整数表記は `env_int()` が `FNX_PF_ROWS: '<値>' is not a whole number` を送出します。整数として parse できても範囲や倍数条件に外れる場合は `FNX_PF_ROWS: a multiple of 16 from 16 to 8192, got <値>` です。`sfnx` の Engine 構築時に発生した例外は `fail()` が protocol の `ERR <例外>` 行と stderr の `sfnx: failed: <例外>` を出し、終了コード 1 で process を終了します（`src/split/src/env.hpp:15-21,33-40`; `src/split/src/engine.cu:111-114`; `src/split/tools/sfnx.cpp:1120-1131,1090-1098`）。CUDA の VRAM 自動選択が標準構成 8192×4 以外を選ぶ場合は、stderr に `fnx: prompt path: ...` が出ます（`src/split/src/engine.cu:97-108`）。

## 根拠

- 値の parse 規則: `src/split/src/env.hpp:15-21,33-40`。
- 対象 executable と backend build 条件: `src/split/CMakeLists.txt:1-7,108-136`。
- 既定値、自動選択、検証、設定反映: `src/split/src/engine.cu:78-117`。
- 1 chunk ずつの prefill 処理と buffer 使用: `src/split/src/prefill.cu:854-875,1300-1318,1338-1370`。
- QSA ring の行数: `src/split/src/kernels.cu:1306-1311`。
- engine 構築とエラー表示: `src/split/tools/sfnx.cpp:1113-1135`; `src/split/tools/fnx_run.cpp:978-988`。
