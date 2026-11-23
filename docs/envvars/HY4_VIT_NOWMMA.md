# `HY4_VIT_NOWMMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 版 VisionEncoder の GPU 経路で、gfx11 / gfx12 向け WMMA（行列コア）カーネルを選ばないための抑止スイッチ。WMMA が選ばれないと、通常は fdot2 カーネルへ切り替わる。CPU VisionEncoder には適用されず、CUDA・Metal・SYCL の同名変数読み取りも確認できない。読み取りは `VisionEncoder::load()` にある（`engine/src/hy4flash/run/hy4_vision.hip.h:604-648`）。

## 値と判定

`getenv("HY4_VIT_NOWMMA")` の null 判定だけを使う。値の変換や文字列比較はせず、変数が存在すれば WMMA を抑止する。したがって `1` だけでなく `0`、`true`、`false`、空文字、空白を含む値もすべて「設定あり」として働き、大文字小文字や数値としての妥当性は関係しない（`engine/src/hy4flash/run/hy4_vision.hip.h:633-640`）。

| build / 実行条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `HY4_MMA && !HY4_CUDA` でコンパイルされた HIP GPU 経路、GPU arch が `gfx11` または `gfx12` で始まる | `use_wmma` が true になり WMMA を選ぶ | 値の内容を問わず、設定されていれば WMMA を抑止（例: `1`、`0`、`true`、空文字） | 該当なし。値自体を検査しない |
| 同じ HIP build だが GPU arch が `gfx11` / `gfx12` 以外 | `use_wmma` は false | WMMA はもともと選ばれず、この変数による追加の変更なし | 該当なし |
| `HY4_MMA && !HY4_CUDA` が成立しない build（CUDA または WMMA カーネルを含まない build） | このコードの読み取り自体がコンパイル対象外 | この変数はこの実装では読まれない | 該当なし |
| `VisionEncoder::load()` が CPU 読み込みへ進む | GPU カーネル選択前に戻る | この変数は読まれず、WMMA/fdot2 の選択に影響しない | 該当なし |

`HY4_MMA` は HIP で通常有効だが、RDNA2 (`gfx103x`) では 0 に設定される。WMMA 判定自体が `#if HY4_MMA && !HY4_CUDA` の内側にあるため、環境変数の効果はこの build 条件と GPU arch の両方に依存する（`engine/src/hy4flash/run/hy4_gpu.h:16-23,335-352`; `engine/src/hy4flash/run/hy4_vision.hip.h:633-640`）。

## 有効になる条件

- HIP GPU 版 VisionEncoder の `load()` が GPU 読み込みまで進み、ビルド時に `HY4_MMA && !HY4_CUDA` が成立していること。CUDA / WMMA 無効 build では読み取り箇所がコンパイルされない（`engine/src/hy4flash/run/hy4_vision.hip.h:624-640`）。
- GPU の arch 名が `gfx11` または `gfx12` で始まること。この条件を満たさない GPU では未設定でも `use_wmma` は false で、変数を設定しても選択は変わらない（同 `:633-640`）。
- 先に CPU 経路が選ばれていないこと。`force_cpu`、`HY4_VIT_CPU` の `atoi` が非 0、低 VRAM、または `hipMalloc` 失敗では CPU 読み込みを完了して return するため、この変数の判定には到達しない（同 `:613-630`）。
- 上記の CPU 経路選択が優先される。`load()` の引数は shard path と `force_cpu` で、WMMA 選択式には CLI 値を渡していない。確認した offline / server の呼び出し元はいずれも `force_cpu` を省略し、既定値 `false` を使う。したがって、この loader 内に CLI 値で環境変数の判定を上書きする処理はない（同 `:604-640`; 呼び出し元は `engine/src/hy4flash/run/hy4_main.hip.cpp:723` と `engine/src/hy4flash/run/hy4_serve.hip.h:436`）。
- WMMA を抑止した HIP GPU 経路では、`HY4_VIT_PLAIN` も未設定なら `use_fdot2` が true となる。`HY4_VIT_PLAIN` が設定されていれば、その値の内容を問わず fdot2 も選ばず plain カーネルへ進む（同 `:641-647`; GEMM 分岐は同 `:820-858`）。
- GPU 経路を利用する画像処理でのみ関係する。オフライン画像処理とサーバーの画像リクエストは `VisionEncoder::load()` を呼ぶが、画像のないリクエストではこの経路を通らない（`engine/src/hy4flash/run/hy4_main.hip.cpp:718-729`; `engine/src/hy4flash/run/hy4_serve.hip.h:431-445`）。

## 実行時の詳細

`VisionEncoder::load()` が画像 shard を GPU に読み込んだ後、HIP WMMA build では GPU arch 名を調べ、`gfx11` / `gfx12` かつ `HY4_VIT_NOWMMA` が未設定の場合だけ `use_wmma` を true にする。このフィールドは Encoder インスタンスの状態であり、関数 static やプロセス共通の環境値 cache ではない（`engine/src/hy4flash/run/hy4_vision.hip.h:604-648`）。

`use_wmma` は GEMM の WMMA / fdot2 / plain カーネル選択に加え、attention と V 転置バッファの確保方法にも使われる。したがってこの変数は画像 encoder の GPU 計算経路を変える。コード上、テキスト側のカーネルやデコーダ設定を直接変更する処理は確認できない（同 `:820-858,932-935,967-984`）。

Encoder が読み込み済みで `load()` を再度呼ぶと、`loaded` の早期 return により環境を読み直さない。unload 後の次回 load では改めて判定する。サーバー経路は VRAM 状態に応じて encoder を unload することがあり、オフライン経路では画像 encode 後に unload する（同 `:604-606,650-657`; `engine/src/hy4flash/run/hy4_serve.hip.h:446-451`; `engine/src/hy4flash/run/hy4_main.hip.cpp:727-729`）。

## ログと測定値

この変数だけを理由とする警告やエラーはない。GPU shard 読み込みログは選択結果を `[vision] shard loaded to the GPU: ... (wmma)`、`(fdot2)` または `(plain)` の末尾で示す。CPU 経路では `[vision] shard loaded on CPU (low-VRAM fallback): ...` と出て、この変数は評価されない（`engine/src/hy4flash/run/hy4_vision.hip.h:624-648`）。

`docs/DETAILS.md` の Vision 説明には読取方式の選択と一般的な時間の説明があるが、この変数による WMMA 切替の記載や比較測定値は確認できない（`docs/DETAILS.md:1113-1144`）。

## 根拠

- `engine/src/hy4flash/run/hy4_vision.hip.h:604-648` — `VisionEncoder::load()` の読み込み分岐、環境変数判定、GPU ログ。
- `engine/src/hy4flash/run/hy4_vision.hip.h:820-858,932-935,967-984` — WMMA / fdot2 / plain の GEMM・attention 経路および WMMA 用 V バッファ。
- `engine/src/hy4flash/run/hy4_gpu.h:16-23,335-352` — build macro と RDNA2 の WMMA 除外。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:718-729`; `engine/src/hy4flash/run/hy4_serve.hip.h:431-451` — offline / server の VisionEncoder 呼び出しと unload。
- `docs/DETAILS.md:1113-1144` — Vision の利用経路・設定についての資料との照合。
