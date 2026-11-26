# `STRATA_SPLIT_COVER_B`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve --layer-split auto` の配置探索で、GPU キャッシュに入る expert profile の各順位に割り当てる「ルーティング質量」を決めるカバレッジ曲線の指数 `b` を上書きする。CUDA 実装は `engine/src/program/generate.cpp`、SYCL 実装は `engine/sycl/src/program/generate.cpp` にあり、探索スコアのキャッシュ miss 費用を変えて自動 split 境界に影響する。モデル実行時のルーティングや生成 token を直接変更する値ではない（CUDA: `engine/src/program/generate.cpp:7038-7055,7085-7108,7510-7515`、SYCL: `engine/sycl/src/program/generate.cpp:3970-3987,4007-4023,4173-4178`）。

## 値と判定

両実装とも `std::getenv` で設定の有無を調べ、設定されていれば `std::atof` で `double` に変換する。文字列全体の検証、範囲検査、clamp、変換失敗時のエラーはない。`atof` が数値として読める先頭部分を変換するため、先頭の空白や符号は許容され、後続文字は無視される。変換できない文字列や空文字は `0.0` になる。したがって `0`、`0anything`、`true`、空文字はいずれも指数 0 として扱われる一方、変数が設定されているためカバレッジ曲線自体は有効になる。`3abc` は 3 として扱われる。未設定だけが「変数なし」である（CUDA: `engine/src/program/generate.cpp:7041,7047-7055`、SYCL: `engine/sycl/src/program/generate.cpp:3973,3979-3987`）。

| GPU 数（`ns`）と設定 | `b` | 使用する順位質量 |
|---|---:|---|
| 2 または 3 GPU、未設定 | 3.0（ただし曲線式には使わない） | 旧式 `(r+1)^-1.2` |
| 4 GPU 以上、未設定 | 3.0 | `(1-r/n)^b - (1-(r+1)/n)^b` |
| 任意の GPU 数、設定あり | `atof` の結果 | 同じカバレッジ曲線式 |

ここで `r` は profile 順位、`n` は profile 件数。`b=3` が既定値で、明示値に対する有効範囲は設けられていない。0、負値、非有限値、NaN 等も拒否されず、そのまま `pow` と後続計算へ渡るため、そうした入力で探索値がどうなるかは入力文字列から単純な有効/無効判定にできず、正常な配置探索結果も保証されない。CUDA: `engine/src/program/generate.cpp:7040-7055`、SYCL: `engine/sycl/src/program/generate.cpp:3972-3987`。

## 有効になる条件

- 対象経路は server モードの `--layer-split auto`。層 split の指定は `o.serve` が真であることを要求し、1 GPU しか見えない場合は「no split」として自動指定を解除する（CUDA: `engine/src/program/generate.cpp:4803-4808,4836-4839,4848-4853`）。
- split が複数 GPU で実行されること。`--split-skip-if-fits` などで `multi_gpu` が解除されると自動配置探索に入らない（CUDA: `engine/src/program/generate.cpp:4856,6450-6480,6959-6961`）。
- 複数 GPU の layer split には `--expert-profile` が必要。profile の読み込みに失敗すればエラー終了し、未指定なら「a layer split across GPUs needs --expert-profile」で終了する（CUDA: `engine/src/program/generate.cpp:4895-4899,6746-6751`、SYCL: `engine/sycl/src/program/generate.cpp:2354-2357,3781-3784`）。
- 2 または 3 GPU では未設定時に旧式の質量式を使うが、空文字を含め何か設定すると新しい曲線を選ぶ。4 GPU 以上では未設定でも新しい曲線になる（CUDA: `engine/src/program/generate.cpp:7044-7055`、SYCL: `engine/sycl/src/program/generate.cpp:3976-3987`）。
- `--layer-split K[,K2...]` の手動境界ではこの auto 探索ブロックを通らない。CLI に `b` を指定する引数はなく、環境変数が指数の唯一の上書き手段。
- CUDA と SYCL の双方に実装がある。OS 固有条件や追加 build macro 条件はこの分岐にない。その他の backend に同じ名前の読み取りは見つからなかった。

## 実行時の詳細

設定値を読むのは `multi_gpu && split_auto` の自動配置探索に入ったときで、各プロセスの初期化中にその探索用の `cover_b` と `coverage_curve` を算出する。関数 `static` に保存する cache はなく、リクエストごとの読み取りでもない。このコード内で起動後に環境変数を書き換える処理は見つからず、通常は次回プロセス起動時に反映される（CUDA: `engine/src/program/generate.cpp:6959-6961,7040-7048`、SYCL: `engine/sycl/src/program/generate.cpp:3921-3924,3972-3979`）。

カバレッジ曲線は各順位 `r` の質量差を作り、配置候補ごとに profile 順の expert を各 stage の容量へ入れて、保持質量と miss 費用を見積もる。CUDA では各 stage の未保持質量に `STRATA_SPLIT_MISS_MS` と stage ごとの link scale を掛け、層処理時間と足して候補を比較する（`engine/src/program/generate.cpp:7085-7108`）。SYCL では `miss_ms * (1 - held_mass)` と層処理時間を合算する（`engine/sycl/src/program/generate.cpp:4007-4023`）。そのため同じ `b` でも profile 順、profile 件数、空き VRAM、GPU 速度などで選択境界は変わり得る。CLI が `--layer-split auto` を指定しても、探索が startable な配置を見つけられない場合は gate を外して速度だけで選び直し、候補もなければ `--layer-split auto: no valid split ...` を出して終了コード 2 となる（CUDA: `engine/src/program/generate.cpp:7487-7504`）。

## ログと測定値

この変数専用の有効/無効ログや値のエラー文言はない。正常に配置が決まると、CUDA と SYCL は選ばれた `K`、予測 decode window 時間、キャッシュが保持すると推定した profiled pair 数・ルーティング質量、候補数を stderr に出す（CUDA: `engine/src/program/generate.cpp:7510-7515`、SYCL: `engine/sycl/src/program/generate.cpp:4173-4178`）。出力は変数の値そのものを表示しない。

ソースコメントは `b=3` の例として 20,000 held（`f=0.8138`）で 99.35%、`f=0.59` で 93.2% と記し、別の実測値と比較している（CUDA: `engine/src/program/generate.cpp:7032-7036`、SYCL: `engine/sycl/src/program/generate.cpp:3964-3968`）。これはコメント中の特定 rig / traffic に関する記述であり、`STRATA_SPLIT_COVER_B` の任意値に対する性能や正確性の保証ではない。`docs/DETAILS.md` にこの変数の説明は見つからなかった。

## 根拠

- CUDA の読み取り・既定値・式: `engine/src/program/generate.cpp:7038-7055`
- CUDA の探索スコアと最終ログ・失敗: `engine/src/program/generate.cpp:7085-7108,7487-7515`
- CUDA の serve / auto 条件と profile 必須条件: `engine/src/program/generate.cpp:4803-4853,4895-4899,6746-6751`
- SYCL の読み取り・既定値・式と探索スコア: `engine/sycl/src/program/generate.cpp:3970-3987,4007-4023`
- SYCL の auto 探索・出力・profile 必須条件: `engine/sycl/src/program/generate.cpp:3921-3924,3781-3784,4173-4178`
