# `STRATA_PF_FUSED_Q2N`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。

## 役割

CUDA の native Q2_0 pack で、gate/up の Q2_0 × down の Q2_0 となる MoE 層を native fused int8 prompt kernel の対象に加えます。通常この層は MMQ を使い、この変数が有効で kernel の setup に成功すると native fused 経路が選択可能になります。対象は prompt / prefill の expert 計算です。読み取り箇所は `src/prefill/moe_fused_iq.cu` の一箇所です（`src/prefill/moe_fused_iq.cu:1831-1835`）。

## 値と判定

値全体の parse はせず、`std::getenv()` が返す文字列の先頭文字が `'1'` かだけを調べます。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定値は存在するが、先頭文字が `'1'` ではない） |
| `1` で始まる文字列（例: `1`, `10`, `1abc`） | 有効要求 |
| それ以外（例: `0`, `true`, ` 1`, `01`） | 無効 |

数値変換、範囲検査、大文字小文字変換はありません。値が有効要求でも、後述の CUDA / device / kernel setup 条件を満たさなければ機能は有効になりません（`src/prefill/moe_fused_iq.cu:1834-1836`）。

## 有効になる条件

- CUDA ビルドであること。読み取りと `q2n` 分岐は `#else` 側にあり、`__HIPCC__` の経路ではこの変数を読みません（`src/prefill/moe_fused_iq.cu:1778-1783,1808-1819,1831-1835`）。
- device の compute capability major が 8 以上であること。sm_80 未満は `q2n` の読み取り位置より前に戻ります（`src/prefill/moe_fused_iq.cu:1817-1825,1831-1835`）。
- native fused kernel 群の基本 setup が成功し、`d.ok` が true であること。さらに Q2_0 gate/up 用の `setup_one<T_Q2_0, true>` が成功する必要があります。失敗時は `d.q2n` が false のままで、Q2_0 gate/up は対象外です（`src/prefill/moe_fused_iq.cu:1828-1836`）。
- 対象層の gate/up と down の形式がともに Q2_0 であること。ほかの down 形式の層にはこの opt-in は適用されません（`src/prefill/moe_fused_iq.cu:1998-2007`）。
- native fused 経路を選べる prefill 状態であること。呼び出し元は native pack、fused buffer 計画、`stream_all`、no-peer、Hadamard fold なし、および `native_supported()` を満たす場合に `fused_nat` を選びます（`src/prefill/prefill.cpp:4215-4223`）。この経路でない場合はこの変数だけでは fused kernel を選びません。

ほかの設定との関係:

- `STRATA_PF_FUSED` が未設定または空文字なら、`STRATA_PF_FUSED_Q2N=1` による Q2_0/Q2_0 の個別 opt-in が有効になり得ます。`STRATA_PF_FUSED=0`（先頭文字が `0`）は native 経路を無効にします。`STRATA_PF_FUSED=1` の場合も、Q2_0 gate/up の coverage に `d.q2n` が必要です（`src/prefill/moe_fused_iq.cu:1976-2007`; `src/prefill/moe_fused.cu:690-696`）。
- `STRATA_PF_FUSED_NATIVE=0`（先頭文字が `0`）は `native_supported()` を false にします（`src/prefill/moe_fused_iq.cu:1976-1990`）。
- CLI 引数によるこの変数の上書きは実装で確認できません。

## 実行時の詳細

`dev_info()` は device ごとの `g_dev[]` に `done` と結果を保存し、二度目以降はその値を返します。`q2n` 自体も関数内の `static const bool` なので、最初にこの CUDA の sm_80+ 判定箇所へ到達した時の値がプロセス内で cache されます。起動後に環境値を変更しても再評価されません。sm_80 未満の呼び出しは読み取り位置へ到達しません（`src/prefill/moe_fused_iq.cu:1771-1777,1817-1835`）。

値が有効でも基本 kernel または Q2_0 gate/up setup が失敗した場合、Strata はこの変数について専用の警告を出さず、Q2_0/Q2_0 層は通常の MMQ 経路に残ります。対象 layer が fused 経路に入ると、prefill は stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を一度出力し、native activation quantize と expert grouping を呼びます（`src/prefill/prefill.cpp:4252-4262`）。setup 後に実行時 CUDA エラーを検出した場合、native 実装の `ck()` は `prefill fused experts (native): <処理名>: <CUDA error>` を stderr に出し、プロセスを `exit(1)` で終了させます（`src/prefill/moe_fused_iq.cu:52-56,2109`）。この変数自体に対する無効値エラーや終了処理はありません。

## 根拠

- 候補一覧には名前がありますが、環境値を実際に読むのは CUDA native fused IQ 実装の `std::getenv("STRATA_PF_FUSED_Q2N")` だけです（`src/prefill/moe_fused_iq.cu:1834`）。ほかの一致はコメント、docs、テスト設定です。
- Q2_0 gate/up kernel の setup と任意の NT=256 / warp-specialized setup への反映: `src/prefill/moe_fused_iq.cu:1831-1851`。
- Q2_0/Q2_0 の適用判定、および他形式への制限: `src/prefill/moe_fused_iq.cu:1872-1881,1990-2015`。
- prefill 呼び出し元の経路条件と実行ログ: `src/prefill/prefill.cpp:4215-4223,4252-4262`。
- `docs/DETAILS.md` は opt-in が sm_80+ の native Q2_0 pack の Q2_0/Q2_0 層に限られ、`STRATA_PF_FUSED=0` または `STRATA_PF_FUSED_NATIVE=0` が無効化すると説明しています。また RTX 5080 Linux CUDA 13.0 での測定例と、Ampere で未検証だった旨を記載しています（`docs/DETAILS.md:1081-1099`）。これらは文書に記載された特定環境での報告で、一般的な速度向上を示すものではありません。
