# `FNX_KV8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Flash-Next split engine の paged K/V cache を int8 または f16 で保持するかを選ぶ。既定は int8、`FNX_KV8=0` で f16。int8 の場合、K/V の各行を 32 要素ごとに量子化し、グループごとの scale を f16 で保持する。QSA の pooled keys はどちらの設定でも f16 のまま（`engine/src/split/src/kernels.hpp:142-160`）。

この変数は `fnx::Engine` の K/V pool のページ寸法・割り当てと、K/V 書き込み・attention 読み出し形式を決める。通常の `strata` エンジン全体の K/V 設定ではなく、ビルド時に opt-in する `strata-split-N` と、同じ `fnx::Engine` を生成する `fnx_run` の実行経路に限られる。split は既定でビルドされず、Linux の CUDA または HIP の構成で `STRATA_BUILD_SPLIT=ON` が必要（`engine/CMakeLists.txt:922-927`, `engine/src/split/CMakeLists.txt:1-7,20-27`）。

## 値と判定

`fnx::kv_q8()` が `std::getenv` で取得した文字列全体を `strcmp` で比較する。数値変換はせず、空白除去、大文字小文字変換、前方一致も行わない（`engine/src/split/src/kernels.cu:1890-1897`）。

| 条件 | unset | 有効になる値 | 無効な値 |
|---|---|---|---|
| split engine の `fnx::Engine` | int8（q8） | `1` は int8、`0` は f16 | 空文字、`true` / `false`、`01`、`0anything`、前後に空白のある値など。`FNX_KV8: 0 or 1, not '<値>'` を含む例外になる |

`1` と `0` 以外の設定値は、値が真偽値らしく見えるかにかかわらず拒否される。負値や数値境界の扱いは該当しない（数値として parse しない）。CLI 引数による上書き箇所はなく、この変数の判定に関係する別の環境変数も見つからない。

## 有効になる条件

- split engine がビルドされ、実行経路で `fnx::Engine` が構築されること。`-DSTRATA_BUILD_SPLIT=ON` がない通常の構成では、この split engine はビルド対象外（`engine/CMakeLists.txt:922-927`）。
- `FNX_KV8` が未設定か `1` なら int8 cache、`0` なら f16 cache。モデルの attention 層の K/V append と attention 読み出しが、この選択された形式を使う（`engine/src/split/src/engine.cu:412-424,925-926`; `engine/src/split/src/kernels.cu:1687-1711,1738-1746`; `engine/src/split/src/attn_prompt.cuh:64-75`）。

## 実行時の詳細

`fnx::kv_q8()` は関数内 `static const bool` を初回呼び出し時に初期化し、その値を以後の呼び出しで再利用する。通常の初回呼び出しは `Engine::Engine` 内、ページ数を決める箇所（`engine/src/split/src/engine.cu:68-78`）。従ってこのプロセスでは最初の Engine 構築時に環境値が確定し、構築後に環境を変更しても反映されない。未設定時は int8 となる。

int8 のとき Engine は、f16 pool と同じ K/V pool の byte 量に収まるページ数になるよう、各カードの f16/int8 ページ寸法比の最小値で context ページ数を縮める。lane 分の追加ページを加えて割り当てを行い、実際に確保する K/V pool と lane 0 のページ表にも選択形式を使う（`engine/src/split/src/engine.cu:68-78,393-424`）。このため int8 は K/V cache の表現と pool 内で確保する位置数に影響する。

K/V append kernel は int8 設定で各 32 要素グループの最大絶対値から scale（`max(abs(x))/127`）を作り、値を丸めて int8 に格納する。f16 設定では K/V を f16 に変換して格納する。attention の prompt 読み出し側は `g.q8` に応じて int8 値と scale または f16 値を読み出す（`engine/src/split/src/kernels.cu:1687-1711,1738-1746`; `engine/src/split/src/attn_prompt.cuh:64-75`）。

有効値による既定選択を CLI 引数が上書きする経路はない。無効値は `kv_q8()` 初回呼び出し時に例外となり、K/V pool の初期化に進まない。

## ログと測定値

正常ロード後、`sfnx` は stderr に `sfnx: loaded ... K/V pool (<形式>) ...` を出し、形式部分は `int8` または `f16`（`engine/src/split/tools/sfnx.cpp:1137-1150`）。無効値の場合、ロード中の例外は stderr に `sfnx: failed: FNX_KV8: 0 or 1, not '<値>'` と出て、プロトコル stdout に `ERR FNX_KV8: 0 or 1, not '<値>'` を出し、終了コード 1 で終わる（`engine/src/split/tools/sfnx.cpp:1094-1103,1123-1135`）。`fnx_run` では stderr に `fnx_run: FNX_KV8: 0 or 1, not '<値>'` を出して終了コード 1（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。

対象の Strata 資料には、この環境変数の形式ごとの性能・品質測定値は見つからなかったため記載しない。

## 根拠

- `engine/src/split/src/kernels.cu:1890-1897` — 値の読み取り、許可文字列、既定値、static cache。
- `engine/src/split/src/kernels.hpp:142-175` — ページレイアウトと K/V / pooled key の形式。
- `engine/src/split/src/engine.cu:68-78,393-424` — context page の調整と pool 初期化。
- `engine/src/split/src/kernels.cu:1687-1711,1738-1746` — K/V cache への書き込み。
- `engine/src/split/src/attn_prompt.cuh:64-75` — prompt attention の K/V 読み出し。
- `engine/src/split/src/engine.cu:906-928` — attention 経路から append と attention への呼び出し。
- `engine/CMakeLists.txt:922-927`; `engine/src/split/CMakeLists.txt:1-7,20-27,93-101,116-126` — split build と対応環境。
- `engine/src/split/tools/sfnx.cpp:1094-1103,1123-1150`; `engine/src/split/tools/fnx_run.cpp:1364-1373` — 起動時の表示とエラー処理。
