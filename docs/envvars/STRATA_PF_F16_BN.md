# `STRATA_PF_F16_BN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の fused prefill expert が gfx11 の F16 WMMA kernel を使う場合に、1 work item あたりの行数（BN）を固定します。指定できる BN は 64 行または 128 行です。未指定または認識されない値では、バッチ中の routed row 数と expert 数から 64 / 128 行を選びます。

これは通常の利用者向けの機能スイッチではなく、既に選択された F16 kernel の仕事単位を調整する実装フックです。環境変数だけでは F16 kernel を有効にしません。

## 値と判定

`src/prefill/moe_f16_common.cuh` の `pick_bn()` が `std::getenv()` で読み、`std::atoi()` の変換結果が `kTileRows`（64）またはその2倍（128）と一致する場合だけ固定値として採用します。

| 値 | 判定・動作 |
|---|---|
| 未設定 | 固定指定なし。自動選択 |
| `64` に変換される文字列 | BN=64 |
| `128` に変換される文字列 | BN=128 |
| 空文字、数値に変換できない文字列、変換結果が64/128以外 | 固定指定なし。自動選択 |

全体を数値として検証する処理ではありません。`atoi` のため、先頭の空白や符号を含む文字列、数値の後ろに文字が続く文字列でも変換結果が64または128なら固定指定になります（例: ` 64`, `+128`, `64tail`）。`064` は10進数の64として扱われます。負値や `0` は固定値になりません。

自動選択は `n_expert > 0` なら `n / n_expert`、そうでなければ分母を1として計算し、平均が64以上なら128、64未満なら64を選びます。比較は `double` で行います。

## 有効になる条件

この指定が実際の kernel 選択に反映されるのは、HIP の fused native expert 経路で gfx11 の F16 kernel が選ばれた場合です。実装上は `STRATA_PF_FUSED=1` に加え、F16 経路の `STRATA_PF_F16=1` が必要です。Q4_K / Q5_K の gate/up と Q5_1 の down では、さらに `STRATA_PF_FUSED_KQ=1` が必要です。

F16 native kernel の他の対象形式は IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S / IQ4_XS の gate/up と、Q2_0 / IQ4_NL / Q8_0 の down です。実際に使える型の組み合わせはデバイス情報と `native_supported()` の条件にも依存します。gfx12（`d.w12`）ではこの F16 kernel 分岐を使わず、他の backend にもこの選択は適用されません。

## 実行時の詳細

`pick_bn()` 内の `static const int forced` は初回呼び出し時に一度だけ評価されます。その後プロセス内で環境変数を変更しても固定指定の再読み込みはありません。HIP の `experts_native()` は F16 wide 判定を計算し、F16 kernel を起動する際に BN=64 または128のテンプレート版を選びます。K-quant 専用の `f16kq::gate_up()` と `f16kq::down()` も同じ `pick_bn()` を呼び、それぞれの kernel 版を選択します。

`BN=128` 版は work item が連続した64行タイルを2つまとめて扱い、128行未満の端数にも対応します。したがって、この変数が変えるのは F16 prefill expert kernel の処理単位と起動するテンプレート版です。ソースは、この環境変数による出力の同一性や性能上の優劣を保証していません。

## 資料上の測定値

`src/prefill/moe_f16_common.cuh:62-64` の実装注釈には、gfx1151 の Q4_K、512 expert 中 top 10、128-expert launch という条件で BN=64 / 128 の所要時間（ms）が記録されています。1024 tokens: 1.22 / 1.28、2048: 1.51 / 1.64、4096: 2.73 / 2.48、8192: 4.76 / 4.59、16384: 9.19 / 8.46 です。同じ注釈の Q5_1 down は2048: 1.02 / 1.04、4096: 1.61 / 1.48、16384: 5.29 / 4.83 です。これはソースコメントに記録された条件付き測定で、他の機種・モデル・設定での性能を示すものではありません。`docs/DETAILS.md` にはこの変数名の説明や別の測定記録は見つかりませんでした。

## 根拠

- `include/strata/prefill/moe_fused.hpp:23-24` — 基本タイル行数 `kTileRows=64`。
- `src/prefill/moe_f16_common.cuh:53-73` — F16 スイッチと環境変数の解析、未指定時の64/128自動選択。
- `src/prefill/moe_fused_iq.cu:1323-1354,1386-1408` — F16 対象型、デバイス条件、fused native kernel の有効条件。
- `src/prefill/moe_fused_iq.cu:1428-1465,1487-1492` — HIP 経路でのBN判定とF16 kernel起動。
- `src/prefill/moe_f16_kq.cu:1-8,308-331` — gfx11 K-quant kernel の対象型とBN別の起動。
