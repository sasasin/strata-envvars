# `STRATA_PF_Q8D_F16`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の状態は `main...origin/main` で、作業ツリーに未コミット変更はありませんでした。外部ライブラリの環境変数は対象外です。

## 役割

HIP の gfx1151（Strix Halo）で、native fused prefill が `Q8_0` down 射影に F16 matrix-core kernel を使う既定動作を止めるための変数です。通常は gfx1151 でこの選択が既定で有効で、`STRATA_PF_Q8D_F16` の値の先頭文字が `0` のときだけ無効になります。対象は Q8_0 down であり、gate/up や他の重み形式の選択を直接変えません。

`STRATA_PF_F16=1` が別途有効な場合、Q8_0 down は通常の F16 対応形式として同じ F16 kernel に進むため、この変数を `0` にしても F16 経路は止まりません。`STRATA_PF_F16` が無効のときに、本変数が gfx1151 の Q8_0 down を追加で F16 対応扱いにします。ソース注釈は、この選択時に Q8_0 down の出力が int8 kernel と異なり得ることを記しています。

## 値と判定

HIP コンパイル時に限り、`q8d_f16_default()` の関数内 `static const bool` が `std::getenv()` の結果を一度読み、その先頭文字だけを検査します。文字列全体の parse、数値変換、大文字小文字変換はありません。

| 状況 | `q8d_f16_default()` の結果 |
|---|---|
| 環境変数が未設定 | 有効（gfx1151 で既定 ON） |
| 空文字 | 有効（設定値は存在するが、先頭文字は `\0` で `'0'` ではない） |
| 先頭文字が `0`（例 `0`, `0abc`） | 無効 |
| それ以外の先頭文字（例 `1`, `true`, `false`, 空白） | 有効 |
| CUDA コンパイル | 常に無効扱い。本変数は読み取られない |

この判定結果が実際に使われるのは HIP かつ `d.w12 == false` で、さらに実デバイスが gfx1151 の場合だけです。gfx12（RDNA4）または gfx1151 以外では `getenv` 判定に到達せず、関数は `false` を返します。したがって gfx1151 以外で設定しても効果はありません。

## 有効になる条件

本変数の設定が効くには、次の条件が必要です。

- HIP build で、native fused prefill の実カーネルがデバイス上で利用可能であること。HIP 側の `dev_info()` はデバイスアーキテクチャとロードされた native kernel の属性を調べ、native kernel が実装されている場合に `d.ok` を立てます。
- デバイスが gfx1151 であること。gfx12 は明示的に除外されます。
- 対象 layer の down 形式が `Q8_0` であること。
- `STRATA_PF_F16` が要求されていないこと。この変数は `!f16` の場合に限り追加の F16 選択肢になります。`STRATA_PF_F16=1` は別経路で Q8_0 down に F16 kernel を選びます。
- prefill planner がその layer を native fused 経路に割り当てること。native 形式では全 layer の `native_supported()` を調べて fused 用バッファを縮小するか判断し、各 layer の実行時にも native 対応と stream 条件を確認します。peer-device 経路では fused 経路を使いません。

`STRATA_PF_Q8D_F16=0` で Q8_0 down が native 対応形式から外れた場合、該当 layer は fused native kernel を使いません。planner は fused 用バッファを全 layer 向けに縮小せず、対応 layer だけを fused に残す設計です。これは `native_supported()` と prefill planner の分岐から分かる効果であり、環境変数固有の警告は実装されていません。

## 実行時の詳細

HIP デバイスの `dev_info()` は device property から gfx12 / gfx1151 を識別し、native W11 kernel の属性と occupancy を確認して device 状態を cache します。`q8d_f16_default()` は gfx1151 かつ非 gfx12 の条件を満たした後にだけ環境変数を読みます。その読み取り結果は関数内 static に cache されるため、プロセス実行中に環境を書き換えても再評価されません。CLI 引数、設定ファイル、他の環境変数によるこの値の上書きはありませんが、`STRATA_PF_F16` は並行する別の F16 選択経路です。

`d_covered_on()` は Q8_0 down を `STRATA_PF_F16` または本変数が有効なとき native 対応とみなします。実行時の native expert kernel は `f16 = !d.w12 && f16::requested()` と `f16_q8d = !f16 && Q8_0 down && q8d_f16_default(d)` を作り、`f16_q8d` が真なら Q8_0 down 用の `native_f16_kernel` を起動します。偽なら Q8_0 の native int8/W11 kernel に進みます。

直接の変数判定によるログや終了処理はありません。native kernel 関数を対応外の形式で直接呼んだ場合には一般的な guard が stderr に `prefill fused experts (native): types %d / %d are not covered here`（wide batch 版は `prefill fused experts (native, NT = 256): types %d / %d are not covered here`）を出して `exit(1)` します。通常経路では事前の `native_supported()` 判定があるため、この guard は対応外呼び出しに対するものです。

## 根拠

- `src/prefill/moe_fused_iq.cu:1672-1684,1771-1807`: per-device 状態の保持、HIP build での device architecture / native kernel 判定、gfx1151 と gfx12 の識別。
- `src/prefill/moe_fused_iq.cu:1890-1913`: 対象 Q8_0 down の条件、環境値の読み取り、`STRATA_PF_F16` との併用・優先関係。
- `src/prefill/moe_fused_iq.cu:1976-2016`: `native_supported()` で形式と device 状態を判定し、native 経路の可否を返す処理。
- `src/prefill/moe_fused_iq.cu:2025-2032,2061-2065,2096-2106`: unsupported guard、HIP native kernel の選択、および Q8_0 down の F16 / W11 launch 分岐。
- `src/prefill/prefill.cpp:298-313,1360-1379,4215-4234`: native pack の全 layer 対応確認、planner の fallback / fused 割当、実行時の stream・peer 条件。
- `src/prefill/moe_f16_common.cuh:53-60`: 関連する `STRATA_PF_F16` の先頭文字判定と static cache。
- `000_envvers.md:1231-1235` は本変数を候補として列挙しています。ソース上では上記の HIP 読み取りがあり、候補一覧と矛盾しません。
