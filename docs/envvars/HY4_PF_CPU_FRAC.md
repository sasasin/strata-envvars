# `HY4_PF_CPU_FRAC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の HY4 hybrid prefill streaming で、CPU RAM に常駐している tier-2 expert の一部を GPU 転送・計算の対象から外し、prefill 中に CPU expert pool で並列計算する割合を指定する。割合は expert 数全体ではなく、各層で CPU に常駐し、すでに VRAM/vcache にない tier-2 expert の候補 `lay` に対する割合である。フラグ付けされた expert は GPU 用の group table で無効化され、実際に選択された場合は CPU 側の計算対象になる。`Runner::pf_init` と `Runner::pf_build_groups` に実装されている。`engine/src/hy4flash/run/hy4_graph.hip.h:416-455, 641-646, 2573-2602`

## 値と判定

`pf_init` が初期化中に `getenv` で設定有無を調べ、設定されていれば `atof` で数値変換し、`std::max(0.0, std::min(0.45, value))` で 0〜0.45 に clamp する。文字列全体の妥当性検査やエラー通知はない。`atof` が数値として読める先頭部分を変換するため、数値の後ろの文字は検査されず、先頭が数値でない文字列や空文字は 0 になる。先頭の空白や符号を含む数値も変換対象になる。`engine/src/hy4flash/run/hy4_graph.hip.h:641-642`

| 条件 | unset | 有効になる値（例） | 無効・分割なしになる値（例） |
| --- | --- | --- | --- |
| 変数が設定されている | 自動値は使わない | `0.1` → 0.1、`0.5` → 0.45 に clamp、`0.2junk` → 0.2 | 空文字、`abc`、`0`、負値 → 0。変換後の値が `0.001` 以下では分割条件を満たさない |
| 変数が未設定 | bounce ring 使用時かつ CPU thread 数が 12 以上なら 0.20。それ以外は初期値 0.0 | 自動値 0.20 | 自動値 0.0 |

分割処理は `pf_cpu_frac > 0.001` かつ当該層の候補 `lay.size() > 8` のときだけ実行される。対象数は `size_t(lay.size() * pf_cpu_frac)` への切り捨てで算出し、最大でも `lay.size()-1` に制限する。そのため小さな正の割合でも、切り捨て後の個数が 0 なら分割 expert は発生しない。候補を expert rank 昇順に並べ、末尾側（rank が大きい側）を CPU 用に選ぶ。`engine/src/hy4flash/run/hy4_graph.hip.h:430-455`

## 有効になる条件

- HIP の HY4 `Runner` であること。この変数の直接参照は `engine/src/hy4flash/run/hy4_graph.hip.h` に 1 箇所だけあり、CUDA / Metal / SYCL 側の同名読み取りは確認できない。ファイル先頭は HY4 flash HIP forward の実装と記載している。`engine/src/hy4flash/run/hy4_graph.hip.h:1, 641`
- `hyb` が true で、かつ `HY4_PF_STREAM` が未設定または `atoi` の結果が 0 以外であり、`pf_init` が呼ばれること。`hyb` は `g.cpu_mask` が空でないとき CPU expert pool の初期化後に true になる。`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583, 1706-1708`
- CPU resident expert の body が存在して `pf_init` が `maxb == 0` で早期 return せず、さらに prefill streaming の初期化が scratch buffer 不足または pinned bounce ring 割り当て失敗で無効化されず、`pf_build_groups` まで到達すること。後者の失敗時はそれぞれ `prefill streaming disabled: no room for a scratch buffer` または `prefill streaming disabled: cannot allocate ... pinned bounce ring ...` を stderr に出して `pf_init` から戻る。`engine/src/hy4flash/run/hy4_graph.hip.h:545-562, 597-619, 645-646`
- 分割対象 expert は、各層で `tier == 2`、CPU resident、VRAM/vcache 未常駐で、`cpu.view` が body を返す候補に限られる。候補が 8 個以下の層では分割されない。`engine/src/hy4flash/run/hy4_graph.hip.h:430-455`
- forward 時には `pf_active(T)`（`pf_stream` かつ `T >= pf_min_T`）である必要がある。さらに `pf_use_gather(T)` が true の gather 経路では `do_pf_cpu` が false になるため、この割合による CPU split は使われない。分割フラグは gather でない streaming 経路で `cpu.submit` に渡される。`engine/src/hy4flash/run/hy4_graph.hip.h:405-406, 2473-2477, 2573-2602`
- 未設定時の自動値 0.20 は bounce ring と `cpu.n_threads() >= 12` の両方を必要とする。設定値を明示した場合、この自動値の条件は適用されない。`engine/src/hy4flash/run/hy4_graph.hip.h:641-642`

## 実行時の詳細

値は `Runner::pf_init` 中、prefill streaming 用の buffer・stream・event の準備後に読み取られる。初期化時に `pf_build_groups(true)` が CPU 分割対象を各層について決める。以後、vcache version が変わると `pf_build_groups(false)` で group を再構築するが、環境変数を再読込せず保存済みの `pf_cpu_frac` を使う。プロセス実行中に環境値を変更しても、既存 `Runner` の割合は変わらない。`engine/src/hy4flash/run/hy4_graph.hip.h:641-649`

設定値は各層の CPU 常駐 tier-2 候補数に掛け、rank の大きい側を CPU 対象としてフラグ化する。GPU table ではこれらの expert を無効化し、full-layer streaming 時には GPU group 0 を投入した後、選択された CPU 対象 expert を既存の CPU expert pool に投入する。CPU 側の部分和は完了後に GPU 側の `zout_f` に加算される。したがって変数は expert の実行場所と重なり方を変える。token 選択そのものを変える分岐はこの処理にはないが、生成結果の同一性はこのコードだけからは保証できない。`engine/src/hy4flash/run/hy4_graph.hip.h:504-520, 2587-2602, 2614-2630`

## ログと測定値

streaming の初期化に成功すると stderr に `[hybrid] prefill streaming on (...)` が出力され、その中の `cpu_frac=%.2f` に clamp 後または自動設定後の割合が表示される。`pf_build_groups(true)` による初回ログであり、vcache version による再構築時は `log_init=false` のため同じログを繰り返さない。変数の空文字・非数値文字列・clamp に対する専用警告やエラーはない。`engine/src/hy4flash/run/hy4_graph.hip.h:540-543, 645-646`

この commit の `docs/DETAILS.md` および関連する `docs/AMD_HIP.md`、`docs/STRIX_HALO.md`、`docs/SETTINGS.md` には、この変数の動作や測定値の記載を確認できなかった。性能値は記載しない。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:1` — HY4 HIP forward 実装のファイル説明。
- `engine/src/hy4flash/run/hy4_graph.hip.h:416-455` — 候補 expert の抽出、割合条件、CPU split の選定。
- `engine/src/hy4flash/run/hy4_graph.hip.h:504-520` — CPU split 対象を GPU table から外す処理。
- `engine/src/hy4flash/run/hy4_graph.hip.h:540-543` — 初期化ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:545-646` — 初期化、環境値の読み取り・clamp・未設定時の既定値。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583, 1706-1708` — hybrid runner と prefill streaming 初期化の条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2473-2477, 2573-2602, 2614-2630` — streaming/gather 条件、CPU pool 実行、部分和の合流。
