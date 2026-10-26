# `DS4_CACHE_THREADS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSV4.1 CUDA エンジンの expert cache が、GPU 上の expert と CPU 側 expert を入れ替える swap 処理に使う worker thread 数を指定します。各 worker は自身の pinned host staging buffer と、デバイスごとの非同期 CUDA copy stream を持ち、swap queue から仕事を取り出して expert の重みを転送・再配置します。設定は expert cache 自体を有効化せず、cache が有効な場合の swap worker 数だけを調整します。

## 値と判定

load 時に `getenv()` で値の有無を確認し、設定されていれば `atoi()` で整数へ変換します。thread 数は次の式で決まり、1 未満にはなりません。

`max(1, min(c_inflight, atoi(DS4_CACHE_THREADS)))`

| 値 | 実際に要求される worker 数 |
|---|---|
| unset | 1 |
| 空文字、非数値文字列、`0`、負数 | 1（`atoi` が 0 以下を返し、下限 1 が適用される） |
| 正の整数 | `DS4_CACHE_INFLIGHT` 由来の `c_inflight` 以下に制限した値 |
| 数字の後ろに文字がある値 | `atoi` が先頭の整数部分を変換する。例: `3x` は 3 |

`c_inflight` は別環境変数 `DS4_CACHE_INFLIGHT` から `atof()` で読み、既定値 8 を整数化して下限 1 を適用した値です。したがって `DS4_CACHE_THREADS` の上限は固定値 8 ではなく、`c_inflight` の値です。`atoi` / `atof` は文字列全体の厳密な検証を行わず、大文字小文字比較もありません。

## 有効になる条件

モデルの load 処理で `o.expert_cache` が true のときだけ `DS4_CACHE_THREADS` を読み取り、worker、swap buffer、stream を作成します。expert cache が無効なら、この変数は読み取られず worker も作成されません。実装箇所は DSV4.1 CUDA エンジンの `src/dsv41/ds4_model.cu` です。

`DS4_CACHE_INFLIGHT` は worker 数とは別に、同時進行中として許される swap の上限にも使われます。worker 数が上限より小さい場合は queue 処理スレッド数が制約になります。worker 数を増やすと同時の処理能力が増え得ますが、各 worker ごとに複数の pinned host buffer と各 CUDA device 用 stream を割り当てます。ソースコメントは V100 で 4 threads は 1 thread より速くなかったという測定メモを記していますが、詳細な測定条件はコードコメントにありません。

## 実行時の詳細

`c_inflight` はモデル状態オブジェクトのメンバー初期化時に読み取られます。`DS4_CACHE_THREADS` は `load` の expert-cache 初期化ブロックに入った時に読み取られ、worker 数分 `SwapBufs` を確保します。各要素に最大 expert blob サイズの pinned host buffer 3個（`a`, `b`, `h`）と device ごとの non-blocking CUDA stream を作り、要素ごとに `cache_loop` を実行する `std::thread` を起動します。以後環境変数を変更しても、作成済み worker 数は変わりません。

`cache_loop` は mutex / condition variable で保護された swap queue から swap を取り出します。expert を host buffer に並べ替え、CUDA copy stream で CPU→GPU の転送と必要な GPU→CPU の転送を行い、完了した swap を ready queue に積みます。`cache_tick_swaps()` は window 間に ready swap を反映し、expert slot と device table を更新します。queue への投入は expert cache の hit/heat に基づき、`sw_inflight < c_inflight` の場合に行われます。

この変数に固有の stdout/stderr ログはありません。`DS4_CHECK_SWAPS` が別途設定されている場合は swap worker が照合を行い、stderr に `ds4 cache: ...` の検査結果を出しますが、これは本変数自体のログではありません。

## 文書との照合

`docs/DETAILS.md` は `--expert-cache` の予算や expert cache の概説を説明していますが、`DS4_CACHE_THREADS` の値や worker 数の規則は説明していません。数値測定についても、コードコメントに「one V100」「4 measured no faster」とある以上の環境・手順は確認できないため、一般的な性能傾向としては扱いません。

## 根拠

- `src/dsv41/ds4_model.cu:1006-1008` — worker ごとの buffer / stream と既定数 1、および測定コメント。
- `src/dsv41/ds4_model.cu:1016-1019` — `DS4_CACHE_INFLIGHT` の変換と `c_inflight` 下限。
- `src/dsv41/ds4_model.cu:1112-1121` — swap queue、worker buffer、thread 状態。
- `src/dsv41/ds4_model.cu:2795-2809` — expert cache 条件、`DS4_CACHE_THREADS` の変換・clamp、buffer / stream / worker 作成。
- `src/dsv41/ds4_model.cu:6040-6083,6123-6124` — worker の queue 消費、copy 処理、ready queue への通知。
- `src/dsv41/ds4_model.cu:6245-6253,6268-6322,6338-6350` — window 間での swap 適用と inflight 上限。
- `docs/DETAILS.md:366-376` — expert cache size の説明。`DS4_CACHE_THREADS` の記載はない。
