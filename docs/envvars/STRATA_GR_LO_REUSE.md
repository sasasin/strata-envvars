# `STRATA_GR_LO_REUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 fused hyper-connection（GR）read で、down projection の分割和を reduce するときに、low-rank 値を平均して SiLU を適用した結果を `lo` バッファへ先に書きます。後続の up kernel はその値を再計算せず読み込みます。対象箇所は `fused_gr_read_multi` 内の選択と `gr_down_reduce_kernel<..., true>`、`gr_up_multi_kernel<..., ..., ..., true>` です。計算式は reduce 時に `x / HC` の SiLU、通常の up kernel では down partial の和を `HC` で割った後の SiLU です（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:776-806,880-895,3301-3314,3392-3410`）。

この変数は fused GR kernel が実際に使われるときだけ参照されます。SYCL build は `fused_gr.dp.cpp` を kernel target に含めます（`engine/sycl/CMakeLists.txt:38-47`）。generate 経路では `gr_native_mmvf` が有効であることが前提で、CLI の `--gr-native-mmvf` または `--native` の処理がこれを有効にします。さらに `--no-fused-gr`、GPU stage、layer/half dump、stage timing が指定されていない必要があります（`engine/sycl/src/program/generate.cpp:1952,2209,2587-2595,3221-3228`）。モデル形状も `fused_gr_supported` の `N/HC/LR` と一致する必要があります（`engine/sycl/src/core/layer.cpp:1558-1559`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`）。

## 値と判定

`strata::bm_default_on` が `std::getenv` で取得し、値が非空なら先頭 1 文字だけを判定します。先頭が `0` なら OFF、それ以外の文字なら ON です。文字列全体の parse、数値範囲検査、大文字小文字変換はありません。したがって `1`, `true`, `false`, ` 0`, `00`, `0anything` はそれぞれ ON, ON, ON, ON, OFF, OFF です。空文字は「明示 OFF」ではなく未設定と同じ default 判定です（`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_GR_LO_REUSE` の値判定 | Battlemage なら ON、それ以外は OFF | 非空で先頭が `0` 以外（`1`, `true`, `false`, 空白で始まる値など） | 非空で先頭が `0`（`0`, `00`, `0anything`） |
| 空文字 | Battlemage なら ON、それ以外は OFF | 該当なし（空文字自体は ON 指定ではない） | 該当なし（空文字自体は OFF 指定ではない） |
| 値判定後の kernel 適用 | 下記「有効になる条件」を満たす場合のみ | Battlemage で値判定が ON | いずれかの適用条件を欠く場合は再利用されない |

helper は非空値があれば GPU 世代に関係なくその ON/OFF を返します。しかし GR reuse の適用分岐自体が Battlemage を要求するため、他世代で `=1` にしてもこの経路は有効になりません（`engine/sycl/include/strata/sycl_queue.hpp:196-200`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3302-3306`）。

## 有効になる条件

- 実行が SYCL の fused GR 経路に到達すること。`gr_native_mmvf` は `--gr-native-mmvf` か `--native` の処理で有効になります。`--no-fused-gr`、GPU stages、dump、stage timing は fused 経路を止めます。環境変数はこれらの CLI 条件を上書きしません（`engine/sycl/src/program/generate.cpp:1952,2209,2587-2595,3221-3228`）。
- 実行デバイスが `IntelGpuGen::Battlemage` と認識されること。値 `1` はこのデバイス条件を上書きしません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3303-3306`）。
- reuse 適用分岐の他条件をすべて満たすこと: `cached_norm` が false、`gf_enabled` が false、`gr_norm_split()` と `gr_down_sliced()` が true、`gr_more_groups()`、`gr_large_grf()`、`gr_up_ilp()` が false、`gr_up_cols() == UPM_COLS`、そして `gr_reuse_safe(...)` が true（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3306`）。関連する設定は `STRATA_GR_MORE_GROUPS`、`STRATA_GR_LARGE_GRF`、`STRATA_GR_UP_ILP`、`STRATA_GR_UP_COLS` です。Battlemage では最初の 2 つの既定は false、`STRATA_GR_UP_ILP` は未設定なら false、`STRATA_GR_UP_COLS` は既定 16 です。more-groups / large-GRF を有効にする値や up-ILP の先頭文字 `1`、また up-cols を 4/8/32/64 にすると条件を満たしません（同 `:811-832,1200-1210`）。
- `gr_norm_split()` と `gr_down_sliced()` は既定で true ですが、`STRATA_GR_NORM_SPLIT=0` または `STRATA_GR_DOWN_SLICED=0` で false にできます（後者は `atoi` 判定）（同 `:574-576,834-836`）。`gr_reuse_safe` は `xn` と GR tensor/buffer 群との重なり、および token 間の `lo` 領域の重なりを検査し、安全でない場合に false を返します（同 `:304-326`）。
- private GR F32 経路が `STRATA_PRIVATE_GR_F32_REG` の非ゼロ値で有効になる場合、reuse 適用条件の `!gf_enabled` によりこの分岐を使いません（同 `:2685-2689,3303-3306`）。`cached_norm` は `STRATA_SYCL_GR_CACHED_NORM=3`、`STRATA_SYCL_GR_NORM_BOUNDS` の先頭 `1`、split norm/down sliced、および `gr_cached_norm_safe` がそろう場合に有効となり、この場合も `!cached_norm` 条件で対象分岐は使いません（同 `:76-79,569-576,3298-3306`）。
- `STRATA_SYCL_GR_LO_ONCE` が非ゼロなら、別の reduce/up 経路が先に選ばれ、対象変数の cached-lo reduce specialization は呼ばれません。ただしこの経路も reduce で `lo` を作り、up に渡すため、low-rank 値の再利用自体は起こります（同 `:1149-1158,3359-3360,3388-3410,3485-3487`）。

## 実行時の詳細

`reuse_lo` は `fused_gr_read_multi` 内の関数ローカル `static const bool` です。プロセス中で最初にこの初期化へ到達したときに helper を呼び、その後の呼び出しでは値を再利用します。従って初回読み取り後に環境を変更しても反映されず、異なる GPU を同一プロセスで使う場合も helper の世代判定は初回のデバイスで固定されます（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3160,3301-3303`）。CLI から値を上書きする個別引数はありません。この読み取り箇所にサーバーモード固有の条件や別の build macro gate はありません。サーバーから呼ばれる場合も fused SYCL GR 経路・GPU 条件が必要です。

有効時、分割 down reduce は各 `r < LR` の行について部分和 `x` を `HC` で割って SiLU を適用し、結果を `GR_PICK(m, k, lo)[r]` へ保存します。reduce の起動分岐では既定の非 ILP `gr_down_reduce_kernel<false, true>` が選ばれます。続く up kernel は reuse specialization を選び、`m.cached_lo` が true なら `lo` から値をロードして通常の partial 和・除算・SiLU 計算を飛ばします（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:798-805,1213-1224,3392-3410`）。

有効時の案内ログは static 初期化で一度だけ stderr に出ます。適用条件を満たさない場合、対象変数に固有の警告や理由ログはなく、既存の通常 reduce/up kernel 経路が選ばれます（同 `:3303-3314,3392-3410`）。この変数固有の終了・timeout 経路はありません。fused GR 入力不正時には環境変数とは無関係に `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を stderr に出して `exit(1)` します（同 `:3142-3155`）。

## ログと測定値

適用分岐に入ると stderr に次の形式で出ます。`normalized activation` は `STRATA_GR_CACHED_NORM` の結果であり、`low-rank SiLU` がこの文書の変数の結果です。

```text
strata: GR reuse enabled: normalized activation %d, low-rank SiLU %d
```

ログはこの reuse 分岐に入ったときだけ出て、条件不足で無効になった理由を出すログはありません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3303-3314`）。`docs/INTEL.md` は Battlemage 既定と対応 layout を要約しています。また性能値は 2 枚の Arc Pro B65 で複数の PR #4185 runtime controls をまとめた比較であり、この変数単独の測定としては扱えないため、ここでは個別性能値を記載しません（`docs/INTEL.md:582-612`）。`docs/DETAILS.md` にこの変数の個別説明はありません。

## 根拠

- helper の値判定と Battlemage default: `engine/sycl/include/strata/sycl_queue.hpp:193-200`
- 変数の読み取り、適用条件、状態設定、ログ: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3314`
- down reduce における low-rank SiLU の計算と保存: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:776-806,3392-3410`
- up kernel の cached value 読み出し: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:867-895,1213-1224`
- fused GR の CLI/runtime gate と対応形状: `engine/sycl/src/program/generate.cpp:1952,2209,2587-2595,3221-3228`; `engine/sycl/src/core/layer.cpp:1558-1559`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`
- 一覧文書との照合: `docs/INTEL.md:582-612`; `docs/DETAILS.md` にこの変数の記述なし。
