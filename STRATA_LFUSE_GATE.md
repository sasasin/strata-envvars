# `STRATA_LFUSE_GATE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 調査）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の batched decode で、共有 expert の gate の BF16 投影を router 投影と同じ multi-row GEMV launch に含める処理を有効・無効にします。変数名に `GATE` とある通り、共有 expert の gate/up 投影を一つの launch にまとめる別の `STRATA_LFUSE_PAIR` 機能は制御しません。

## 値と判定

CUDA と SYCL の実装は `getenv()` の値の有無と先頭文字だけを調べ、文字列全体や数値としての妥当性は parse しません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効 |
| 先頭文字が `0`（例: `0`, `0anything`） | 無効 |
| 先頭文字が `0` 以外（例: `1`, `true`, `false`, `off`, 空白始まり） | 有効 |

判定結果は関数内の `static const bool` に保存されます。各 backend のプロセスで初回評価後に環境変数を変更しても、その結果は再評価されません。

## 有効になる条件

`STRATA_LFUSE_GATE` が有効でも、共有 gate の投影を router launch に加えるには次の条件を満たす必要があります。

- 親機能 `STRATA_LFUSE` が有効。こちらは別の判定で、値の先頭文字が `1` の場合だけ有効です。HIP gfx1151 では起動時に Strata が既定値 `1` を設定する場合があります。
- `ar_on()`（all-resident 経路）、native MoE combine、`STRATA_DEC_BATCH` による batched decode が有効。
- verify window の行数 `n` が 2〜8。
- router launch が対象の native multi-row router 経路に入る。CUDA は `NE == 512 && K == 10`、SYCL は `(NE == 512 || NE == 256) && K == 10` を要求し、どちらも `n > 1`、router weight の存在、`native_router_enabled()` が必要です。
- `shared_expert_native_bf16_enabled()` が有効。

これらの条件に合わない経路では gate 投影の fused launch は使われません。この変数専用のログ出力はありません。

## 実行時の詳細

条件成立時、Verifier は `ffn_gate_inp_shexp.weight` を補助行として router の multi-row GEMV に渡し、結果を `sh_g_` に書きます。補助行を計算できた場合は `sg_ready` が true となり、後続の共有 expert 処理へ gate が計算済みであることを示すフラグを渡します。最後の MoE combine は `sg_gated_` に応じた gated combine 経路を使います。無効の場合や補助計算が成立しない場合は通常の router GEMV に進みます。

CUDA と SYCL の verifier に同じ環境変数判定があります。CUDA の router 対象は 512 experts のみですが、SYCL は 256 experts も対象にしています。SYCL/HIP gfx906 の別分岐では通常の router window 経路へ進み、`sg_ready` を立てません。

参照: `src/core/verify.cpp:133,1436-1447,1531-1536,1652-1656`; `sycl/src/core/verify.cpp:72,1307-1318,1390-1395,1502-1506`。

## 根拠

- 環境変数の parse と static cache: `src/core/verify.cpp:133`, `sycl/src/core/verify.cpp:72`。
- gate 融合が成立する共通条件: `src/core/verify.cpp:852-855`, `sycl/src/core/verify.cpp:837-840`。
- gate weight の選択と router launch: `src/core/verify.cpp:1433-1447`, `sycl/src/core/verify.cpp:1304-1318`。
- `sg_ready` の共有 expert への伝達と combine: `src/core/verify.cpp:1531-1536,1652-1656`, `sycl/src/core/verify.cpp:1390-1395,1502-1506`。
- `STRATA_LFUSE` の gfx1151 既定値と適用: `src/core/arch_defaults.cpp:50-53,61-70`; 起動時適用箇所 `src/program/generate.cpp:2152-2158`。

`docs/DETAILS.md` に `STRATA_LFUSE_GATE` 固有の説明や測定値は見当たりません。上記は調査対象 HEAD の実装から確認できる動作です。
