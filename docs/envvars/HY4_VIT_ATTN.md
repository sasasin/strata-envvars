# `HY4_VIT_ATTN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal 版 Hy4-Flash の画像用 ViT attention 実装を選ぶ。`VitMetal::encode` は既定で MPP（materialised scores）経路を使い、値が文字列 `mpp` と完全一致しない場合は `v_attn` の simdgroup 経路を使う。したがって `sg` は後者を選ぶが、`sg` 以外の不一致値も同じ経路になる。対象は Metal の vision shard を使って画像を encode する処理であり、テキストだけの推論や CUDA/HIP/SYCL 実装にはこの読み取りがない（`engine/src/hy4flash/metal/hy4_metal_vision.h:199-205,245-247`）。

## 値と判定

`getenv` で値を取得し、未設定なら `mpp_attn=true`、設定済みなら `std::string(am) == "mpp"` の結果を使う。文字列全体の大文字小文字を区別する比較で、数値・空白・真偽値の parse はしない（`engine/src/hy4flash/metal/hy4_metal_vision.h:200-202`）。

| 条件 | unset | MPP 経路 | simdgroup 経路 |
|---|---|---|---|
| Metal の画像 ViT encode | `mpp` と同じく有効 | 文字列が厳密に `mpp`（例: `mpp`） | `sg`、空文字、`MPP`、`1`、`0`、`true`、`false`、`mpp `、その他すべての不一致値 |

## 有効になる条件

- Metal 版 Hy4-Flash の vision 実装を含む実行ファイルを使う。標準的な Metal runner と専用 vision test は `hy4_metal_vision.h` を include し、専用 build script がそれぞれをコンパイルする（`engine/src/hy4flash/metal/hy4_metal_main.cpp:30`; `engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:7`; `engine/src/hy4flash/metal/build_vis.sh:15-20`）。
- `VitMetal::encode` が呼ばれること。serve では `--vision` shard を指定し、その probe が成功し、画像リクエストを処理するときに初めて load/setup/encode する。vision shard がない場合、対象機能は利用できない（`engine/src/hy4flash/metal/hy4_metal_serve.h:292-300,323-331,365-373`; `engine/src/hy4flash/metal/hy4_metal_vision.h:306-318`）。専用 test では画像が指定されて encode されるときに参照される（`engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:58-75`）。
- この変数を読むのは Metal 実装だけであり、同じ名前の読み取りは他 backend には見つからない。

## 実行時の詳細

環境変数は shard の `load` 時ではなく、各 `VitMetal::encode` 呼び出しで評価される。値はメンバーや static に cache されないため、プロセス実行中に環境を書き換えた場合も次の encode が新しい値を読み得る（`engine/src/hy4flash/metal/hy4_metal_vision.h:92-100,174-202`）。serve は画像ごとに `encode` を呼ぶ（同ファイル: `306-318`）。

`mpp` 経路は attention score・softmax 結果・中間出力用の `d_s`, `d_p`, `d_o` buffer を追加確保し、QK、softmax、PV と出力処理を query block ごとに dispatch する。その他の値ではそれらの buffer を確保せず、単一の `v_attn` dispatch を使う。いずれの経路も後続の出力投影と ViT 層処理へ進む（`engine/src/hy4flash/metal/hy4_metal_vision.h:204-208,221-249`）。Metal kernel ソースも `v_attn` と MPP 用の `v_mpp_head_128_64_4` / `v_attn_out` を別々に定義している（`engine/src/hy4flash/metal/hy4_vision.metal:124-145,330-350,376`）。

変数値の検証、警告、fallback はない。選択値に関する専用ログもない。通常の処理エラーは serve から `ERR image: <理由>` として返され、専用 test では `encode: <理由>` を stderr に出して終了コード 1 となるが、ソース上これらは変数の不正値を検出する経路ではない（`engine/src/hy4flash/metal/hy4_metal_serve.h:365-370`; `engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:71-74`）。

## ログと測定値

`HY4_VIT_ATTN` の値や選択した経路を明示するログはない。専用 test は profiler を有効にし、処理時間を `[vit prof]` と `[vit] run ...` の行で stderr に出すが、環境変数の値や経路名は表示しない（`engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:67-75`; `engine/src/hy4flash/metal/hy4_metal_vision.h:265-269`）。この変数について条件付き測定値を示す設計資料は確認できなかった。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_vision.h:199-208` — 値判定と MPP 用 buffer。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:221-249` — attention 経路と後続処理。
- `engine/src/hy4flash/metal/hy4_metal_vision.h:306-318` — 各画像に対する encode 呼び出し。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:292-300,323-331,365-373` — serve の shard 条件、画像リクエスト、エラー応答。
- `engine/src/hy4flash/metal/hy4_vision_test_metal.cpp:30-36,58-75` — 専用 test の利用と観測出力。
- `engine/src/hy4flash/metal/hy4_vision.metal:124-145,330-350,376` — Metal 側の各 attention kernel。
