# `HY4S_SKIP_EXPERTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

SYCL の `Runner::run_routed_experts` で、MoE の routed expert 出力バッファ `zout_f` をゼロにして、その呼び出しでの routed expert 評価を省きます。ルーター計算と選択、`mlp_moe_pre` 内の routed down projection、shared experts の計算、`mlp_moe_post` の後処理はこの分岐の外にあるため、これらは残ります。したがってモデルの通常出力を保つ設定ではなく、routed expert の寄与をゼロにする診断・実験用のスイッチです（`engine/src/hy4flash/sycl/sy_graph.h:1066-1102`, `1120-1150`, `1104-1117`）。

この名前を読む実装は `engine/src/hy4flash/sycl/sy_graph.h` のみです。Strata リポジトリ全体で候補名を検索し、helper 経由や動的な名前の渡し先も確認しましたが、他の参照・転送箇所はありません。対象名は環境変数候補一覧 `docs/envvars/000_envvers.md:420` に掲載されています。

## 値と判定

`std::getenv("HY4S_SKIP_EXPERTS")` の戻り値が null かどうかだけで判定します。値の parse や文字列比較はありません。未設定なら通常経路へ進み、何らかの値が設定されていればゼロ化します。明示的な空文字も null ではないため有効です。`0`、`false`、`0anything`、空白を含む値、大文字小文字を変えた値も、設定されている限りすべて有効です（`engine/src/hy4flash/sycl/sy_graph.h:1146-1150`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の routed expert 処理で `use_gx == false` | routed expert の通常計算へ進む | 空文字を含む、設定されたすべての値 | なし |
| `use_gx == true` | GPU experts 経路へ進む | この分岐では参照されない | 該当なし（値にかかわらずこの経路では作用しない） |

## 有効になる条件

- Strata の SYCL `Runner` が routed expert 処理を実行する経路であること。この名前の読み取りは `engine/src/hy4flash/sycl/sy_graph.h` にのみあります。
- `run_routed_experts` の `use_gx` が false であること。true の場合は `gx->run(...)` を呼び、時間を加算して先に return するため、環境変数の判定に到達しません（`engine/src/hy4flash/sycl/sy_graph.h:1134-1149`）。
- eager 経路では `use_gx` は `gx != nullptr && T >= gx_min_T` で決まります。CLI は `--gpu-experts` と `--gx-min-t` の値、および GPU experts の初期化成功により `gx` と閾値を設定します。初期化できず `gx` が設定されない場合や chunk が閾値未満の場合は `use_gx` が false になり、この環境変数の分岐が使われます（`engine/src/hy4flash/sycl/sy_graph.h:1231-1243`; `engine/src/hy4flash/sycl/sy_main.cpp:104`, `162-163`, `301-335`）。
- サーバーでも GPU experts 初期化に成功すると `gx` を設定し、閾値は 32 token です。chunk が 32 以上なら GPU experts 経路が先行し、この変数は作用しません。未初期化または 32 未満の chunk は `use_gx == false` となり得ます（`engine/src/hy4flash/sycl/sy_serve.h:289-301`; `engine/src/hy4flash/sycl/sy_graph.h:1238-1243`）。
- SYCL command graph 経路では各層から `run_routed_experts(il, T, false)` を呼ぶため、この関数内の環境変数分岐に進みます（`engine/src/hy4flash/sycl/sy_graph.h:1337-1368`）。通常の eager/graph 選択条件は `forward_chunk` にあります（同 `1382-1391`）。
- CLI の `--force-route` で `force_route_dir` が設定されている場合は graph 経路を使わず、環境変数判定より前に route ファイルを読みます。ファイルの読込失敗または要素不足では `force-route: cannot load layer %d` を stderr に出して終了コード 5 で終了するため、環境変数を設定してもこの失敗は回避しません（`engine/src/hy4flash/sycl/sy_main.cpp:168`, `286`; `engine/src/hy4flash/sycl/sy_graph.h:1120-1132`, `1387-1389`）。
- この変数自体に CLI 引数・別環境変数との値の優先順位や上書き処理はありません。GPU experts 経路の選択が、この変数の判定を通るかどうかを決めます。

## 実行時の詳細

`mlp_layer` は routed 層で router と routed down projection を含む `mlp_moe_pre`、shared experts の `mlp_moe_shared` を先に実行し、その後 `run_routed_experts` を呼びます。`use_gx` が false で環境変数が設定されている場合、`zout_f` の `T * 1536` 個の float を `dzero` でゼロにし、CPU expert 時間を加算して return します。これにより通常の CPU/VRAM-cache/peer routed expert 実行は行いません。続く `mlp_moe_post` の routed up projection はゼロ化された `zout_f` を入力にし、shared 側の値との後処理は続きます（`engine/src/hy4flash/sycl/sy_graph.h:1066-1102`, `1104-1117`, `1120-1150`, `1231-1243`）。

値は関数内 `static` に保存されず、`run_routed_experts` が routed 層ごとに呼ばれるたびに `getenv` で読み直されます。Strata 内にこの変数を書き換える処理は見つかりませんでした。子プロセスへの転送もありません。起動時に設定した値は通常そのまま各呼び出しで参照されます（同 `1120-1150`）。

## ログと測定値

この環境変数の判定・ゼロ化に伴う専用ログや警告はありません。`force_route_dir` の読込失敗は前述のとおり stderr にエラーを出し、終了します（`engine/src/hy4flash/sycl/sy_graph.h:1124-1129`, `1146-1150`）。`docs/DETAILS.md` にこの変数の効果に関する測定値は見当たらず、測定値は記載していません。

## 根拠

- `engine/src/hy4flash/sycl/sy_graph.h:1066-1102` — routed 層の router/down projection と shared experts。
- `engine/src/hy4flash/sycl/sy_graph.h:1104-1117` — routed output と shared output を使う後処理。
- `engine/src/hy4flash/sycl/sy_graph.h:1120-1150` — route ファイル読込、GPU experts 優先分岐、環境変数判定、ゼロ化。
- `engine/src/hy4flash/sycl/sy_graph.h:1231-1243`, `1337-1368` — eager/graph からの呼出しと引数。
- `engine/src/hy4flash/sycl/sy_main.cpp:104`, `162-163`, `301-335` — CLI の GPU experts 閾値と初期化。
- `engine/src/hy4flash/sycl/sy_serve.h:289-301` — サーバーの GPU experts 初期化と閾値。
- `engine/src/hy4flash/sycl/sy_graph.h:1382-1391` — graph を選ぶ条件。
