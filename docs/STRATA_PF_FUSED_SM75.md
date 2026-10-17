# `STRATA_PF_FUSED_SM75`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の Turing（compute capability 7.5）で、Q2_0 pack の MoE prompt expert 計算に fused int8 カーネルを使えるようにする opt-in です。Turing では Ampere 以降用の `cp.async` と `m16n8k32` 命令を使えないため、通常ロードと `m8n8k16` MMA を使う実装を選びます。環境変数が有効でも、それだけで fused 経路を選ぶわけではなく、prompt の chunk、streaming、GPU 数、pack、カーネル利用可能性などの条件も必要です。

## 値と判定

両方の CUDA 実装箇所で、環境変数を初めて評価したときの値を `static const bool` に保存します。文字列全体や数値としての parse は行わず、先頭文字が `'1'` かだけを比較します。

| 値 | Turing カーネル許可 |
|---|---|
| unset | 無効 |
| 空文字 | 無効 |
| `1`、`10`、`1anything` | 有効 |
| `0`、`true`、` 1`、その他先頭が `1` でない値 | 無効 |

大文字小文字、空白除去、後続文字の検査はありません。各 CUDA translation unit の `dev_info()` が初めて呼ばれた際に判定し、その後の環境変更は同じプロセスでは反映されません。device 情報も各実装内で初回取得後キャッシュされます。

## 有効になる条件

- CUDA build であること。HIP build の分岐はこの変数を参照せず、この opt-in では有効になりません。
- 実 device が compute capability 7.5 であり、build に sm_75 以上の対象コードが含まれ、必要なカーネル属性と occupancy の確認を通ること。`STRATA_EMULATE_CC` による compute capability の置換はソース上テスト用として扱われています。
- Q2_0 pack の経路では、fused backend が利用可能であること。`STRATA_PF_FUSED` が unset の CUDA build では通常その選択が既定で有効ですが、値の先頭が `0` なら無効になります。
- 実際の prefill 呼び出しで `mmq_plan` が該当 layer を選び、`stream_all` が有効、peer device を使っておらず、chunk が streaming の最低サイズ以上であること。条件を満たさない chunk は MMQ 経路に残ります。
- native IQ pack では別の選択条件もあります。sm_75 で実装対象なのは Q2_0 gate/up と Q2_0 down の組み合わせだけで、通常の native pack fused opt-in `STRATA_PF_FUSED=1` も必要です。`STRATA_PF_FUSED_NATIVE=0` は native pack の fused 経路を止めます。sm_80 以降ではこの変数の gate/up 追加対象になりません。

## 実行時の詳細

Q2_0 実装の `dev_info()` は、compute capability が 75 未満なら利用不可とし、75–79 ではこの変数が有効な場合だけ先へ進みます。その後、カーネル属性・PTX version・共有メモリー設定・occupancy を確認し、利用できなければ Q2_0 fused backend を使えない状態にします。80 以上はこの変数の値にかかわらず従来の対応カーネル判定へ進みます。

native IQ 実装も同じ先頭文字判定で sm_75 の `dev_info` を許可しますが、Turing では Q2_0 形式の gate/up と down に限定します。これは native pack の `STRATA_PF_FUSED` opt-in の上に重なる条件です。

prefill が fused 経路へ入ると、初回に stderr へ `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を出し、activation の量子化、GPU 上での routed expert grouping、その後の expert kernel launch を行います。このログは一般的な Q2_0 fused 経路のものです。`STRATA_PF_FUSED_SM75` 専用のログは確認できません。既存資料はこの経路を「answers を変える options」の一つに挙げていますが、ここではソースにある Turing の実装切替のみを説明し、精度や速度を一般化しません。

## 根拠

- `src/prefill/moe_fused.cu:645-668,675-695`: CUDA Q2_0 backend の compute capability gate、変数値判定、カーネル利用可能性、`STRATA_PF_FUSED` との関係。
- `src/prefill/moe_fused.cu:198-218`: sm_75 で通常コピーと複数の `m8n8k16` MMA を使う実装。
- `src/prefill/moe_fused_iq.cu:1184-1192,1287-1310,1328-1353,1386-1409`: native pack 側の sm_75 gate、対象形式、別 opt-in 条件。
- `src/prefill/prefill.cpp:3366-3382,3408-3418`: prefill での stream-all / peer / pack 条件と fused 経路のログ・処理開始。
- `docs/DETAILS.md:2259-2261`: この変数を Q2_0 pack の fused int8 prompt expert opt-in として記載し、compute capability 7.5 のみで sm_80+ は不変と説明。
