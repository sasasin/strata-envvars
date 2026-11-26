# `STRATA_VISION_ARCH_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP 版の `strata-vision-hip` が起動時に行う GPU architecture とビルド対象一覧の照合を省略するための変数。省略すると、GPU 自体が見つかった後の architecture 不一致では reader が `ERR` を返して終了する代わりに、GPU reader はその照合を通過して処理を続ける。CUDA、SYCL、Metal、CPU reader にはこの判定コードがない。実装は `terminal/tools/vision/strata_vision.cpp:108-125`。

## 値と判定

HIP ビルドで `--gpu` が指定された起動に限り、`std::getenv` の結果を `std::atoi` に渡し、その整数が 0 かどうかで分岐する。文字列全体の妥当性検査はしない。`atoi` が読み取る整数部分が 0 なら照合を省略し、0 以外なら照合を行う。

| 条件（build / 起動） | unset | 照合を省略する値 | 照合を行う値 |
|---|---|---|---|
| `STRATA_VISION_HIP` 定義済み、`--gpu` あり | 照合する | `0`、空文字、`false`、`abc`、`0anything`、空白だけなど（`atoi` 結果が 0） | `1`、`-1`、`true`、`1anything`、` 1tail` など（先頭の整数変換結果が 0 以外） |
| HIP 以外の build、または `--gpu` なし | この変数を読まない | 該当なし | 該当なし |

`atoi` の整数変換なので、`true` / `false` の真偽文字列としては解釈しない。英字の大文字小文字や末尾文字の検証もない。先頭の空白と符号付き整数の規則に従い、数値の後ろは無視される。値の設定や CLI 引数による上書き処理はありません。根拠: `terminal/tools/vision/strata_vision.cpp:119-120`。

## 有効になる条件

- HIP reader を `--gpu` 付きで起動すること。通常は AMD GPU 用の `strata-vision-hip` が該当する。HIP macro と実行ファイル名の設定は `terminal/tools/vision/CMakeLists.txt:25-28,84-90`。
- 先に `VitGpu::available` が成功し、GPU が見つかること。見つからない場合はこの変数の判定前に `ERR this picture reader found no GPU (it was built for: %s)` を stdout に出して終了コード 3 で終了する（`terminal/tools/vision/strata_vision.cpp:108-117`, `terminal/tools/vision/own/vit_gpu.cu:898-903`）。
- `strata_gfx_in` が architecture 文字列から `gfx` と16進文字列を抽出できること。抽出結果が空の場合は変数の値にかかわらず一覧照合を行わず、そのまま先へ進む（`terminal/tools/vision/strata_vision.cpp:118-120`, `terminal/tools/vision/gpu_arch.h:12-20`）。
- 抽出結果が空でなく、`atoi` の結果が 0 以外なら、ビルド時の `STRATA_VISION_HIP_ARCHS` に一致する項目が必要。一致判定は項目全体の文字列一致で、`,`・`;`・空白を区切りとして扱う（`terminal/tools/vision/strata_vision.cpp:120`, `terminal/tools/vision/gpu_arch.h:22-32`）。
- サーバーでは `--vision gpu` などの設定によって GPU reader が選ばれていること。AMD の設定には CPU reader が fallback として登録され、GPU reader が `ERR` で開始できない場合は CPU reader に切り替わる（`terminal/strata_control/vision_reader.py:1-9`, `terminal/serve/server.py:3063-3069,3142-3157`）。

## 実行時の詳細

値は reader プロセスの `main` 内で、GPU reader の起動ごとに一度読み取られる。static cache はなく、そのプロセスが生きている間の環境変更を再評価しない。サーバーは reader 起動時に `popen(..., env=env)` で環境マッピングを渡し、`env` が `None` なら子プロセスは通常のプロセス環境を継承する（`terminal/serve/server.py:3214-3221`）。この変数に特別な引数優先規則はない。

照合が有効で、GPU architecture がビルド一覧にない場合、reader は stdout に `ERR this GPU (%s) is not in the picture reader's build (%s)` を出し、flush して終了コード 3 を返す（`terminal/tools/vision/strata_vision.cpp:120-124`）。サーバーは起動応答の `ERR` を失敗として扱い、CPU fallback があれば `[strata] the GPU picture reader did not start (...); pictures are read on the CPU` を出して CPU reader を開始する。fallback がない場合は起動例外を伝播する（`terminal/serve/server.py:3142-3157,3230-3243`）。

照合を `0` で省略したとき、または architecture 抽出結果が空のときに、その後の GPU 処理が対象 GPU で成功するかはこの判定だけでは保証されない。照合を省略した後の不一致 GPU の挙動は本変数の Strata 側コードからは確定できないため、ここでは記述しない。

## ログと測定値

変数が unset または `atoi` 結果が 0 以外の場合に、照合失敗で出る文言は `ERR this GPU (%s) is not in the picture reader's build (%s)`。終了コードは 3。サーバー経由で CPU reader が利用可能なら fallback の1行が表示される。照合を省略した事実を示す専用ログはない（`terminal/tools/vision/strata_vision.cpp:119-124`, `terminal/serve/server.py:3142-3157`）。この変数による性能測定値は資料に記載されていない。

`docs/DETAILS.md:1146-1149` は AMD の GPU reader が起動できなければサーバーが CPU reader を起動すると説明しているが、この変数や値の規則は記載していない。上記の値判定と architecture 照合は現行ソースに基づく。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:108-125` — HIP と `--gpu` の条件、GPU の事前確認、変数の読み取り、判定、標準出力と終了。
- `terminal/tools/vision/own/vit_gpu.cu:898-915` — GPU 有無と architecture 名の取得。
- `terminal/tools/vision/gpu_arch.h:12-32` — architecture 抽出とビルド一覧との比較。
- `terminal/tools/vision/CMakeLists.txt:25-39,84-90` — HIP reader と architecture 一覧の build 条件。
- `terminal/serve/server.py:3063-3069,3142-3157,3214-3243` — server の環境受け渡し、GPU reader の失敗検出と CPU fallback。
- `terminal/strata_control/vision_reader.py:1-9` — AMD GPU reader と CPU fallback の選択説明。
- `docs/DETAILS.md:1146-1149` — サーバーでの AMD reader fallback の概要。
