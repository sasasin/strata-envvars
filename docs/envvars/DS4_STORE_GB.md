# `DS4_STORE_GB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 エンジンの GGUF モデルで、GPU に載らない routed expert を需要に応じて読み込む RAM store の最大サイズを GB 単位で指定します。Strata が起動する同梱エンジンの DS4 モデル読み込み経路がこの変数を読みます。名前に `SSD` が含まれますが、ソース上の store は RAM の slot arena で、モデルファイルから expert を読み込んで保持します。

この環境変数が存在すると `--ssd-cache` の値より優先されます。store のサイズが 0 以下になれば store は初期化されず、該当する auto モードで可能な場合の CPU lane expert 全コピー経路も選ばれません。

## 値と判定

`std::getenv("DS4_STORE_GB")` で設定有無を判定し、設定されていれば値を `std::atof` に渡します。文字列全体の検証や範囲 clamp はありません。`atof` は数値の先頭部分を変換するため、たとえば `"12.5junk"` は 12.5、空文字や数値として読めない文字列は 0 になります。

| 値 | 結果 |
|---|---|
| 未設定 | `--ssd-cache` の値を使う。既定値は -1 で、自動サイズを計算する。 |
| 0（または `atof` で 0 になる文字列） | RAM store を無効化する。 |
| 正数 | その値を store の最大予算（10進 GB、`GB * 1e9` bytes）にする。 |
| 負数 | 自動サイズ分岐に入る。環境変数が設定されているため、後述の RAM 再見積もりと CPU lane 全コピー判定は通常の未設定 auto と異なる。 |

変換で得られた値は `store_gb()` 内の関数 static にキャッシュされます。モデルの blob layout がこの値を使うため、一度決定した値はプロセス内で再評価されません。

## 有効になる条件

正のサイズでも store が実際に作られるのは、モデルが GGUF であり、読み込み時点で routed expert がファイルから読まれる設定（`file_experts`）、layer が存在し、先頭 layer の形式が `gg::kFmtMXFP4` の場合です。どれかを満たさないと `init_store()` は終了します。モデルが GGUF 以外なら `store_gb()` は強制的に 0 にします。

自動値（負数）の決定は次の通りです。

- 未設定かつ `--ssd-cache` も既定の auto の場合、CPU lane の expert が利用可能 RAM に収まると判定されれば、需要 store を使わず `auto_copy_all` 経路を選びます。`DS4_STORE_GB` が設定されていると `cpu_lane_fits_ram()` は false を返すため、この全コピー判定は使われません。
- それ以外の auto では、最初の RAM 空き量から 12 GB を差し引き、残りが 4 GB 以上なら、その残りと `max(48 GB, GGUF 内の trunk の routed expert 総 bytes)` を GB に換算した値との小さい方を予算にします。48 GB は計算上の下限であり、store は expert 総量を超えて埋まりません。4 GB 未満、または RAM 空き量を取得できない場合は 0 GB です。
- 環境変数が設定されている（負数を含む）場合は `store_gb_now()` が GPU 重みロード後の RAM 再見積もりを行いません。未設定で CLI も auto の場合に限り、空き RAM とコンテキスト長を用いて予算を再計算し、初期値より小さければ stderr にサイズ変更の行を出します。

指定値は上限予算であり、確保量を保証しません。store は slot 数に換算して arena の上限を決めます。初期化時に最大 slot が 1 つも入らなければ `ds4: --ssd-cache: the store could not start` を stderr に出して store を使わず続行します。arena は必要に応じて chunk ごとに commit され、空き RAM が chunk サイズと floor の合計より少ない場合は増やせません。floor の既定値は 8 GiB で、別変数 `DS4_STORE_FLOOR_GB` が設定されていればそちらで変更されます。

## 実行時の詳細

`store_gb()` は model layout の作成中にも呼ばれ、expert blob 内の行間 padding を store の aligned read 用に決めます。そのため値はモデル読み込み中に一度決定・キャッシュされます。モデル読み込みの最後に `init_store()` が呼ばれ、予算から slot 数を設定して RAM store を初期化します。その後 `preload_store()` が profile にある expert を読み込みます。実際の読み込みは store の slot 上限と RAM floor に制限されます。

store が正常に開始すると stderr に `ds4: RAM store: up to ...` の行が出ます。自動サイズが CPU lane の expert 全体より 1 GB 以上小さく、verbose が有効な場合は、残りを SSD から読む旨の補足も出ます。設定予算が 0 以下、モデル形式などの条件不一致、または store 初期化失敗では通常の RAM store 開始ログは出ません。

起動後に環境変数を変更しても、static cache 済みの値や既に作成された store には反映されません。子プロセスへの転送や上書きは、この環境変数の実装箇所では行っていません。

## 根拠

- `src/dsv41/ds4_model.cu:4578-4611` — CPU lane 全コピー条件、expert 上限計算、自動サイズ、環境変数変換と static cache。
- `src/dsv41/ds4_model.cu:4613-4631` — GPU 重みロード後の自動サイズ再見積もりとログ、環境変数設定時の再計算抑止。
- `src/dsv41/ds4_model.cu:4633-4642,4657-4664,4710-4723` — store 初期化条件、予算 bytes、設定引き渡し、失敗・開始ログ。
- `src/dsv41/ds4_model.cu:1672` — layout 時にもサイズを参照すること。
- `src/dsv41/ds4_model.cu:2819-2823` — モデル読み込み末尾の `init_store()` と preload。
- `src/dsv41/ds4_model.hpp:37-40` — RAM store と `--ssd-cache` の役割、CLI 側の auto 既定値。
- `src/dsv41/ds4_main.cpp:1217` — `--ssd-cache` の引数変換。
- `src/dsv41/ds4_store.hpp:73-108,480-493` — slot 上限、初期化失敗条件、chunk 確保と RAM floor。
- `docs/DEEPSEEK41.md:104` — RAM store がモデル起動時に自動サイズを決めるという利用者向け説明。`docs/DETAILS.md` には `DS4_STORE_GB` に関する説明は見つかりませんでした。
