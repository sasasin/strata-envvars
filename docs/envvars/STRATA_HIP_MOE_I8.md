# `STRATA_HIP_MOE_I8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の Inkling2 backend が grouped MoE の gate/up および down 投影で INT8 WMMA カーネルを選ぶかを制御する。未設定時は RDNA4 だけで有効になる。値を設定すると GPU 世代による既定値を上書きする。環境変数は backend の初期化時に読む（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-565,719-723`）。

## 値と判定

`InkHipBackend::init()` で `getenv` が null かを見て、設定されている場合は `std::atoi(ev) != 0` を保存する。文字列全体の検証、空白除去、範囲制限、無効値の警告はない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:719-723`）。

| 条件 | unset | INT8 WMMA を有効にする値 | 無効にする値 |
|---|---|---|---|
| HIP backend の初期化時 | `mem_info_.gen == AmdGen::Rdna4` のとき有効、それ以外は無効 | `atoi` 結果が非ゼロ。例: `1`, `-1`, `1abc` | `atoi` 結果がゼロ。例: 空文字、`0`, `-0`, `0anything`, `true`, 数字で始まらない文字列 |

`atoi` は先頭の空白と符号の後の数字を読み、数字列の後ろは判定しない。したがって `1.5` も有効、` 0x1` は先頭の `0` を読んで無効となる。変換可能な整数の大きさに対する Strata 独自の境界チェックはない。`atoi` が `int` の範囲外となる入力の結果は、このコードでは規定していない。

## 有効になる条件

- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp` の Inkling2 HIP backend を実行し、その `init()` が成功すること。backend 初期化は HIP デバイス確認後に行われる（同ファイル `:554-585`）。
- `use_i8_moe_wmma_` が真であることに加え、MoE の `layer_all_gpu_[ip]` grouped 経路に入り、GPU 世代が RDNA2 でも `Unknown` でもなく、バッチ `B >= 64` であること。`B < 64` の grouped 経路は `small_i8 = false` として FP16 WMMA を選ぶ（同ファイル `:3946-3965,4030-4058`）。
- `B <= 4` の direct MoE 経路や、条件を満たす hipBLASLt MoE 経路が先に選ばれた場合、このフラグによる grouped INT8 選択は行われない。hipBLASLt 経路は `layer_all_gpu_`、`B >= blaslt_moe_min_b_`、runner ready、作業バッファの確保、`!use_graph` を条件とする。既定の `blaslt_moe_min_b_` は `999999` で、`STRATA_HIPBLASLT_MOE_MIN_B` の別設定で変わる（同ファイル `:712-729,3880-3904`）。
- gate/up は `layer_gu_class_[ip]` が 0 または 1、down は `layer_dn_class_[ip]` が 0 または 1 のときに、このフラグを使う INT8 カーネル分岐へ入る。その他のクラスは FP16 WMMA 側へ進む（同ファイル `:3977-4003,4004-4028`）。
- GPU 世代の既定値は `query_device_memory()` が HIP の `gcnArchName` を `classify_amd_gen()` に渡して決める。分類上 RDNA4 は `gfx1200` / `gfx1201`（同ファイル `:61-70`、`engine/include/strata/hip_uma_guard.hpp:29-51`）。環境値による上書きは RDNA4 以外でも行われるが、上記 grouped 経路以外では効果がなく、コードはこの環境値に追加の世代適合性チェックをしていない。
- CLI 引数による同設定の上書きは見つからない。ここで扱うのは MoE expert の grouped 実行時の選択であり、他の MoE 経路のカーネル選択を一括して変更しない。

## 実行時の詳細

初期化ではまず `use_i8_moe_wmma_` を RDNA4 判定で設定し、環境変数が存在すれば `atoi` の非ゼロ判定で置き換える。空文字も「設定あり」なので `atoi("") == 0` 相当となり、無効側へ上書きする（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:719-723`）。この読み取りは関数ローカル `static` ではなく backend メンバーへの代入であり、推論ごとには読み直さない。同じ backend の再初期化では `init()` が再度実行されるため、その時点の環境値が反映される。プロセス実行中の環境変更は既に初期化済みの backend には反映されない。

対象 grouped MoE 経路では、gate/up 側で入力 `mlpin` を q8 に量子化して該当する `_i8_128` WMMA カーネルを実行し、down 側でも中間活性 `d_act` を q8 にして対応する `_i8_128` カーネルを実行する。フラグが無効、または量子化クラスが対象外なら FP16 変換／WMMA 分岐を使う。両方の結果は同じ後続の `k_moe_reduce_buckets` に渡される（同ファイル `:3972-4028,4067-4068`）。

HIP Graph が有効な場合、初回は通常の処理経路を capture し、以後 graph hit では保存済み graph を launch する。この環境値を graph hit ごとに再評価する処理はない（同ファイル `:3230-3245,3260-3285`）。

## ログと測定値

この環境変数の値、既定値、または選択された INT8/FP16 分岐を知らせる専用ログ・警告は読み取り箇所と選択箇所にない。HIP エラーが起きた場合にこの切替固有のエラー文言や fallback があることも確認できない。参照資料に本変数についての条件付き測定値は見つからなかったため、性能や数値差は記載しない。

## 根拠

- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-585` — backend 初期化と HIP デバイス確認。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:61-70`、`engine/include/strata/hip_uma_guard.hpp:29-51` — GPU 世代の取得と分類。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:712-729` — 関連する hipBLASLt MoE 設定、環境変数の読み取り、GPU 世代による既定値。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3880-3904,3946-4068` — MoE 実行経路、INT8 / FP16 grouped カーネル選択と集約。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3230-3285` — graph capture と graph hit。
