# `STRATA_METAL_GEMM_TILES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査対象リポジトリは `main`、開始時点で `origin/main` と一致し、未コミット変更はありませんでした。

## 役割

Metal の非 streaming prompt chain にある dense GEMM の threadgroup tile を、Apple M5 系で選び直します。`engine/metal/src/engine/window.cpp` の `gemm_tile` が tile dimensions を変更し、`engine/metal/src/engine/prompt_chain.inc` の `Window::pc_chunk` 内 GEMM dispatch がその値から kernel 名と grid を決めます（`window.cpp:91-99`, `prompt_chain.inc:283-288`）。この変数は prompt chain 自体の有効・無効を切り替えず、M5 用 tile 調整だけを無効にします。

## 値と判定

`gemm_tile` の最初の呼び出し時に `std::getenv` で読み、値全体を `std::string(e) == "0"` と比較します。未設定・空文字・`"1"`・`"00"`・`"0anything"`・`"false"`・空白付きの値はいずれも off にはならず、文字列の case や数値としての妥当性も検査しません。正確に `"0"` の場合に限り、M5 tile の選択を止めて helper の呼び出し元が設定した既定 tile を保ちます（`window.cpp:93-99`）。

| 条件 | unset | M5 tile 調整を止める値 | off にしない例 |
|---|---|---|---|
| `gemm_tile` が呼ばれる場合 | 調整を許可 | `0` | 空文字、`1`、`00`、`0anything`、`false`、` 0` |

## 有効になる条件

- Strata の Metal engine を含む build であり、実行時に Metal の prompt 経路を使うこと。Metal engine は `engine/metal/CMakeLists.txt` の `STRATA_METAL_ENGINE` が ON の場合に構成されます（`engine/metal/CMakeLists.txt:103-111, 150-154`）。
- prompt が非 streaming で、`STRATA_METAL_PROMPT=window` ではなく、prompt token 数が `STRATA_METAL_PROMPT_MIN`（未設定時 32）以上であること。この場合 `prompt_run_rows` から `Window::prompt`、`pc_chunk` へ進みます。条件外は 8-row window 経路などに進みます（`window.cpp:3743-3777`, `prompt_chain.inc:583-597`）。
- `gemm_tile` は device 名が `Apple M5` で始まる場合だけ tile を変更します。それ以外の chip 名では既定 tile のままです（`window.cpp:94-99`）。
- `STRATA_METAL_GEMM_TILES` は `STRATA_METAL_PROMPT` や `STRATA_METAL_PROMPT_MIN` による経路選択を上書きしません。また、コード上でこの tile helper を呼ぶのは `prompt_chain.inc` の GEMM lambda です。streaming 用 `prompt_gemm` 経路（`window.cpp:3185-3190, 3749-3766`）では呼ばれません。

## 実行時の詳細

`pc_chunk` が dense GEMM を dispatch するたび、初期値 `tm=64`, `tn=(Nn <= 64 ? 32 : 64)` を設定して `gemm_tile` を呼びます。環境変数が正確に `"0"` でなく、device 名が `Apple M5` で始まる場合、`Nn == strata_metal::geo::N && K == strata_metal::geo::ZV` なら `64 x 128`、そうでなく `Nn >= 6144` なら `128 x 64` を選びます。その他の形状・chip では初期値を変えません。helper 後は tile 寸法を kernel 名 `gemm_f16_<tm>_<tn>_4` と dispatch grid `(ceil(Nn/tn), ceil(M/tm))` に使います（`window.cpp:94-99`, `prompt_chain.inc:283-288`）。

環境値の判定は関数内 `static const bool` に保存され、最初の `gemm_tile` 呼び出しで一度評価されます。その後のプロセス内環境変更は再評価されません。prompt 経路そのものは `STRATA_METAL_PROMPT`、`STRATA_METAL_PROMPT_MIN` と streaming 状態に依存します。CLI 引数や設定ファイルから tile 判定を上書きする処理はこの経路にありません（`window.cpp:94-99, 3743-3766`）。

ソースコメントは変更を「出力を分割する tile のみの差で bit-identical」と説明しています。これは実装コメントの記述であり、この調査では build・実行・出力比較を行っていません（`window.cpp:91-93`）。

## ログと測定値

この変数の値や選択 tile を直接表示するログ、無効値の警告、専用の終了・失敗分岐はありません。prompt chain の計測ログは `STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定された場合に出ますが、tile 値は出力しません（`prompt_chain.inc:608-610`）。

`window.cpp:91-93` のコメントには、M5 Max の `T=2048/4096` で測った GDN out projection（`N=2560, K=6144`）について `64 x 128 (1.17 -> 0.99 ms)` とあります。測定方法、モデル、OS、反復回数などの条件はそのコメントに記載されていないため、この値を他の環境へ一般化できません。

## 根拠

- `engine/metal/src/engine/window.cpp:91-99` — tile の既定・M5 分岐、`getenv` と文字列判定。
- `engine/metal/src/engine/prompt_chain.inc:283-288` — helper の呼び出し、kernel 名と dispatch grid への反映。
- `engine/metal/src/engine/window.cpp:3743-3777` — prompt 経路の選択と streaming 経路。
- `engine/metal/src/engine/prompt_chain.inc:583-610` — prompt chain の chunk 実行と計測ログ条件。
- `engine/metal/CMakeLists.txt:103-111, 150-154` — Metal engine の build 条件とソース群。
