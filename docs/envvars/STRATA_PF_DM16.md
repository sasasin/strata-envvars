# `STRATA_PF_DM16`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

prompt の fused native MoE 経路で、対象となる F16 down カーネルの expert 出力行を FP32 ではなく FP16 で書き、後段を `moe_combine16` に切り替える要求スイッチです。FP16 の down 行は各値を半精度へ変換し、有限範囲を `[-65504, 65504]` に飽和させます。設定だけでは fused 経路や F16 カーネルを選択せず、カーネル選択条件が満たされない層では通常の FP32 行と `moe_combine` のままです（`engine/src/prefill/prefill.cpp:980-984, 5698-5704, 5830-5844, 7622-7630`; `engine/src/prefill/moe_fused_iq.cu:3781-3788`; `engine/src/prefill/moe_f16_common.cuh:229-253`）。

主な利用経路は AMD gfx11 の prompt fused native expert カーネルです。Strata の gfx11 既定値テーブルは `STRATA_PF_DM16=1` を加える場合があります（後述）。decode、非 native fused expert 経路、同梱ツールからこの値を読む実装は見つかりませんでした。

## 値と判定

`prefill.cpp` の `pf_dm16()` は `std::getenv` の戻り値が非 null で、かつ先頭文字 `e[0]` が文字 `'1'` の場合だけ true とします。文字列全体・数値としての妥当性・大文字小文字・後続文字は検査しません。従って空文字は false、`1` と `1anything` は true、`10` も true、`0`・`0anything`・`true`・` 1` は false です。unset は false です（`engine/src/prefill/prefill.cpp:981-984`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `pf_dm16()` の判定 | false（ただし gfx11 起動時の既定設定が先に値を設定する場合あり） | 先頭文字が `1` の値: `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, ` 1` |

関数内 `static const bool` に初回評価結果を保存します。したがって `pf_dm16()` の初回呼び出し後にプロセス環境を変更しても、この判定には反映されません。値を読む際に CLI 引数や設定ファイルとの比較はなく、コード中で確認できる既定値設定との関係は「unset のときだけ Strata が設定し、利用者が設定した値はそのまま残す」です（`engine/src/prefill/prefill.cpp:981-984`; `engine/src/core/arch_defaults.cpp:218-223, 302-309, 334-343`）。

## 有効になる条件

- 実行が prompt の MoE 処理を通り、その層で `fused_nat` が true であること。コード上これは MMQ 計画の対象、`stream_all`、peer 計算なし、native レイアウト、対応する重み形式（または対応条件を満たす folded layer）などを要します。通常の fused/非 native 経路ではこの値を渡さず、FP32 down 行を使います（`engine/src/prefill/prefill.cpp:5692-5704, 5830-5847`）。
- `moe_fused_iq.cu` が対象ビルドに含まれ、その native 経路に到達すること。該当実装は HIP/CUDA コンパイル分岐を持ち、機能のコメントとカーネル選択条件は gfx11 の F16 expert カーネルを示します。ビルドされない fused 実装の stub は要求を受けても何もしません（`engine/src/prefill/prefill.cpp:180-203`; `engine/src/prefill/moe_fused_iq.cu:3781-3835`）。
- down が F16 カーネルを使うこと。HIP では `STRATA_PF_F16` が `1` または `2` であると F16 が要求されます。さらに down の形式が F16 対応であるか、F16 要求が false の場合でも `f16_q8d`（Q8_0 down の既定 F16 経路）が選ばれる必要があります。非対応形式・gfx12 (`d.w12`)・他の down カーネルでは DM16 になりません（`engine/src/prefill/moe_f16_common.cuh:55-62`; `engine/src/prefill/moe_fused_iq.cu:3781-3788, 3830-3836`）。
- prompt 呼び出し側が追加条件を満たすこと: `rows_cpu == 0`、`peer_now == false`、`m.shared` と `m.bo` の両ポインターが 16-byte aligned であること。どれかを満たさない場合は `want_dm_f16(false)` が渡ります（`engine/src/prefill/prefill.cpp:5830-5844`）。
- fused native 関数内で要求後にも形式別判定を通ること。実装は `d16` を算出して直近カーネルが FP16 を書いたか `dm_f16_used()` で返し、呼び出し元がそれを受けた場合だけ `moe_combine16` を選びます。別経路や別形式なら FP32 用 combine です（`engine/src/prefill/moe_fused_iq.cu:3786-3788`; `engine/src/prefill/prefill.cpp:5840-5844, 7622-7630`）。

起動時に既定で有効化する条件もあります。RDNA3 discrete `gfx1100/1101/1102` では WMMA 既定値テーブルが `STRATA_PF_DM16=1` を含み、`STRATA_DEFAULTS=026`、`STRATA_GFX11_DEFAULTS` が先頭文字 `0`、または `STRATA_GFX11_WMMA_DEFAULTS` が先頭文字 `0` のときはこのテーブル自体が無効です。Windows `gfx1151` の別テーブルにも `STRATA_PF_DM16=1` が含まれます。いずれも既に環境変数が設定されていれば（空文字や `0` も含む）Strata は上書きしません。これらの設定は機能の成立を保証するものではなく、上記の prompt・native・F16 条件は別途必要です（`engine/include/strata/core/gfx11_extra.hpp:27-37, 87-114`; `engine/src/core/arch_defaults.cpp:190-209, 302-343`）。

## 実行時の詳細

prompt 層の fused native 処理で、呼び出し側が `pf_dm16()` を評価して `want_dm_f16(...)` に渡します。この読み取りは `static` にキャッシュされます。要求値は `moe_fused_iq.cu` の `thread_local` 状態に保存され、`experts_native()` は各呼び出しの冒頭で前回の `dm_f16_used` を false に戻します。F16 down 対応時だけ `d16` を true にして、down kernel の FP16 出力テンプレート経路を選びます。FP16 出力の各値は上記範囲に飽和後 half に変換されます。呼び出し元はその呼び出しの `dm_f16_used()` を受け取り、CPU 行がないとき `moe_combine16` に分岐します。この combine は down 行を half から float に戻して重み付き加算し、shared 経路と合成します（`engine/src/prefill/prefill.cpp:5831-5844, 7622-7630`; `engine/src/prefill/moe_fused_iq.cu:3596-3601, 3686-3701, 3786-3795`; `engine/src/prefill/moe_f16_common.cuh:229-253`; `engine/src/prefill/kernels.cu:2442-2469`）。

DM16 固有の CLI 引数、リクエストごとの再読み取り、子プロセスへの転送は見つかりませんでした。`pf_dm16()` の読み取り箇所は一つです。ソース全体で他の候補名参照も確認し、`gfx11_extra.hpp` と `arch_defaults.cpp` は値を読み取る箇所ではなく unset 時の値設定、テストや設定レジストリは実行時読み取りではないことを区別しました。

## ログと測定値

この変数だけに対する有効・無効ログ、警告、エラーはありません。gfx11 既定値を適用した起動では一般の既定スイッチ一覧ログに `PF_DM16` が含まれます。ユーザーが `STRATA_PF_DM16` を設定済みの場合は既定値一覧に追加されず、同変数はログされません（`engine/src/core/arch_defaults.cpp:334-344`）。

コードコメントには down 行の書き込み・読み込みバイト数が半分になるとの説明がありますが、この調査では実測条件を示す資料を確認できなかったため、性能測定値は記載しません（`engine/src/prefill/prefill.cpp:980`; `engine/src/prefill/kernels.cu:2442-2443`）。

## 根拠

- `engine/src/prefill/prefill.cpp:980-984` — 環境値の読み取りと static cache。
- `engine/src/prefill/prefill.cpp:5692-5705, 5830-5844, 7622-7630` — native prompt 経路、呼び出し条件、FP16 combine の選択。
- `engine/src/prefill/moe_fused_iq.cu:3596-3601, 3686-3701, 3781-3836` — thread-local 要求、実際の down 出力形式の判定とカーネル選択。
- `engine/src/prefill/moe_f16_common.cuh:229-253`; `engine/src/prefill/kernels.cu:2442-2469, 3502-3508` — FP16 down 出力の飽和・変換と combine。
- `engine/include/strata/core/gfx11_extra.hpp:27-37, 87-114`; `engine/src/core/arch_defaults.cpp:218-223, 302-343` — gfx11 既定値、利用者設定優先、既定スイッチログ。
