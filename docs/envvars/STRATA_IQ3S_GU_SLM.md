# `STRATA_IQ3S_GU_SLM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL エンジンの native IQ3_S gate/up 計算で、入力 activation を work-group の local memory にまとめて読み込み、その値を IQ3_S の gate/up dot 計算に使う専用 kernel を選びます。対象は `L.n_embd == 2560` かつ `L.n_ff == 640` のレイアウトです。環境変数を読む箇所は `launch_gu<21>()` のみで、CUDA/HIP の通常実装や Python サーバー側からは読みません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4980-5012`）。

## 値と判定

`strata::bm_default_on(name, device, false)` が値を判定します。環境値が空でなければ先頭文字だけを見て、`'0'` なら無効、それ以外なら有効です。空文字は未設定と同じ扱いになり、この呼び出しでは既定値 `false` になります。文字列全体の parse、数値変換、大文字小文字の変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（helper はデバイス既定に戻るが、この変数の既定値は `false`） |
| `0` または `0...` | 無効 |
| `1`、`true`、`false`、空白で始まる値など、空でなく先頭が `0` 以外 | 有効 |

無効な文字列としての拒否や警告はありません。設定値が `false` でも先頭が `f` のため有効になります。根拠: `sycl/include/strata/sycl_queue.hpp:162-166`。

## 有効になる条件

値判定が有効で、さらに次の条件を満たすと専用 kernel を選びます。

- IQ3_S（`L.gu_type == 21`）の gate/up 経路である。
- 旧 IQ kernel が無効（`g_old_kernels == false`）。
- `L.n_embd == 2560` かつ `L.n_ff == 640`。
- `STRATA_IQ3S_GU_ROW_REUSE` の先行分岐が kernel を選んでいない。

`STRATA_IQ3S_GU_ROW_REUSE` は Battlemage では既定有効で、同じ IQ3_S のレイアウト、8 lane、旧 kernel 無効、`STRATA_EXPERT_SPLIT` 無効の条件がそろうと先に row reuse kernel を起動して戻ります。そのため、この経路では `STRATA_IQ3S_GU_SLM` は読まれる前に到達不能です。row reuse を無効化するには同変数を `0` で始まる非空値にします。row reuse が既定無効のデバイスではこの先行条件が通常成立せず、SLM 側の判定に進みます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4986-5012`, `sycl/include/strata/sycl_queue.hpp:159-166`）。

`STRATA_GRID_SLM` は別の compile-time 条件です。これは row reuse 分岐をコンパイルから外す条件に使われますが、`STRATA_IQ3S_GU_SLM` の判定・起動分岐自体はその `#if` の外にあります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:452-457,4986-5012`）。

## 実行時の詳細

helper の結果は `launch_gu<21>()` 内の function-local `static const bool` に保存されます。したがって環境値とデバイス既定の判定は初回呼び出し時に一度行われ、プロセス実行中に環境を変えても再評価されません。helper はデバイス世代が Battlemage かを既定判定に使いますが、この変数の既定値は `false` なので、未設定・空文字なら全デバイスで無効です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5001`, `sycl/include/strata/sycl_queue.hpp:159-166`）。

専用 kernel は work-group ごとに最大 4 token 分の Q8_1 activation を local memory にコピーして barrier で共有し、1〜4 件ずつ IQ3_S dot を計算して gate または up の出力へ書きます。kernel の起動後はこの分岐から戻り、通常の IQ3_S gate/up kernel 群は起動しません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:2274-2337,5002-5012`）。IQ3_S 型の振り分け元は native grouped expert の `L.gu_type` switch です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6126-6135`）。

この環境変数専用の有効化ログ、無効値警告、fallback ログはありません。条件を満たさない場合は通常の gate/up kernel 選択へ進みます。起動 API の失敗時にこの分岐固有の回復・終了処理はありません。

## 根拠

- 全リポジトリでの完全一致検索では、コード上の参照は `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5001` のみ。`docs/INTEL.md:538` にも索引的な説明があり、row reuse 有効時に到達不能になる旨は実装の分岐順とも一致します。
- helper の値判定と Battlemage 既定値: `sycl/include/strata/sycl_queue.hpp:159-166`。
- 専用 kernel の条件、launch と通常経路への分岐: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4980-5027`。
- staging と gate/up 計算: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:2274-2337`。
- IQ3_S 型の launch 入口: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6126-6135`。
