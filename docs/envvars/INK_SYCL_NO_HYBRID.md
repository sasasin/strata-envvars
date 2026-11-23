# `INK_SYCL_NO_HYBRID`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Intel Arc 向け Inkling SYCL runner の CPU/RAM hybrid MoE 実行を無効にする。`InkSyHybridEngine::init()` でこの変数が無効化条件に合致すると engine は `active=false` のまま戻り、MoE 層は runner 内の通常 GPU MoE 分岐へ進む。モデルの expert 配置・host expert 数を決める読み取りではなく、runner 初期化時に hybrid engine を使うか決めるフックである（`engine/src/inkling2/sycl/ink_sy_hybrid.h:488-495`; `engine/src/inkling2/sycl/ink_sy_runner.h:328-334,656-680`; `engine/src/inkling2/sycl/ink_sy_common.h:884-889,1216-1225`）。

## 値と判定

`std::getenv("INK_SYCL_NO_HYBRID")` が非 null で、かつ値の先頭文字が `'1'` の場合だけ `enabled=false` になる。それ以外は `enabled=true`。文字列全体の比較、数値変換、空白除去、大文字小文字変換はない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:488-495`）。

| 条件 | 値の例 | 判定 |
|---|---|---|
| 未設定 | — | 有効（通常の既定） |
| 設定済み、先頭が `1` | `1`, `1anything`, `10` | hybrid を無効化 |
| 設定済み、先頭が `1` 以外 | 空文字, `0`, `false`, `true`, ` 1`, `2` | hybrid は無効化されない |

判定は `init()` が呼ばれるたびに行われる。同じ engine では `init()` 冒頭で `release()` した後に環境を評価するため、その時点の値が使われる。値を後から変えても既に初期化済みの engine の `active` は変わらず、次の `init()` まで反映されない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:488-495`）。CLI 引数や別の設定値との優先順位処理はこの判定にない。

## 有効になる条件

- 対象は `InkSyHybridEngine` を `ink_sy_runner.h` から呼ぶ Inkling SYCL backend である。この判定箇所は `engine/src/inkling2/sycl/ink_sy_hybrid.h` にある（`engine/src/inkling2/sycl/ink_sy_runner.h:26,163,329`）。
- hybrid engine を実際に起動するには上記の無効化条件に当たらず、モデルの `n_host_experts` が 1 以上である必要がある。host expert がなければ値にかかわらず `active=false` で初期化を終える（`engine/src/inkling2/sycl/ink_sy_hybrid.h:491-495`）。
- host expert 数はモデル読込時に VRAM 側へ割り当てなかった expert から決まる。環境変数はその配置計算より後の `hybrid.init(m)` で評価される（`engine/src/inkling2/sycl/ink_sy_common.h:884-889,1216-1225`; `engine/src/inkling2/sycl/ink_sy_runner.h:328-330`）。
- `INK_SYCL_CPU_THREADS` は hybrid が有効で host expert がある場合にのみ worker 数を上書きする。`INK_SYCL_NO_HYBRID` が hybrid 初期化を止めると、この worker 数設定には到達しない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:491-495,524-529`）。
- 他の環境変数、CLI 引数、サーバーモード、モデル形式による追加の上書き条件は、この変数の判定箇所にはない。

## 実行時の詳細

runner の初期化で `hybrid.init(m)` を呼ぶ。無効値（先頭文字 `1`）または host expert 不在なら hybrid 用バッファ確保・worker 起動へ進まず、`active=false` で戻る。runner は続けて `hybrid=<0|1>` を含む ready 行を stderr に出す（`engine/src/inkling2/sycl/ink_sy_runner.h:328-334`; `engine/src/inkling2/sycl/ink_sy_hybrid.h:488-495`）。

`active=true` の場合、初期化は doorbell と staging 用領域を確保し、VRAM cache ring を予算内で確保し、CPU worker pool を起動して `active=true` にする。初期化成功時は stderr に `[ink_sycl_hybrid] ACTIVE: ...` を出す（`engine/src/inkling2/sycl/ink_sy_hybrid.h:501-541`）。MoE 実行ごとに runner は `active` を調べ、true なら `run_moe_hybrid()`、false なら通常の GPU 経路（dual-GPU 時の通常分岐を含む）へ進む（`engine/src/inkling2/sycl/ink_sy_runner.h:656-680`）。

有効時の hybrid MoE は `M <= 2` では VRAM resident expert と CPU worker に分けて実行し、`M > 2` では cold expert を staging 経由で GPU 実行する経路に入る。これは `INK_SYCL_NO_HYBRID` の値の追加 parse ではなく、engine が有効な場合の実行分岐である（`engine/src/inkling2/sycl/ink_sy_hybrid.h:619-640,699-740,743-845`）。

## ログと測定値

無効化専用の警告や理由ログはなく、runner ready 行の `hybrid=0` で inactive を観測できる。値が無効化条件に当たらず、host expert がある場合は `ACTIVE` 行が出る。`INK_SYCL_HYBRID_STATS` が設定され、かつ engine が active の状態で `release()` されたときだけ統計行を stderr に出す（`engine/src/inkling2/sycl/ink_sy_runner.h:330-333`; `engine/src/inkling2/sycl/ink_sy_hybrid.h:471-477,537-541`）。

`docs/DETAILS.md` にこの変数の説明や条件付き測定値は見当たらないため、性能差は記載しない。

## 根拠

- 候補名の唯一の Strata ソース参照と値判定、初期化条件: `engine/src/inkling2/sycl/ink_sy_hybrid.h:488-495`。
- runner 初期化と ready ログ: `engine/src/inkling2/sycl/ink_sy_runner.h:328-334`。
- active による MoE 分岐: `engine/src/inkling2/sycl/ink_sy_runner.h:656-680`。
- host expert 数の設定: `engine/src/inkling2/sycl/ink_sy_common.h:884-889,1216-1225`。
- active engine の確保・起動・ログと統計: `engine/src/inkling2/sycl/ink_sy_hybrid.h:471-477,501-541`。
- hybrid 実行の batch 分岐: `engine/src/inkling2/sycl/ink_sy_hybrid.h:619-640,699-740,743-845`。
