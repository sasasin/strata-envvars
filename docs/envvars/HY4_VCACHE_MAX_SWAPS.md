# `HY4_VCACHE_MAX_SWAPS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の HY4 実行経路にある適応型 VRAM expert cache について、decode 中に一度のレイヤー更新で昇格候補として扱う expert 数の上限を設定する。通常は 8、VRAM に置かれた expert と動的 cache slot の合計が 3,148 未満の場合は 2 が既定値で、環境変数があればその値で上書きする。実際の昇格数は候補の有無、cache slot、転送中 slot、スコア条件などにも制限されるため、この値は実行される swap 数を保証しない。`engine/src/hy4flash/run/hy4_graph.hip.h:701-731,865-875,912-965`

## 値と判定

`vcache_init()` で `getenv("HY4_VCACHE_MAX_SWAPS")` が非 NULL かだけを確認し、設定されていれば `atoi` で整数化した値を `[0, 32]` に clamp する。未設定なら既定値が残る。空文字は「設定あり」として `atoi("") == 0` になり、0 に設定される。`atoi` は先頭の空白と符号を許し、10進数として読める先頭部分を使うため、例では `" 3tail"` は 3、`"0tail"`・`"true"`・空文字は 0、`"-1"` は clamp 後 0、`"33"` は 32 となる。文字列全体の妥当性、大文字小文字、後続文字は検査しない。`atoi` の整数範囲を超える入力の結果は保証されない。`engine/src/hy4flash/run/hy4_graph.hip.h:705-731`

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・変換される値 |
|---|---|---|---|
| 適応 cache 初期化まで到達する HIP hybrid 実行 | 通常 8。`g.n_vram_experts + vcache_nslots < 3148` なら 2 | `0`〜`32`。`"3tail"` は 3、`" 3"` は 3 | 空文字・`"true"`・`"0tail"` は 0、負数は 0、33 以上は 32 に clamp |

`--spec-check` / `--parity-m` は cache を後から freeze しますが、この環境変数の初期化時の読み取りや初期値の設定を置き換えません。別の CLI 引数による上書きはこの実装にはありません。`engine/src/hy4flash/run/hy4_graph.hip.h:714,717-731`; `engine/src/hy4flash/run/hy4_main.hip.cpp:821-825,916`

## 有効になる条件

- 対象は `engine/src/hy4flash/run/hy4_graph.hip.h` の HIP 実装です。リポジトリ全体の完全一致検索では、値を読む箇所はこの一箇所でした。他 backend に同名の読み取りは見つかりません。
- runner が hybrid であること。ソースでは `g.cpu_mask` が空でないと CPU expert runtime を初期化して `hyb = true` にします。`vcache_init()` は `hyb` が真でも、`g.vcache_nslots <= 0` または slot byte 数が 0 なら環境変数を読む前に戻ります。`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583,717-724`
- 動的 slot 数は、単一 GPU・CPU expert mode・`dyn_frac > 0.01`・`HY4_RESERVE_GB` による VRAM 余力の確保や VRAM 確保失敗によって実際の slot 数が減るか 0 になることもあります。従って環境変数が設定されていても、slot がない場合は効果がありません。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1073-1083,1124-1143,1159-1171`
- decode 中は `vcache_frozen` が真なら `vcache_note_decode()` が昇格処理をせずに戻ります。`--spec-check` / `--parity-m` 経路では呼び出し元が cache を freeze します。`engine/src/hy4flash/run/hy4_graph.hip.h:714,903-904`; `engine/src/hy4flash/run/hy4_main.hip.cpp:821-825,916`

## 実行時の詳細

環境変数は runner の初期化中、`hyb` のときに呼ぶ `vcache_init()` で一度読み取られ、整数メンバー `vcache_max_swaps` に保存される。リクエストごとの再読込や、この値の static cache はないため、同じ runner の実行中に環境を変更しても値は更新されない。`engine/src/hy4flash/run/hy4_graph.hip.h:717-732,1704-1708`

値は decode の各レイヤーで呼ばれる `vcache_note_decode()` の候補配列幅 `max_c` を決める。通常は `vcache_max_swaps`、最初の 32 cache step の warmup 中は `max(vcache_max_swaps, 32)` が使われ、どちらも 32 を上限とする。したがって設定値 0 でも warmup 中の候補幅は 32 で、その後は候補幅 0 となり昇格処理を行わない。warmup 判定は `vcache_steps < 32` で、decode 対象が 8 token 以下の場合に cache step が進む。`engine/src/hy4flash/run/hy4_graph.hip.h:865-875,903,1009-1018,3384-3389`

候補幅は実際の swap 数ではない。候補は tier-2 で VRAM に未配置の expert かつ host RAM に resident であるものに絞られ、score が victim より所定比率で高いこと、空き ring slot、slot に収まる body なども必要になる。host-to-device 転送は warmup 中最大 8、通常最大 4 の制限を別に持つ一方、scratch 上の expert は device-to-device 経路で候補になり得る。`engine/src/hy4flash/run/hy4_graph.hip.h:885-900,912-927,953-1005`

この環境変数は prefill 終了時の `vcache_rebalance_prefill()` の上限には使われない。同関数は別途 `max(128, (vcache_nslots * 3) / 4)` などで swap 数を決める。`engine/src/hy4flash/run/hy4_graph.hip.h:803-829,3444`

## ログと測定値

初期化後、`[vcache] pre-populated ... max_swaps=%d` のログに、clamp 後の `vcache_max_swaps` が出力される。このログは hybrid かつ動的 slot があり、初期化が途中で戻らず pre-populate 処理まで進んだ場合に出る。decode / session の `[vcache] ... promotions` ログは hit/miss が記録されるなどの別条件で出るが、表示する promotions は実際の昇格数であり、設定値そのものではない。変数固有の無効値警告やエラー処理はない。`engine/src/hy4flash/run/hy4_graph.hip.h:717-779`; `engine/src/hy4flash/run/hy4_main.hip.cpp:1084-1088,1110-1114`

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:692-731` — cache 状態、既定値、小容量時の既定値、環境変数の読み取りと clamp。
- `engine/src/hy4flash/run/hy4_graph.hip.h:865-1005` — warmup 候補数、昇格候補の制約と転送経路。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1009-1018,1552-1583,1704-1708` — step 更新、hybrid 判定、初期化の時期。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1073-1083,1124-1143,1159-1171` — 動的 cache slot の割当条件と失敗時の扱い。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:821-825,916,1084-1088,1110-1114` — freeze 経路と観測ログ。
