# `STRATA_KVA_SKIP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

KVA（近似 prompt read）が適用される late layer で、既定の state-only 処理に代えて attention 半分を通常どおり計算し、MoE 半分を省略するモードを選びます。値が有効でも、KVA 自体が有効で、その chunk と layer が近似対象になった場合だけ効果があります。KVA は既定で無効です（`include/strata/prefill/kva.hpp:72-90,149-156`）。

## 値と判定

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定 | 既定 | `StateOnly` |
| 空文字 | 既定 | `StateOnly` |
| 完全一致の `moe` | 有効 | `Moe` |
| その他すべて（`state`、`bogus`、`MOE`、空白付きなど） | 無効値として既定に戻る | `StateOnly` |

`std::string(sk) == "moe"` による大文字小文字を区別する文字列全体の比較です。trim、数値変換、無効値の警告やエラーはありません。CLI 引数による上書きもありません。値の既定は `KvaConfig::skip = StateOnly` で、環境読み取りはその値を完全一致時だけ `Moe` に変えます（`include/strata/prefill/kva.hpp:69-90,182-188`）。同ファイルのテストも未設定、`moe`、`state`、`bogus` の結果を確認するケースを記述しています（`src/prefill/kva_test.cpp:129-138`。テストは今回実行していません）。

## 有効になる条件

- KVA の主スイッチ `STRATA_KVA` が空でない値で設定され、先頭文字が `0` でないこと。未設定・空文字・先頭文字が `0` の値では KVA が動かず、この変数も効果を持ちません（`include/strata/prefill/kva.hpp:149-156`）。
- ビルドに KVA prefill path があること。`STRATA_GPU_METAL` ビルドでは `kKvaBackend` が false となり、KVA は無効です（`include/strata/prefill/kva.hpp:43-49,149-156`）。
- SYCL engine は別の prompt path を使い KVA を持たない、と Strata の KVA 説明文書は記載しています（`docs/KVA.md:99-104`）。
- その prompt read が KVA の適用条件を満たし、chunk が近似 prefix 内にあり、layer が split 以降であること。KVA は cold read、全 trunk の読み取り等の条件を検査し、chunk ごとに近似区間を決めます。`STRATA_KVA_ONLY` が `gdn` または `qsa` なら、選ばれた種類の layer にだけこの skip が及びます（`include/strata/prefill/kva.hpp:104-134`; `src/prefill/prefill.cpp:2947-2966,3115-3123,3621-3627`）。
- layer の MoE expert 転送計画も、同じ近似 chunk・split・`STRATA_KVA_ONLY` 条件に基づいてその layer を除外します（`src/prefill/prefill.cpp:3382-3394`）。

## 実行時の詳細

本番経路では `kva_config()` が `static const KvaConfig` を初回に一度生成して環境値を保持します。generate 初期化時にもこの設定を参照し、prefill 各回も同じ cache を読むため、起動後に環境を書き換えても反映されません。`kva_config_from_env()` 自体は環境から都度作る helper ですが、製品経路は cache された `kva_config()` を使います（`include/strata/prefill/kva.hpp:149-195`; `src/program/generate.cpp:6263-6279`; `src/prefill/prefill.cpp:2947-2954`）。

近似対象 layer では `STRATA_KVA_SKIP=moe` のとき attention half（GDN または QSA）を実行します。その出力は residual に書き込まれます。続く `half == 1` で MoE half を実行せず、その layer の expert 転送も計画から除きます。既定の state-only と異なり、attention の出力計算・residual への反映が残ります（`src/prefill/prefill.cpp:3621-3627,3382-3394,3696-3705`; attention 処理 `src/prefill/prefill.cpp:3792-3842,3843-3961,4103`）。

有効時にこの変数専用の警告や失敗経路はありません。KVA が適用された read の stderr 行では mode が `moe-skip` と表示されます（`src/prefill/prefill.cpp:5820-5831`）。KVA を要求していても条件不成立なら、通常の `KVA configured but NOT applied: ...` 行などで KVA が適用されなかった理由が出ますが、この変数の不正値を理由とするログはありません（`src/prefill/prefill.cpp:5844-5856`; 起動時の batch slots、layer split、peer device の通知 `src/program/generate.cpp:6269-6277`）。

## 根拠

候補一覧 `000_envvers.md` には名前がありますが、Strata 所有コードでの実際の読み取りは `include/strata/prefill/kva.hpp:182` の1箇所です。ほかに見つかった名前の参照はコメント、KVA 説明文書、テストです。動的な環境名 helper への引き渡しはなく、読み取った `Skip` 値は前述の prefill 分岐へ渡されます。

`docs/KVA.md:116` も `moe` を opt-in とし、attention 半分を実行して MoE 半分と expert transfers を省くモード、ログ名 `mode moe-skip` と説明しています。同文書の「既定 state-only より遅く、exact residual に近い」という記述は定性的な説明で、この変数についての独立した測定値や測定条件は確認できなかったため、ここでは性能値を記載していません。
