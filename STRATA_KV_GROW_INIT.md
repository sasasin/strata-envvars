# `STRATA_KV_GROW_INIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

`--kv-grow` の elastic K/V を有効にしたとき、各 QSA state の K/V pool で起動時に物理メモリを割り当てる初期セル数を指定します。初期値を超える K/V は、コンテキストが伸びたときに expert cache からチャンクを受け取って拡張されます。変数は elastic K/V 自体を有効にしません。既定の初期セル数は `16384` です。

## 値と判定

CUDA と SYCL の `generate` は、環境変数を `std::atoll` で読み、変換後の値が正の場合だけ採用します。それ以外は `16384` を渡します。文字列全体の妥当性や数値の後続文字は検査しません。

| 環境変数の値 | 渡される初期セル数 |
|---|---:|
| 未設定 | 16384 |
| 空文字 | 16384（`atoll` の結果が 0） |
| `4096` | 4096 |
| `+4096`、先頭空白の後の `4096` | 4096（符号・先頭空白を `atoll` が処理） |
| `4096tail` | 4096（数値の後ろは変換対象外） |
| `0`、`-1`、`words` | 16384（結果が正でない） |

数値の全体 parse、上限チェック、エラー通知はありません。変換可能な正数でも、各 pool の実際の初期割り当てはその state の QSA ページ数を超えません。`pool_slots` がセル数をページ単位に切り上げ、state のスロット数で上限を設けます。したがって指定セル数と実際に確保されるセル数は、ページ境界やモデルの context 上限によって異なります。

## 有効になる条件

この値が初期確保に使われるのは、`STRATA_KV_GROW` または `--kv-grow` によって elastic K/V が要求され、さらに次の条件を満たして `on` になったときです。

- 単一 GPU。
- resident K/V ではなく、全 K/V を VRAM に置く設定。
- expert profile があり、全 expert を RAM に置くモードで、expert cache が有効。
- remote expert cache を使わない。
- VMM が利用できる。
- `--batch`、`--vram-elastic`、`--peer-device` を使わない。

条件を満たさず `on` が false の場合も `STRATA_KV_GROW_INIT` は読み取られて setter に渡されますが、`qsa_state_init` は elastic pool を作らないため、初期セル数には効果がありません。`STRATA_KV_GROW` が空文字なら `--kv-grow` の CLI 状態が使われ、空でない値なら先頭文字が `0` かどうかで要求状態を判定します（例: `false` は要求扱い）。この enable 判定は初期セル数の parse とは別です。

## 実行時の詳細

環境変数は `generate` の session 構築前に一度読み取られます。CUDA と SYCL の双方で `qsa_set_kv_elastic(on, init_cells)` を呼び、setter は elastic K/V の有効状態と正の `init_cells` をプロセス内の共有状態に保存します。後から環境変数を変更しても、すでに保存された初期値は再評価されません。

elastic K/V が有効な QSA state では、初期セル数に必要なページ分の K/V pool を VMM range に map します。各 QSA state の配列はその state 専用 range に置かれ、map に失敗した場合は `strata: the elastic K/V could not reserve or map its pools` を stderr に出し、session state の初期化を失敗させます。以後の拡張では現在のセル数や必要量に応じて pool を map します。初期値そのものを表示する専用ログはありません。起動後に現在の elastic K/V セル数を出すログは `elastic K/V: ... cells in VRAM` です。

`docs/DETAILS.md` は `--kv-grow` の用途と有効条件を説明していますが、`STRATA_KV_GROW_INIT` の値や既定値は記載していません。ここでの既定値と変換規則は実装から確認したものです。

## 根拠

- `src/program/generate.cpp:4221-4238` — CUDA 側の enable 条件、`STRATA_KV_GROW_INIT` の `atoll` 判定、QSA setter 呼び出し。
- `sycl/src/program/generate.cpp:3768-3785` — SYCL 側の同じ判定と setter 呼び出し。
- `src/core/layer.cpp:520-528,576-579,689-730` — 初期値の初期化、setter の保存、elastic pool の初期確保。
- `sycl/src/core/layer.cpp:581-589,659-662,779-821` — SYCL 側の同じ状態と初期確保。
- `src/core/layer.cpp:530-536,550-572` — セル数をページ単位に丸め、state のスロット数で上限を設けて map する処理。
- `include/strata/core/layer.hpp:285-289` — 初期セルと拡張の API 説明。
- `docs/DETAILS.md:260-264` — `--kv-grow` の用途と有効条件。初期セル数の環境変数に関する記載はありません。
