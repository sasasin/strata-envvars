# `--no-fused-gdn`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（root scope） |
| オプション | `--no-fused-gdn` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

GDN（gated delta network）の decode 処理で、条件を満たす場合に使う融合 native kernel 経路を無効にする診断・比較用フラグです。native GDN 自体を無効にするものではなく、native GDN が有効なら各処理を分割した kernel 呼び出しに切り替えます。

## 使い方

```sh
# native GDN と native BF16 を有効にして、decode の融合 GDN kernel を使わない
strata generate --pack ./pack/full --tokens "1,2,3" --native-gdn --native-bf16 --no-fused-gdn
```

## 値と既定値

値は不要です。指定されなければ内部値 `no_fused_gdn` は `false` で、融合を許可します。指定すると `true` になり、同じ引数を複数回指定しても同じ値のままです。数値などを後ろに置いてもこのオプションの値としては消費せず、別の引数として解析されます。専用の値検証はありません。

## 実行時の動作

parser は `Options::no_fused_gdn` を立て、初期化時に `layer_set_fused_gdn(!o.no_fused_gdn)` へ反映します。既定では fusion switch は有効です（CUDA/HIP と SYCL の parser・設定箇所はそれぞれ `engine/src/program/generate.cpp:958,4266,6110`、`engine/sycl/src/program/generate.cpp:624,2212,3225`）。

実際に融合するかは、別途 native GDN が有効かにも依存します。`--native-gdn` または native preset が native GDN を有効にします（`engine/src/program/generate.cpp:1957,2595,6119`）。融合 switch が有効な場合でも、前段の畳み込み・正規化・alpha/beta 計算の融合には `native_bf16_projections`、`ssm_d_conv == 4`、`ssm_state_size == 128` が必要です。再帰 step と出力 norm の融合には native GDN と `ssm_state_size == 128` が必要です（`engine/src/core/layer.cpp:282-285,349-369`）。

このフラグを指定すると、decode の前段は `native_gdn_conv_silu`、個別の Q/K 正規化、別々の alpha/beta 投影と gate 処理へ進み、step と出力 norm も `native_gdn_step` と `native_gdn_out_norm` に分かれます（同 `engine/src/core/layer.cpp:287-307,321-345,349-369`）。SYCL 側にも同じ条件分岐があります（`engine/sycl/src/core/layer.cpp:276-307,321-337,341-361`）。native GDN が無効、またはモデル形状等の融合条件を満たさないときは、該当箇所ですでに分割経路を通るため、このフラグによる切替はありません。`layer_verify_compatible` はこのフラグが無効化した場合に fused GDN kernel が無効である理由を返します（`engine/src/core/layer.cpp:537-546`）。

この switch の参照先は `core/layer.cpp` の層処理です。prefill 側は別の GDN 実装（`engine/src/prefill/prefill.cpp:5196-5205,9334-9341`）を通り、この switch から切り替える処理は確認できません。

serve のセッション設定 fingerprint にも `no_fused_gdn` が含まれ、設定の識別に使われます（CUDA/HIP: `engine/src/program/generate.cpp:14026-14029`、SYCL: `engine/sycl/src/program/generate.cpp:8204-8208`）。ソース上、このオプションによるファイル生成・削除や子プロセス起動は確認できません。

## 適用条件と副作用

- 対象は `strata generate` の root 引数です。CUDA/HIP 実装と SYCL 実装の双方に parser と対応する decode layer 経路があります。
- native GDN が無効の場合、融合 kernel はもともと選ばれないため、このフラグは実行経路を変えません。
- 対応する融合条件を満たすモデルでは、GDN を構成する処理が融合 kernel から分割 kernel に切り替わります。性能や数値差の大きさはソースだけでは確定できません。
- kernel 呼び出し中の例外は層名付きの `err` に設定され、処理関数は失敗を返します（`engine/src/core/layer.cpp:294,307,345,353-355,369`）。

## 出力とエラー

このフラグ固有の検証エラーやメッセージ出力はありません。別の未知引数がある場合は parser が `unknown argument: ...` と usage を stderr に出して終了コード 2 を返します（`engine/src/program/generate.cpp:4268-4273`）。

## 根拠

- `engine/src/program/generate.cpp:958,4266` — 既定値 `false` と CUDA/HIP 側 parser。
- `engine/sycl/src/program/generate.cpp:624,2212` — SYCL 側の既定値と parser。
- `engine/src/program/generate.cpp:6110-6119`、`engine/sycl/src/program/generate.cpp:3223-3234` — layer switch と native GDN 設定の反映。
- `engine/src/core/layer.cpp:282-307,321-369`、`engine/sycl/src/core/layer.cpp:276-307,321-361` — 融合条件と分割経路。
- `engine/src/core/layer.cpp:537-549`、`engine/sycl/src/core/layer.cpp:539-551` — fused GDN の互換性判定と switch setter。
- `engine/src/program/generate.cpp:14026-14029`、`engine/sycl/src/program/generate.cpp:8204-8208` — serve session fingerprint への反映。
