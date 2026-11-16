# `STRATA_SYCL_GDN_QK_GRF256`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 版 `gdn_step_norm_multi` の一部条件で、GDN の QK register kernel `gdn_step_norm_qkreg` を選びます。この関数は Q/K の値を subgroup 内で交換して recurrence と出力正規化を実行し、起動 properties に `grf_size<256>` を指定します。環境変数はカーネルの選択を変えますが、CPU 側で値を数値変換したり、通常の GDN と別のモデル構造を選んだりはしません（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:972-1099, 2244-2248, 3026-3058`）。

これは SYCL 実装に限られます。CUDA/HIP の同名読み取りはありません。調査対象の `docs/DETAILS.md` にこの変数の個別説明や性能測定値は見つかりませんでした。

## 値と判定

`gdn_step_norm_multi` 内の関数ローカル `static const bool` 初期化子が `std::getenv` で値を取得し、未設定でないかつ先頭文字が `'1'` かどうかを判定します。文字列全体の比較、数値変換、空白除去はありません（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2244`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| SYCL 版 `verify_kernels.dp.cpp` | 無効 | `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, ` 1`, `2` |

`true` は先頭が `'1'` でないため無効です。大文字小文字や数値としての妥当性は検査せず、先頭 1 文字以降は判定に影響しません。値の検証エラー、無効値時の警告、別の値への fallback はありません。

## 有効になる条件

- SYCL backend の `gdn_step_norm_multi` が呼ばれ、この関数内で環境値の判定まで到達すること。
- 初回にこの分岐へ到達したときの値が有効であること。未設定・空文字なら選択されません。
- `xq_out == nullptr`、`n_keep == nullptr`、`h_k == 16`、`h_v == 48`、`conv_channels == 10240` であること。`n_tok` や `t_out_begin` はこの環境変数側の if 条件には含まれません（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2244-2248`）。
- 直前の `STRATA_GDN_QK_REG` 分岐が先にカーネルを起動して return していないこと。その分岐は `bm_default_on("STRATA_GDN_QK_REG", device, false)` を使い、さらに `t_out_begin == 0` と Battlemage 世代を要求します（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2222-2243`; `sycl/include/strata/sycl_queue.hpp:162-166`）。両方の環境変数が有効でも、先行分岐の条件を満たす呼び出しでは本変数の分岐に進みません。
- モデルや呼び出し側が上記の GDN 寸法・引数条件を満たすこと。`xq_out` が非 null の fused q8_1 出力経路、または `n_keep` を使う commit 経路では本分岐に入りません。

この if 自体は GPU 世代を確認しません。したがって環境値だけで Battlemage 専用には制限されません。選択されたカーネルは SYCL の Intel `grf_size<256>` property を指定しますが、対応可否や実行時の driver の挙動は Strata ソースからは断定できません。

## 実行時の詳細

候補名の完全一致参照は `data/settings-register.json:39951` と `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2244` です。後者だけが実際にプロセス環境から値を読みます。共通 env helper や動的な変数名を介した本変数の読み取りはありません。

値は各プロセスで初めて `gdn_step_norm_multi` の `STRATA_GDN_QK_REG` 分岐を抜けて本判定へ到達したときに読み取られ、`static const bool` に保存されます。関数ローカル static はプロセス内で共有されるため、その後の環境変更は反映されません。先行する `STRATA_GDN_QK_REG` 分岐が成立して return する呼び出しでは、この static 初期化にも到達しません（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2222-2248`）。

有効で条件も満たす場合は `gdn_step_norm_qkreg` を呼び、`grf_size<256>` property つきの SYCL kernel を queue に投入します。カーネルは各 token について Q/K の lane 値を subgroup から選び、GDN state recurrence を更新し、`t_out_begin` 以降の出力を正規化して書きます（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:972-1099, 3026-3058`）。この分岐は直ちに return するため、その呼び出しでは後続の `STRATA_GDN_SPLIT` 分岐や標準 multi kernel に進みません（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2244-2250`）。

呼び出し元には verifier の window と commit の GDN 処理があります。commit 側では `n_keep` を渡すため本変数の分岐条件を満たさず、通常の window 側も `xq_out` や形状により選択可否が決まります（`sycl/src/core/verify.cpp:1230-1232, 2129-2138`）。CLI 引数やサーバー設定による本変数の上書きは見つかりません。

## ログと測定値

本変数によるカーネル選択を知らせる有効ログはありません。専用関数は引数が不正なら stderr に `gdn_step_norm_qkreg: invalid arguments` を出して `exit(1)` します。また `xq_out` が非 null なら `SYCL gdn_step_norm_qkreg: fused q8_1 output is not implemented` という `std::invalid_argument` を投げますが、呼び出し側の分岐条件は `xq_out == nullptr` です（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2245-2248, 3029-3033`）。

この変数に紐づく性能値や精度測定値は、調査した Strata 資料から確認できません。

## 根拠

- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2222-2248` — 先行する `STRATA_GDN_QK_REG` 分岐、本変数の値判定、選択条件と fallback の順序。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:972-1099, 3026-3058` — QK register kernel の計算、GRF256 property、引数検査と queue 投入。
- `sycl/include/strata/sycl_queue.hpp:162-166` — 先行する `STRATA_GDN_QK_REG` の helper 値規則。
- `sycl/src/core/verify.cpp:1230-1232, 2129-2138` — verifier からの window および commit 呼び出し。
- `data/settings-register.json:39951` — 設定台帳の文字列参照（実際の読み取り根拠ではない）。
