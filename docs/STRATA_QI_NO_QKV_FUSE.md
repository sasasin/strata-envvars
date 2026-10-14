# `STRATA_QI_NO_QKV_FUSE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数の動作は対象外。

## 役割

Qwen Image 2.1 の Strata native diffusion runner が、GGUF 内の個別 Q/K/V 重みをロード時に一つの QKV 重みにまとめる処理を止めます。まとめると attention 入力の Q/K/V 射影を一回の GEMM で行い、止めると三回の GEMM を行います。これは Strata native runner 内の実装切り替えであり、外部ライブラリや GPU driver の設定ではありません。

## 値と判定

値の内容は parse されず、コンストラクターで `getenv(...) == nullptr` かどうかだけを見ます。

| 環境変数の状態 | `fuse_qkv` | 個別 Q/K/V 重みの処理 |
|---|---:|---|
| 未設定 | `true` | 条件を満たせば連結してロード |
| 設定あり（`1`、`0`、`false`、空文字を含む） | `false` | 連結せず個別にロード |

大文字小文字、空白、数値としての妥当性は関係ありません。空文字や `0` も「設定あり」として融合を無効にします。判定結果は runner のコンストラクターで `fuse_qkv` メンバーに保存され、その runner の生存中は環境を変更しても反映されません。

## 有効になる条件

- この runner がビルドに含まれる CUDA または HIP の構成で、Qwen Image 2.1 に `qwen_image_2_1_native=1` の model arg を渡し、Diffusion model path が設定されている必要があります。通常の stock runner ではこの変数を読みません。
- native runner の `compute()` は入力形状、参照画像の有無、fused MLP、CUDA/HIP backend を確認します。条件外では stock runner に切り替わるため、この変数による Strata native Q/K/V 射影の切り替えは適用されません。
- `fuse_qkv` が `true` でも、各 layer の Q/K/V tensor がすべて存在し、type と shape の条件が合わない場合、その layer の個別 tensor は結合されません。
- GGUF に最初から `attn.qkv.weight` という結合済み tensor が入っている場合、それは通常の重みとしてロードされます。この環境変数は個別の `to_q` / `to_k` / `to_v` tensor を Strata がロード時に連結する処理を止めるもので、既存の結合済み tensor を分割しません。そのため、結合済み tensor が使われる経路では、変数を設定しても一回の QKV GEMM のままです。

## 実行時の詳細

重みロードでは、融合が有効な場合に各 layer の `to_q.weight`、`to_k.weight`、`to_v.weight` を調べます。3つすべてがあり、type が一致し、Q と K の `ne[0]` が一致し、Q/K/V の `ne[1]` が一致すると、行を Q・K・V 順に並べた `attn.qkv.weight` tensor を作ります。判定コードは V の `ne[0]` を別途比較していません。個別 tensor のデータをこの tensor の各 offset に読み込みます。融合しない場合は個別名のまま読み込みます。

各 layer の計算では `attn.qkv.weight` があれば一回の GEMM を実行して出力を Q/K/V に分け、なければ `to_q`、`to_k`、`to_v` で三回 GEMM を実行します。どちらも同じ後続の `qi21_qkv_post()` に Q/K/V を渡します。この環境変数に固有のログ出力はありません。

Strata の `docs/DETAILS.md` および `docs/` に、この環境変数の説明は見つかりませんでした。性能差や数値精度への影響は資料・測定から確認できないため記載していません。

## 根拠

- `tools/image/sdcpp_native/apply.py:1-4,27-45,49-51` — native runner の選択条件と CUDA/HIP ビルド条件。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:80-90` — コンストラクターでの存在判定と保存。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:131-172` — 個別重みの適合性判定、連結 tensor の作成、個別 tensor の読み込み計画。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:214-225` — 各 layer で結合済み重みまたは個別 Q/K/V 重みがそろうことの確認。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:446-466` — native runner の入力・backend 条件と stock runner への切り替え。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:342-367` — 一回または三回の GEMM と共通後処理。
