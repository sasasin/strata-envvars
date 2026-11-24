# `STRATA_INK_EXACT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA Inkling-2 の hybrid engine で、VRAM に常駐していない cold MoE expert を CPU worker pool で計算するか、GPU にコピーして CUDA kernel で計算するかを選ぶ。`STRATA_INK_EXACT` が未設定なら初回の短い launch probe で選び、値が設定されていれば CPU lane または GPU copy-in lane を強制する。読み取りは `InkHybridEngine::start_workers()` にある（`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1793`）。

この設定が対象にするのは cold expert の計算 lane であり、GPU 上の resident expert の処理は分岐しない。実装上の設定名参照と `getenv` 読み取りは CUDA hybrid 実装にあり、HIP 側の `ink_hip_backend.hip.cpp` にはこの名前の読み取りがない。候補一覧の settings register は backend を `cuda-hip` と記録しているが、調査対象 commit の実コードで値を読むことを確認できたのは CUDA 側だけである（`engine/src/inkling2/cuda/ink_hybrid.cuh:1789`; `terminal/data/settings-register.json:16609-16619`）。

## 値と判定

`std::getenv` の null 判定後、値全体の parse はせず `e[0] != '0'` で判定する。未設定だけが自動選択になる。空文字は設定済みで先頭文字が `'0'` ではないため GPU copy-in lane を強制する。`0` で始まる文字列は CPU lane、それ以外は GPU copy-in lane となる。大文字小文字、数値としての妥当性、後続文字は検査しない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1789-1790`）。

| 条件 | unset | 有効になる値 | CPU lane になる値 |
|---|---|---|---|
| CUDA Inkling-2 hybrid worker pool が開始される | `lane_pref=0`（自動選択） | `1`, `true`, `false`, 空文字, ` 1`, `x` など先頭文字が `0` 以外 | `0`, `0anything`, `00`, `0 ` など先頭文字が `0` |

設定値は `atoi` 等の数値変換を通らない。したがって `true` は有効、`false` も先頭文字 `f` のため有効、`0anything` は無効で CPU lane を選ぶ。無効値の警告や fallback parse はない。強制値の場合は stderr に lane の説明が出る（`engine/src/inkling2/cuda/ink_hybrid.cuh:1789-1793`）。

## 有効になる条件

- CUDA Inkling-2 engine のモデル配置で host 側に置かれる expert があるとき `start_workers()` が呼ばれ、環境変数を読む。全 expert が VRAM に収まる場合は `n_host_experts == 0` となり worker pool が開始されず、この変数は読まれない（`engine/src/inkling2/cuda/ink_runner.cuh:406-424,497-503,622-628`）。
- `start_workers()` は既に `active` なら直ちに戻るため、最初の開始時に lane preference が決まる。ロード後の `pick_cold_lane()` は強制値 (`lane_pref != 0`) なら probe を行わない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1779-1790`; `engine/src/inkling2/cuda/ink_runner.cuh:3715-3718`）。
- unset の自動選択では hybrid が active で cold expert が存在する必要がある。layer-split (`m.ls_active`) または画像 step (`has_img_step`) では測定を行わず CPU lane を維持し、理由を stderr に出す（`engine/src/inkling2/cuda/ink_runner.cuh:3715-3721`）。
- GPU copy-in lane の graph staging は `STRATA_INK_EXACT_GRAPH=0` で無効化できる。さらに hybrid inactive、SSD-only、pinned host arena 不在、host metadata 不在、または既に staging 済みの場合も staging 準備をしない。その場合 exact lane は eager 経路を使う（`engine/src/inkling2/cuda/ink_hybrid.cuh:1368-1369,1380-1398`）。
- lane の設定値を上書きする CLI 引数はこの読み取り箇所にはない。`STRATA_INK_EXACT_GRAPH` はコピー方式の staging を制御する別設定であり、`STRATA_INK_EXACT` の lane 選択値は変えない（同上）。
- 調査対象コードに、この名前を読む server / CLI 層や別 backend への転送処理は見つからない。選択は CUDA Inkling runner の初期化時に行われる（`engine/src/inkling2/cuda/ink_hybrid.cuh:1789`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:354-358`）。

## 実行時の詳細

`start_workers()` は pool の初期化時に環境を読み、`lane_pref` と `exact_mode` を設定する。関数内 static cache ではなく engine instance の状態に保存されるが、worker pool が active になった後は再読しない。通常の起動ではモデルの expert 配置・staging 初期化後、CUDA backend が runner の `pick_cold_lane()` を呼ぶ（`engine/src/inkling2/cuda/ink_runner.cuh:622-628`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:354-358`）。プロセス実行中に環境変数を変更しても既存 runner の lane には反映されない。

- `STRATA_INK_EXACT=0` 相当では `set_lane(false)` が CPU lane を選ぶ。値が `1` 相当なら `set_lane(true)` が GPU copy-in lane を選び、cold expert を GPU にコピーしてカード側 kernel で計算する。exact lane では `dec_pcie_share` を `1.0` にする（`engine/src/inkling2/cuda/ink_hybrid.cuh:1360-1374,1789-1790`）。
- M=1 decode で `exact_mode && exact_graph` の場合は CUDA graph 内で cold expert を stage/copy し、dispatch 後に expert table を復元する。M=1 で exact lane でも graph staging が使えない場合は `needs_eager()` が true となり、M=1 CUDA graph capture 条件から外れる。通常の cold miss dispatch は eager copy 側を通る（`engine/src/inkling2/cuda/ink_hybrid.cuh:1368-1369,2505-2521`; `engine/src/inkling2/cuda/ink_runner.cuh:3663-3665`）。
- M=2..16 の batch/verify 経路では cold expert miss を GPU へ stream する通常の dispatch に進む。exact lane が `dec_pcie_share=1.0` にするため、この分岐では CPU と GPU に miss を分ける条件 (`share < 0.999`) に入らない（`engine/src/inkling2/cuda/ink_hybrid.cuh:2570-2597,2720-2731`）。
- unset の probe はコード内の固定 24 token ID 列を使い、各 lane で warm 6 step、測定 18 decode step を実行して中央値を比較する。実際の user prompt を測るのではない。GPU copy-in lane が CPU lane の 90% 未満の時間（10%以上速い）なら GPU lane、それ以外は CPU lane を採用する。probe 中は tier の移動と学習を止め、終了後に統計・trace カウンタ等を reset する（`engine/src/inkling2/cuda/ink_runner.cuh:3711-3754`; `engine/src/inkling2/cuda/ink_hybrid.cuh:1366,2365`）。
- その probe が選ぶのは実装コメント上「この machine / placement で速い lane」であり、exact lane が使えること自体は、GPU に置いた expert と cold expert の結果を同じにする目的として説明されている。CPU lane は all-resident 実行と丸め結果が異なる可能性をログ文面が示す（`engine/src/inkling2/cuda/ink_runner.cuh:3711-3714,3755-3758`）。

## ログと測定値

値を設定して lane を強制すると stderr に次のいずれかを出す。文言は実装どおりで、`=1` / `=0` は判定の説明として固定文字列になっている（空文字や `true` でも判定に応じた行が出る）。

- GPU copy-in lane: `[InkHybrid] cold experts: copied into the card and computed by its kernels (STRATA_INK_EXACT=1: the same bits wherever an expert lives)`
- CPU lane: `[InkHybrid] cold experts: computed on the CPU where they are (STRATA_INK_EXACT=0)`

unset では、測定終了後に `[InkHybrid] cold experts: launch probe (18 decode steps each): CPU lane %.1f ms/token, copy into the card %.1f ms/token -> ... (STRATA_INK_EXACT=1 or 0 forces a lane)` を stderr に出す。layer-split または画像 step の場合は `[InkHybrid] cold experts: no launch probe on this configuration, computed on the CPU where they are` を出す。強制値では probe の結果行は出ない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1791-1793`; `engine/src/inkling2/cuda/ink_runner.cuh:3717-3720,3755-3758`）。

`exact_prepare()` の staging buffer に対する `cudaMalloc` が失敗した場合は CUDA error を取得して `d_stage=nullptr` とし、その場では専用エラー行を出さず eager 経路にする。ほかの `INK_CK` 対象の CUDA 操作での終了・エラー表示は共通 macro の動作に依存し、この環境変数固有の無効値エラーや終了処理はない（`engine/src/inkling2/cuda/ink_hybrid.cuh:1381-1398`）。資料中の独立した性能測定値は確認できず、probe の実時間は実行時に当該 machine で測る値である。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:1360-1374,1380-1398,1779-1793,2505-2521,2570-2597,2720-2731`
- `engine/src/inkling2/cuda/ink_runner.cuh:406-424,497-503,622-628,3663-3695,3711-3758`
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:354-358`
- `terminal/data/settings-register.json:16609-16637`（候補メタデータとの照合。実装挙動の根拠ではない）
