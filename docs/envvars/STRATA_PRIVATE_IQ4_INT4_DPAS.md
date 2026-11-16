# `STRATA_PRIVATE_IQ4_INT4_DPAS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の IQ4_XS 行列ベクトル積で、条件が揃った Battlemage の packed weights 向けに、IQ4 データを INT4 DPAS で処理する候補カーネルを選びます。対象は dense 投影（`2560→10240` または `6144→2560`、1/2/4 列）、main actor の head（`2560→248320`、4 列）、および draft actor の head（`2560→106299`、1 列）です。該当しない呼び出しではこのフラグによる選択は行われず、通常の IQ4_XS 経路または先行する別の B60 経路に続きます。読み取りと分岐は `native_iq4_xs_mmvq` にあります（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3730`）。

## 値と判定

関数内 `static const bool` 初期化子で `std::getenv` の結果を一度読み、値が存在し、かつ先頭 1 文字が ASCII `'1'` の場合だけ有効です。文字列全体や整数としては parse しません。未設定と空文字は無効、`1`・`10`・`1anything` は有効、`0`・`01`・`true`・` 1`・`True` は無効です（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3717`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL `native_iq4_xs_mmvq` が初回評価する時 | off | 先頭が `1` の任意の文字列 | 空文字、先頭が `1` 以外の文字列 |

初回評価後は同一プロセス内で値を static に保持するため、環境変数を後から変更しても反映されません。既定値は off です（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3717-3718`）。

## 有効になる条件

- SYCL 実装が組み込まれたビルドで IQ4_XS の native MMVQ に到達する必要があります。SYCL カーネルのソース一覧に `native_mmvq.dp.cpp` が含まれます（`sycl/CMakeLists.txt:39`）。
- 使用デバイスの世代が Battlemage であること、B60 packed weights 状態が true であることが必要です。Battlemage 以外、または raw weights の状態ではこの分岐を通りません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3718-3719`）。
- actor と形状が一致する必要があります。main actor の dense は `(n_in,n_out)=(2560,10240)` または `(6144,2560)` で列数 1/2/4、main actor の head は `(2560,248320)` で 4 列、main 以外の actor の draft head は `(2560,106299)` で 1 列です（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3720-3724`）。
- packed weights 状態は B60 layout の処理で設定されます。生成経路は `STRATA_PRIVATE_B60_DECODE_LAYOUT` を使って layout を要求し、single actor 経路では加えて `STRATA_PRIVATE_BMG_SINGLE_ACTOR` が必要です。layout の packed 化後に状態を true にします（`sycl/include/b60_layout_state.hpp:7-8`, `sycl/src/program/generate.cpp:4508-4515,7876-7887`, `sycl/include/b60_layout_host.hpp:126-135`）。この IQ4 フラグ単独では packed 化を要求しません。
- `STRATA_PRIVATE_IQ4_HEAD_SOA=1` で kind 24 の cache 経路が要求されていて、main/draft head の該当形状・actor・Battlemage 条件を満たす場合、その先行分岐が先に return するため、この INT4 分岐には到達しません。dense 2形状に対する kind 23 cache 分岐も先行しますが、その分岐の形状は本フラグの dense shape と一致しません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3716`; cache flag の読み取りは `sycl/include/b60_weight_cache.hpp:5-8`）。
- `STRATA_PRIVATE_B60_NEXT_POOL` が有効で、dense・4列・該当デバイス条件を満たす場合は、通常の INT4 probe の代わりに leaf-pairs probe を選びます。フラグ判定も先頭文字 `'1'` で static cache されます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3683,3724-3728`）。

## 実行時の詳細

GGML type 23 の `native_mmvq` 呼び出しが `native_iq4_xs_mmvq` へ dispatch されます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217`）。この関数では shape・pointer・stream を検証した後、先行する B60 cache 経路を確認し、それを通らない場合に対象環境変数を初めて評価します。値が有効でも条件外ならこの設定の効果はなく、後続の既存 kernel 選択へ進みます（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3694-3730,3731-3785`）。

対応 shape では `b60_iq4_int4_probe(true, ...)` に入り、dense は列数4なら split launch、それ以外の列数1/2は pair-all-T launch、main head は pair-all-T launch、draft head は Q8 split launch を選びます。dense・4列で上記 pool 条件を満たす場合のみ leaf-pairs probe に切り替わります（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3724-3728,5190-5209`）。CLI 引数がこの環境変数を直接上書きするコードは確認できません。

## ログと測定値

この変数の読み取りや選択に対応する専用ログ、警告、終了処理はありません。条件を満たさない場合は当該分岐を通過します。後段の通常 kernel 経路には `launch_check()` がありますが、この環境変数で選ぶ probe 呼び出しの直後に `launch_check()` や本変数固有のログはありません（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3724-3728,3758-3776,5190-5209`）。今回確認した `docs/` に本変数固有の説明・測定値は見つからなかったため、性能や数値結果については記載しません。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3680-3686,3692-3785` — 読み取り、shape・backend・actor・packed state 条件、先行分岐、通常経路。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:5190-5209` — INT4 probe の shape ごとの launch 選択。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217` — IQ4_XS の `native_mmvq` dispatch。
- `sycl/include/b60_layout_state.hpp:7-20`, `sycl/include/b60_weight_cache.hpp:5-8`, `sycl/include/b60_layout_host.hpp:126-137` — 関連する B60 状態・cache flag・packed 状態。
- `sycl/src/program/generate.cpp:4508-4515,7876-7887` — layout を使う生成経路。
- `sycl/CMakeLists.txt:39` — SYCL ビルドへのソース登録。
