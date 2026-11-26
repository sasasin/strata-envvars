# `STRATA_GDN_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

GDN の複数 token 計算で、従来の 1 head あたり 1 block の kernel の代わりに、head の state 列を 4 block に分ける split kernel を選ぶ。CUDA/HIP 実装では `gdn_step_norm_multi`、SYCL 実装でも同名の処理が対象である。split 時は state replay または split step kernel と、出力がある場合の別 norm kernel を起動する。1 token 分しか出力しない呼び出しなど、適用条件を満たさない場合は従来 kernel に進む。`gdn_commit_layers` ではこの変数が per-layer 経路を要求し、複数 layer を一括 commit する実装を使わない。`STRATA_GDN_SPLIT` 自体は演算結果の値や出力 token 数を指定しない。`engine/src/kernels/cuda/verify_kernels.cu:1320-1351`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2251-2304`、`engine/src/kernels/cuda/verify_kernels.cu:1231-1252`。

## 値と判定

各 kernel の関数内 `static const bool` 初期化時に `std::getenv` で読み、値全体の parse はせず `v[0] == '1'` のみを見る。unset、空文字、または先頭が `1` 以外なら split は無効。`1`、`10`、`1anything` は有効であり、`0`、`0anything`、`true`、` 1`、大文字小文字違いの文字列は無効。空白除去・数値変換・範囲検証はしない。`engine/src/kernels/cuda/verify_kernels.cu:1326`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2251`。

| 設定・経路 | unset | split が有効になる値 | split が無効になる値 |
|---|---|---|---|
| CUDA/HIP `gdn_step_norm_multi`、SYCL 同関数 | 無効（ただし起動時のアーキテクチャ既定が先に値を設定する場合がある） | 先頭文字 `1` | 空文字、先頭文字が `1` 以外 |
| CUDA/HIP `gdn_commit_layers` | batch commit を試行可能（他条件も必要） | 先頭文字 `1` で per-layer を選び、batch commit を拒否 | unset・空文字・先頭が `1` 以外なら、この変数による拒否なし |

環境に値があるかどうかと、split 判定は別である。起動時の既定設定処理は既存値を値にかかわらず保持するため、例えばユーザー設定の空文字や `0` は自動で `1` に置き換えられない。`engine/src/core/nv_defaults.cpp:222-239`、`engine/src/core/arch_defaults.cpp:302-323`。

## 有効になる条件

- `gdn_step_norm_multi` では `split` が真で、かつ `t_out_begin >= n_tok`（state のみを commit）または `n_tok - t_out_begin >= 2` のとき split kernel に進む。条件外は通常 kernel を使う。`n_tok` は split 時 `kVerifyMaxT` を超えると `gdn_step_norm_multi: invalid arguments` を stderr に出して `exit(1)` する。`engine/src/kernels/cuda/verify_kernels.cu:1327-1351`。
- 環境変数が `1` でも、該当する GDN 処理が実行されなければ効果はない。CUDA/HIP と SYCL には別々の読み取り箇所があり、各実装の static 判定を初期化する前に環境が設定されている必要がある。関数内 static は一度初期化すると再読込しない。実行中に環境を変えても、その判定には反映されない。`engine/src/kernels/cuda/verify_kernels.cu:1235-1239,1326`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2251`。
- CUDA/HIP の `gdn_commit_layers` は `STRATA_GDN_SPLIT` の先頭が `1`、または `STRATA_GDN_COMMIT_SPLIT` の先頭が `0`、または `STRATA_DBG_GDN` の先頭が `1` なら `false` を返して batch commit kernel を起動しない。ほかに `n_layers`、`n_max`、`n_keep`、head 数の妥当性検査も通る必要がある。`engine/src/kernels/cuda/verify_kernels.cu:1231-1252`。
- CUDA 検証 commit の一括 GDN commit は `STRATA_COMMIT_BATCH` が unset または先頭が `0` 以外の場合に試みられる。`STRATA_COMMIT_BATCH=0` などで一括 commit が無効になり、commit 窓が `kVerifyMaxT` より大きいと per-layer fallback は失敗し、`verify commit: windows past ... tokens (--lookup-max-t) need the batched GDN commit (unset STRATA_COMMIT_BATCH=0, STRATA_GDN_SPLIT, STRATA_GDN_COMMIT_SPLIT=0)` を `err` に設定して commit を失敗させる。`engine/src/core/verify.cpp:3445-3452,3502-3520`。
- 通常の CUDA 同一 compute capability 構成では、sm_70 (Volta) の自動既定値テーブルが `STRATA_GDN_SPLIT=1` を設定する。`STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` は sm_70 テーブルを無効化する。全 CUDA device の compute capability が一致する場合だけ `apply_nv_defaults` を呼ぶ。既に変数が設定済みなら、空文字や `0` も含めてユーザー値が優先される。`engine/src/core/nv_defaults.cpp:136-163,222-239`、`engine/src/program/generate.cpp:4425-4449`。
- AMD では `apply_arch_defaults` による自動設定がある。`gfx1151` には GDN split が既定テーブルに含まれ、`STRATA_GFX1151_DEFAULTS=0` でテーブルを止める。離散 RDNA3 `gfx1100/1101/1102` でも `gfx11_discrete_exact_env` が設定し、統合 GPU ではなく、`STRATA_GFX11_DEFAULTS=0` または `STRATA_DEFAULTS=026` で無効化される。これらも既に値がある場合は上書きしない。`engine/src/core/arch_defaults.cpp:28-66,302-323`、`engine/include/strata/core/gfx11_extra.hpp:27-46,61-73`。
- `generate` の lookup 窓が build の `kVerifyMaxT` より大きい場合、環境値の先頭が `1` で、sm_70 テーブル由来の既定値なら、Strata は変数を環境から削除（Windows は空文字設定）して既定 split を取り下げ、lookup 窓を維持する。ユーザー指定なら変数を保持して窓を `kVerifyMaxT` に clamp する。どちらの場合も対応する stderr 警告を出し、ここでは終了しない。`engine/src/program/generate.cpp:5056-5077`。

## 実行時の詳細

CUDA/HIP kernel では `gdn_step_norm_multi` が関数内 static に値を cache する。split の state-only 経路は `gdn_state_replay_kernel`、出力経路は `gdn_step_split_kernel` の後に `gdn_out_norm_kernel` を使う。split step の state recurrence は列方向を 32 列ずつの 4 block に分ける実装である。`engine/src/kernels/cuda/verify_kernels.cu:1320-1351`、`engine/src/kernels/cuda/verify_kernels.cu:418-429,510-553`。

CUDA/HIP の `gdn_commit_layers` も初回呼び出し時に `STRATA_GDN_SPLIT` を他の二変数とともに static cache する。無効条件なら `false` を返し、呼び出し側の per-layer commit loop に任せる。`Verifier::commit` は batch commit が成功した場合に一括経路を使い、それ以外は各 GDN layer の convolution commit と `gdn_step_norm_multi` を呼ぶ。`engine/src/kernels/cuda/verify_kernels.cu:1231-1252`、`engine/src/core/verify.cpp:3453-3470,3498-3521`。

起動時の自動既定値は engine が switch を読む前に適用される。CUDA の NVIDIA default は全可視 device が同じ compute capability のときに限り適用される。AMD default は `generate` から `apply_arch_defaults` を呼ぶ経路で設定される。自動 default が追加されたときは NVIDIA では `strata: ... speed switches on by default ...` の行に、AMD gfx11 discrete では `strata: gfx11 (RDNA3): ... exact speed switches on by default ...` の行に変数名が含まれる。ユーザー値が維持された場合や該当テーブルが空の場合、この追加ログは出ない。`engine/src/program/generate.cpp:4320,4425-4449`、`engine/src/core/nv_defaults.cpp:222-255`、`engine/src/core/arch_defaults.cpp:302-332`。

## ログと測定値

lookup 窓が build の上限より大きい場合の警告文字列は、既定値を外す経路で `strata generate: STRATA_GDN_SPLIT=1 (the sm_70 default) is dropped: ...`、ユーザー値を保持して clamp する経路で `strata generate: STRATA_GDN_SPLIT=1 holds %d rows per window: ...`。split 経路の引数不正は `gdn_step_norm_multi: invalid arguments` を stderr に出し、プロセスを `exit(1)` する。`engine/src/program/generate.cpp:5070-5076`、`engine/src/kernels/cuda/verify_kernels.cu:1327-1330`。

この文書では性能値を記載しない。リポジトリ資料には特定機種・条件の測定記述があるが、ここでは環境変数の値から一般化した性能を述べない。

## 根拠

- `engine/src/kernels/cuda/verify_kernels.cu:1231-1252,1320-1351`
- `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2251-2304`
- `engine/src/core/verify.cpp:3445-3452,3502-3521`
- `engine/src/program/generate.cpp:4425-4449,5056-5077`
- `engine/src/core/nv_defaults.cpp:136-163,222-255`
- `engine/src/core/arch_defaults.cpp:28-66,302-332`
- `engine/include/strata/core/gfx11_extra.hpp:27-46,61-73`
