# `STRATA_SYCL_DEQUANT_GU_SG`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の IQ gate/up 重みを FP16 に dequantize する経路で、tiled kernel に渡す subgroup 数を選ぶ環境変数。未設定または有効値以外では `1` となり、従来の単一 subgroup kernel を使う。値が `2`、`4`、`8` なら複数 subgroup の tiled kernel に切り替わる。これは kernel 実装の選択であり、Strata のコードから生成値や性能への影響は断定できない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6562-6589,6611-6617,6638-6675`）。

この読み取りは SYCL 版 `iq_dequant_gu_f16` にだけ存在する。通常の prefill で IQ gate/up を FP16 に展開する呼び出し元がある（`sycl/src/prefill/prefill.cpp:4593-4605,4686-4717`）。CPU/CUDA 実装や CLI 引数からこの変数を読む箇所は見つからなかった。

## 値と判定

`dequant_gu_subgroups()` は `std::getenv` の結果を `std::atoi` に渡し、未設定なら `1` とする。変換後の値が `2`、`4`、`8` の場合だけその値を返し、それ以外は `1` に戻す（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の通常 IQ gate/up dequant 経路で、この変数の判定まで到達 | `1`（単一 subgroup kernel） | `atoi` の結果が `2`、`4`、`8`。例: `2`, `4`, `8`, `+2`, `02`, `2tail` | `atoi` の結果が上記以外なら `1`。例: 空文字、`0`, `1`, `3`, `-2`, `true`, `false`, `word` |

これは厳密な文字列比較や全体 parse ではない。`atoi` が読む整数接頭部で判定されるため、先頭空白や符号を含む文字列も整数接頭部が有効値なら受理され、後続文字は判定に使われない（例: `  +4suffix` は `4`）。整数接頭部がない文字列は `0` となり、fallback の `1` を使う。設定値が数値として妥当かを別途検査するコードはない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6613-6616`）。

## 有効になる条件

- SYCL build に含まれる `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の実装を実行すること。CMake は CUDA カーネル一覧の `iq_kernels` を解決し、SYCL 用 migrated source を `strata_kernels` に含める（`sycl/CMakeLists.txt:4-7,240-253`）。
- `iq_dequant_gu_f16` が呼ばれ、入力検査を通ること。`n_embd` が 256 の倍数で IQ type であり、`tail == nullptr` が必要（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6643`）。
- `STRATA_SYCL_DEQUANT_GU_BOUNDED` による bounded 経路が有効な入力を処理して先に return しないこと。bounded が有効で IQ type 16/22/29 と bounded 関数の shape 条件を満たすと、その経路が先に実行され、この変数は読まれない。ほかの入力では bounded 関数が false を返すか bounded が無効で、subgroup 判定に進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558,6643-6649`）。
- subgroup 判定が `1` の場合はこの値だけで別機能は有効にならない。`2/4/8` の場合 tiled kernel を使い、`STRATA_SYCL_DEQUANT_GU_STATIC_TYPE` と `STRATA_SYCL_DEQUANT_GU_STATIC_ROW` がそれぞれ静的 type/row dispatch を選ぶ。row dispatch は `n_embd == 2560` かつ type 16/22/29 の分岐に限られ、どちらの設定も subgroup が `1` のときは読み取られない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6592-6609,6645-6649`）。
- Tiled 経路は `n_ff > 0`, `n_embd > 0`, `n_embd % 256 == 0`, IQ type を追加で要求し、違反時は stderr に `iq_dequant_gu_f16_tiled: invalid type or shape` を出して `exit(1)` する。また device の fp16 capability を要求する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6621-6628`）。
- `sycl/serve/strata-sycl.sh` は親環境から `STRATA_SYCL_*` を wrapper 自身の設定として除外するため、この launcher 経由ではこの変数をコンテナへ転送しない。直接起動など launcher 外で環境を渡す場合とは異なる（`sycl/serve/strata-sycl.sh:33-42,46-52`）。

CLI 引数、設定ファイル値、別の環境変数が `STRATA_SYCL_DEQUANT_GU_SG` を上書きする Strata 側の処理は確認できなかった。bounded 経路の選択は `STRATA_SYCL_DEQUANT_GU_BOUNDED` が関係する。

## 実行時の詳細

入力検査後、`iq_dequant_gu_f16` は bounded 経路を試し、そこで処理されなかった場合に `dequant_gu_subgroups()` を呼ぶ。`2/4/8` なら tiled kernel を dispatch し、各 subgroup が gate/up の block を担当する。`1` なら既存の `dequant_gu_kernel` を起動する。どちらも gate と up を FP16 出力へ展開する処理で、コード上はこの設定による別の値選択や再量子化を行わない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6562-6589,6611-6617,6638-6675`）。

値は `dequant_gu_subgroups()` 内の関数ローカル `static const int` として初回評価時にキャッシュされる。bounded が入力を処理した場合は同関数が呼ばれず、設定を読み取らない。判定後のプロセス環境変更はキャッシュ値に反映されない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617,6643-6649`）。

## ログと測定値

この環境変数の値や選択した subgroup 数を報告するログは確認できなかった。tiled 経路の不正 shape/type は `iq_dequant_gu_f16_tiled: invalid type or shape` を stderr に出して終了し、不正な subgroup 数を関数へ直接渡した場合は `iq_dequant_gu_f16_tiled: subgroups must be 2, 4 or 8` を出して終了する。ただし環境変数からは値を `1/2/4/8` に正規化して渡すため、後者は通常この変数だけでは発生しない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6624-6634`）。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617` — 環境読み取り、変換、受理値、既定値、static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6592-6609,6621-6635,6638-6675` — tiled/通常経路、実行条件、失敗時の出力。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558,6643-6649` — bounded 経路と関連環境変数。
- `sycl/src/prefill/prefill.cpp:4593-4605,4686-4717` — prefill の gate/up dequant 呼び出し。
- `sycl/serve/strata-sycl.sh:33-42,46-52` — SYCL launcher の環境変数転送条件。
- `sycl/CMakeLists.txt:4-7,240-253` — CUDA カーネル一覧と SYCL migrated source の解決・組み込み。
