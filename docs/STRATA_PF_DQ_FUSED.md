# `STRATA_PF_DQ_FUSED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の prompt prefill で、native IQ pack の expert 重みを FP16 に逆量子化する際、gate/up 行列と down 行列の処理を1回の kernel launch にまとめるか選びます。既定ではまとめます。無効にすると、gate/up と down を別々の2回の launch で処理します。コードのコメントは、出力値は従来の2回処理と byte-for-byte で同じで、変わるのは expert あたりの launch 数だけと説明しています。

## 値と判定

値全体の parse ではなく、`getenv()` が返す文字列の先頭1文字だけを調べます。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 有効（1 launch） |
| 空文字 | 有効（1 launch） |
| 先頭文字が `0` | 無効（2 launches）。`0`, `0anything` など |
| それ以外の先頭文字 | 有効（1 launch）。`1`, `true`, `false`, `anything` など |

大文字小文字、空白、数値としての妥当性、後続文字は検査しません。たとえば `false` も有効です。値を判定する `static const bool` は、native pack の対象分岐に初めて入った時に初期化され、その後プロセス内で再評価されません。起動後に環境を変えても反映されません。

## 有効になる条件

- SYCL backend のビルドであること。この名前を読む実装は `sycl/src/prefill/prefill.cpp` に1箇所だけあり、CUDA/HIP側の同名設定は確認できませんでした。
- prompt prefill のMoE expert処理に入ること。decode等の別経路には適用されません。
- `lay.native` が真で、かつそのlayerがMMQ経路でも `STRATA_PF_XMX=2` の専用経路でもないこと。この分岐は、native packであっても特定のMMQ、XMXグループ化経路を選んだlayerでは通りません。

対象の分岐では、`STRATA_PF_XMX=1` の grouped XMX GEMMを後段で使う場合も、この設定による逆量子化を先に行います。設定の値にかかわらず、canonical（非native）packには適用されません。

## 実行時の詳細

対象layerで各routed expertを処理する時、既定経路は `iq_dequant_expert_f16()` を呼び、gate/up と down を同じSYCL kernelに渡します。`STRATA_PF_DQ_FUSED=0` のように先頭が `0` の時は、`iq_dequant_gu_f16()` と `iq_dequant_f16()` を個別に呼びます。両方とも後続の同じFP16 GEMM処理へ渡されます。環境変数による専用ログや警告はありません。

helperの宣言と実装コメントは、新経路が旧2 kernel経路と同じFP16値を生成し、expertごとにlaunch境界を1つ減らすものとしています。headerのコメントには約4K promptで約24,500回のlaunch削減とありますが、これはコメント中の記載であり、この調査では性能を測定していません。`docs/DETAILS.md` にこの変数固有の説明や測定値は見つかりませんでした。

## 根拠

- `sycl/src/prefill/prefill.cpp:4084-4102` — native pack分岐、環境変数の読み取り、2つの処理経路。
- `sycl/src/prefill/prefill.cpp:3225-3235,3945-3958,4214-4224` — packの判定、MMQ/XMX2経路の条件、streamed/resident expertからcomputeを呼ぶ流れ。
- `sycl/include/strata/kernels/iq_dequant_expert.hpp:1-10` — 新kernelの目的、値の同一性に関する実装コメントと宣言。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4443-4465` — SYCL移植kernelの実装。gate/upとdownを1つのkernelでFP16出力へ書き込む。
- `docs/DETAILS.md` — この変数名の記載なし（文書化・測定値との照合対象となる記述なし）。
