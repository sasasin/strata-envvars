# `STRATA_Q36_PEER_SWAPS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 engine の peer GPU 上に置いた expert slot を、直近の routing count に合わせて一度の rebalance あたり各層何個まで交換するかを指定する。既定値は 4。実際の `peer_rebalance(8)` 呼び出しが上限になるため、この変数を 8 より大きくしても一層あたり 8 回を超えない。交換候補は peer GPU と card 0 のどちらにも載っていない expert、退く候補は peer GPU の slot にある expert で、前者の count が後者を上回る場合に限り slot を入れ替えて host arena から peer arena へ expert blob をコピーする。card 0 の slot は変えない。`engine/src/qwen35/q36_engine.cu:3498-3504,3506-3524,3539-3576`。

この変数は Strata の Qwen3.6 CUDA/HIP engine の調整値で、Strata が環境から直接読み取る。`strata` はモデルの GGUF family が `qwen35moe` の場合に同 engine へ切り替わり、同じ engine は `strata-q36` からも使われる。Metal / SYCL build にはこの GPU engine がなく、HIP gfx906 build では Qwen3.6 engine target が作られない。`engine/src/program/generate.cpp:3799-3814`; `engine/cmake/strata_gpu_engine.cmake:6-8,565-584`。

## 値と判定

`peer_rebalance()` 内の関数ローカル `static` initializer が `std::getenv` で読み、設定されていれば `std::atoi` に渡す。未設定なら 4、負値なら 0 に丸める。数値としての全体検証やエラー通知はなく、`atoi` が変換できる先頭の整数部分を使う。例えば空文字・`true`・`0anything` は 0、`1` は 1、` 2tail` は 2、`-1` は 0。正値は呼び出し側の `max_swaps=8` で一層あたり最大 8 に制限される。`atoi` の整数範囲外の入力はコードで検査されない。`engine/src/qwen35/q36_engine.cu:3512-3522,1881-1884`。

| 条件 | unset | 設定値の扱い | 実効上限・無効値の例 |
|---|---:|---|---|
| peer rebalance が到達する場合 | 4 | `atoi` の結果を使い、負値は 0 | 0 以下は交換しない。正値は一層あたり最大 8。空文字、`true`、`0anything` は 0 |

CLI 引数によるこの値の上書きはない。`--peer-device` は peer tier 自体を設定する別の条件で、交換数の指定ではない。`--peer-device` は Qwen3.6 engine の引数として読み取られ `Engine::peer_device` に渡る。`engine/src/qwen35/q36_engine.cu:5360-5392,5466-5473`。

## 有効になる条件

- `strata` では GGUF の family が `qwen35moe` であり、CUDA/HIP build に Qwen3.6 engine が含まれていること。単独 engine `strata-q36` も対象。`engine/src/program/generate.cpp:3799-3814`; `engine/cmake/strata_gpu_engine.cmake:6-8,565-584`。
- expert が VRAM に全て収まらず hybrid 配置となり、CPU expert pool 付き build（`STRATA_Q36_CPU_POOL`）で実行されること。全 expert が card 0 に収まる場合は hybrid に入らず、peer slot の交換も起きない。hybrid にできない build では expert が収まらないと「`the routed experts (...) do not fit in VRAM, and this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)`」で失敗する。`engine/src/qwen35/q36_engine.cu:4318-4348`。
- `--peer-device N` で N >= 1 の peer GPU tier が有効になり、peer arena、slot 表、compute stream が用意されること。peer compute buffers の割り当てに失敗して `peer.comp` が null の場合は、CPU pool が batch の全 entry を受け持ち、交換関数は戻る。`engine/src/qwen35/q36_engine.cu:4077-4088,4203-4235,4391-4396,3506-3510`。
- `STRATA_Q36_PEER_FIXED` が設定されていると値の内容に関係なく peer 配置を固定し、交換を行わない。空文字も「設定あり」。warmup 中と `rows_deferred` 中も交換をスキップする。`engine/src/qwen35/q36_engine.cu:3510-3512`。
- 各 rebalance の総コピー budget は別変数 `STRATA_Q36_PEER_SWAP_MIB`（unset は 512 MiB）が制限する。budget は blob bytes を交換後に差し引き、候補がある層の処理後に 0 以下ならそこで走査を止める。一層の処理中は budget が 0 以下になっても同層内の `per` 上限まで続く。また、走査開始時に budget が 0 以下でも、候補のない層は `continue` され、最初に候補が見つかった層では交換が実行され得る。従って厳密なコピー量上限ではない。`STRATA_Q36_PEER_SWAPS` はこの budget 値を上書きしない。`engine/src/qwen35/q36_engine.cu:3517-3523,3541-3545,3558-3579`。
- 対象関数は main layers を走査する。peer slot 数が 0 の層、候補がない層、またはどの候補も退く expert より routing count が多くない層では交換されない。`STRATA_Q36_PEER_VS_C0` で card 0 と同じ expert を peer に置く診断経路でも、同じ expert を二重保有する状態には交換しない。`engine/src/qwen35/q36_engine.cu:3531-3563,3470-3472,4387-4396`。

## 実行時の詳細

`after_rows()` は hybrid で確定した decode/verify 行の routing count を加算し、位置 `pos` が 32 の倍数に達したとき card 0 の stream を同期してから `rebalance(8)`、続けて `peer_rebalance(8)` を呼ぶ。通常 decode は生成行を確定した後、speculative decode は採用行を commit した後にこの経路へ来るため、拒否された draft の行で slot を交換しない。warmup 中は `peer_rebalance()` 冒頭で戻る。`engine/src/qwen35/q36_engine.cu:1866-1885,3706-3717,4005-4018,3506-3515`。

`STRATA_Q36_PEER_SWAPS` は最初に関数内 initializer へ到達したときに読み、そのプロセス内では `static` に保持される。`STRATA_Q36_PEER_FIXED` が有効、warmup 中、または rows deferred の呼び出しでは initializer に到達しない。読み取り後に環境を変更しても反映されない。未設定の 4 も、設定値の 0 も、他の CLI 値で置換されない。`STRATA_Q36_PEER_SWAP_MIB` も同関数内の `static` として読み取られる。`engine/src/qwen35/q36_engine.cu:3506-3524`。

各交換では `PeerTier::slot_of` と `exp_in_slot` を更新し、当該層の host expert arena から peer GPU arena の該当 slot へ `cudaMemcpyAsync` を発行する。更新候補は routing count の多い順、退く slot は count の少ない順に選ぶ。layer ごとに独立し、MTP block はこの関数の走査対象ではない。`engine/src/qwen35/q36_engine.cu:3531-3576`。

## ログと測定値

交換が起き、`STRATA_Q36_PEER_SWAP_QUIET` が未設定なら、交換ごとに stderr へ次の形式で出る。quiet 変数は設定有無だけを判定するため、空文字でも交換ごとの行を抑制する。

```text
strata-q36: peer swap L<layer>: expert <in> into slot <slot>, expert <out> out (counts <in-count> vs <out-count>)
```

1 回の rebalance で交換が一つ以上あれば、quiet の設定に関係なく集計行も stderr に出る。

```text
strata-q36: peer tier: <n> swap(s) over <n> layer(s) at position <pos>, <MiB> MiB copied, <total> in all; hits so far <hits> of <entries> entries (<percent>%)
```

候補がない、上限が 0、tier が未設定など交換が 0 件の場合、この関数から交換ログは出ない。`cudaSetDevice(P.device)` に失敗するとエラー状態を消去して無言で戻る。非同期 blob copy など `CK(...)` で包まれた CUDA 呼び出しが失敗すると stderr に `strata-q36: <expression> failed: <CUDA error> (<file>:<line>)` を出して終了コード 1 で終了する。環境変数の parse エラー自体は報告しない。`engine/src/qwen35/q36_engine.cu:3527-3528,3567-3587,82-89`。

この環境変数について、ソースに条件付き測定値はない。

## 根拠

- 値の読み取り、既定値、負値 clamp、呼び出し上限: `engine/src/qwen35/q36_engine.cu:3510-3524,1881-1884`
- peer swap の候補選択・コピー・出力: `engine/src/qwen35/q36_engine.cu:3498-3504,3531-3587`
- hybrid 配置、peer 初期化と失敗時の扱い: `engine/src/qwen35/q36_engine.cu:4077-4088,4203-4235,4318-4348,4387-4396`
- Qwen3.6 family switch と build 対象: `engine/src/program/generate.cpp:3799-3814`; `engine/cmake/strata_gpu_engine.cmake:6-8,565-584`
