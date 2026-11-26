# `STRATA_PF_FUSED_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の fused native prompt-expert 経路で、NT=256 カーネルの積和を int8 積から F16 積へ切り替える opt-in です。重みとスケール、および activation とスケールを F16 にして `m16n8k16` の F16 積を FP32 accumulator に加算します。ソースは出力が丸めレベルで変化すると記載しています。対象は NT=256 の形式であり、warp-specialized (`STRATA_PF_FUSED_WS`) を選ぶスイッチではありません（`engine/src/prefill/moe_fused_iq.cu:822-831, 3252-3269`）。

環境変数の値だけで全レイヤーがこの計算に切り替わるわけではありません。prompt 側が native fused 経路を選択し、デバイスで当該カーネル群のセットアップが成功した場合に使われます（`engine/src/prefill/prefill.cpp:5698-5704, 5793-5841`）。HIP ビルドにはこの読み取りと F16 NT=256 経路はなく、読み取り元は CUDA 専用コード内です（`engine/src/prefill/moe_fused_iq.cu:2702-2711, 2777-2809`）。同ファイルは Qwen3.6 用の `moe_fused_iq_q36.cu` からも include されます（`engine/src/prefill/moe_fused_iq_q36.cu:1-4, 36`）。

## 値と判定

| 条件（build / 経路） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の `moe_fused_iq.cu`（および同ファイルを include する Qwen3.6 版） | F16要求は false。NT=256 は別途 `STRATA_PF_FUSED_NT=256` が要求しない限り設定しない | 値の先頭1文字が `1`。例: `1`, `10`, `1anything` | 空文字、`0`, `true`, ` 1`, `2`, `01`。文字列全体の parse や数値検証はせず、先頭1文字だけを比較する |
| HIP ビルド | 読み取りなし | 該当なし | 該当なし |

`std::getenv` の結果が非 null で、かつ `v[0] == '1'` のときだけ要求扱いです。空文字は設定済みでも無効です。大文字小文字や後続文字は判定せず、`1` で始まれば受理します。関数内 `static const bool` に初回結果を保存するため、同プロセスでその関数が初めて呼ばれた後に環境を変更しても反映されません（`engine/src/prefill/moe_fused_iq.cu:2777-2785`）。

`STRATA_PF_FUSED_NT` との関係では、`nt256_requested()` がこの変数または `STRATA_PF_FUSED_NT` の `atoi(...) == 256` を見て NT=256 のセットアップを要求します。したがって F16 指定は NT=256 を暗黙に要求します。両方指定した場合も F16 判定が true ならセットアップと launch は F16 形式を選びます。一方、F16 が無効で NT=256 だけが有効なら通常の int8 NT=256 形式です（`engine/src/prefill/moe_fused_iq.cu:2779-2809, 3007-3015, 3260-3269`）。

## 有効になる条件

- CUDA ビルドであること。HIP の同名ソースにも他の prompt kernel はありますが、この F16 要求コードは CUDA 条件内で、F16 NT=256 経路は HIP にありません（`engine/src/prefill/moe_fused_iq.cu:2702-2711, 2803-2810`）。
- デバイスの compute capability が sm_80 以上であること。sm_80 未満は通常の NT=256 セットアップ箇所に到達しません。Turing (sm_75) 用 setup は先に return するため、この変数では F16 カーネルを有効にしません（`engine/src/prefill/moe_fused_iq.cu:2887-2905, 3007-3015`）。
- build が `STRATA_PF_WIDE_PARAMS` を有効にできること。CUDA の nvcc が 12.1 未満なら WideBatch の大きな kernel parameter を理由に無効化され、`setup_nt()` は false を返します（`engine/src/prefill/moe_fused_iq.cu:2693-2700, 2803-2809`）。
- ベースの native kernel がデバイス上で setup でき、対象すべての NT=256 カーネルについて関数属性、共有メモリ属性、occupancy の setup が通ること。F16 用 setup は共有 memory と occupancy も確認します（`engine/src/prefill/moe_fused_iq.cu:2745-2764, 3007-3015`）。
- モデルの対象レイヤーが prompt 側の native fused 条件を満たすこと。`use_mmq || fused_only`、stream-all、peer 不使用、native expert layout、folded layer の対応条件、および `native_supported()` を満たさないと、この経路自体を選びません。`STRATA_PF_FUSED` などによる `native_supported()` の拒否もここに含まれます（`engine/src/prefill/prefill.cpp:5692-5704`; `engine/src/prefill/moe_fused_iq.cu:3415-3432`）。
- F16 NT=256 kernel 群のいずれかが setup に失敗すると `d.occ_nt` は 0 になり、NT=256 利用可の条件を満たしません。標準の native 512-thread path に留まる場合があり、F16 での実行は保証されません（`engine/src/prefill/moe_fused_iq.cu:3007-3015, 3854-3863`）。
- `STRATA_PF_BATCH` は複数 expert を一度に launch する上限を変え、128 を超える wide batch を選ぶ条件に関係しますが、F16 積和を選ぶ値ではありません。これが wide batch 条件を満たさなくても `Batch` overload は NT=256 が setup 済みなら `WideBatch` overload へ転送します（`engine/src/prefill/prefill.cpp:5784-5794`; `engine/src/prefill/moe_fused_iq.cu:3854-3863`）。

## 実行時の詳細

`f16c_requested()` は関数内 static に判定を保持します。`dev_info()` もデバイスごとの `done` フラグで初回 setup 結果を保持します。F16 が要求されると `nt256_requested()` により NT=256 のカーネル群を setup し、`setup_nt()` は F16 template (`F16=true`) の occupancy を調べます（`engine/src/prefill/moe_fused_iq.cu:2779-2809, 2847-2853, 3007-3015`）。

実際の prompt 処理では `native_supported()` を通ったレイヤーが `experts_native()` に入ります。NT=256 が setup 済みなら、Batch overload も WideBatch overload に移し、CUDA launch が `f16c_requested()` に従って F16 template を実行します（`engine/src/prefill/prefill.cpp:5698-5704, 5830-5841`; `engine/src/prefill/moe_fused_iq.cu:3252-3269, 3854-3863, 3954-3990`）。

NT=256 の F16 形式は重み・activation のスケール適用後の F16 値を積算するため、丸め挙動が int8 形式と異なります。これは F16 重みを使う別カーネルの選択ではなく、NT=256 native kernel 内の積演算形式の変更です（`engine/src/prefill/moe_fused_iq.cu:827-831`）。

## ログと測定値

NT=256 のセットアップに失敗した場合、デバイス情報の初期化で stderr に次の行を出します（F16 の無効値や unset だけでは出ません。デバイスが `d.ok` で、NT=256 が要求され、セットアップ全体が失敗した場合です）。

```text
prefill fused experts (native): STRATA_PF_FUSED_NT=256 is not available here
```

この失敗時、NT=256 専用経路は利用可能と扱われず、F16 の積和で処理されるとは限りません（`engine/src/prefill/moe_fused_iq.cu:3007-3015, 3854-3863`）。

`docs/DETAILS.md` は変更著者による CMP 170HX（GA100、70 SMs）での報告として、Qwen3.8-Flash-Next IQ3_S native pack の同一レイヤーで F16 variant 7.90 ms と記録しています。計測条件の概要は同資料の直前にあり、Strata 側では測定していないと明記されています。そこでは F16 が bitwise base と丸めレベルで異なる設定の一つで、20 prompts の teacher-forced KL 平均 0.0062、top-1 agreement 100% とも報告されています。これらは資料中の著者報告であり、この調査で再測定した結果ではありません（`docs/DETAILS.md:1804-1806, 1815-1824`）。

## 根拠

- 値の判定と `STRATA_PF_FUSED_NT` への接続: `engine/src/prefill/moe_fused_iq.cu:2777-2809`
- sm_80 以上、wide parameter build macro とセットアップ結果: `engine/src/prefill/moe_fused_iq.cu:2693-2700, 2887-2905, 3007-3015`
- F16 積和の形式: `engine/src/prefill/moe_fused_iq.cu:822-831, 3252-3269`
- prompt 経路の選択と呼び出し: `engine/src/prefill/prefill.cpp:5692-5704, 5784-5794, 5830-5841`
- 設定失敗時のログと Batch から WideBatch への転送: `engine/src/prefill/moe_fused_iq.cu:3007-3015, 3854-3863`
- 同じ実装の Qwen3.6 用 include: `engine/src/prefill/moe_fused_iq_q36.cu:1-4, 36`
- 測定値の出典と条件: `docs/DETAILS.md:1804-1806, 1815-1824`
