# `STRATA_PREFILL_STREAM_MIN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt prefill の chunk がこの token 数以上のとき、GPU cache にない expert を全層分まとめて stream する経路の最小 token 数を指定します。閾値未満では routed-only staging（その chunk の token が実際に選んだ expert を必要時に送る経路）になります。閾値は stream ring の大きさと経路選択にも使われます。

実装は CUDA/HIP 共通の `src/prefill/prefill.cpp` と、別実装の `sycl/src/prefill/prefill.cpp` にあります。両者で未設定時の値は通常 1024 ですが、CUDA/HIP 側は CPU prefill share が有効なときだけ別の fallback を使います。

## 値と判定

値は真偽値ではなく、`std::atoll()` で整数 token 数へ変換されます。文字列全体の妥当性検証や clamp はありません。空文字または数字で始まらない文字列は 0 として扱われ、数値の後ろに文字があっても数値部分が使われます。符号や先頭空白も `atoll` の変換に従います。負値もそのまま変数に保持されます。

| 実装・条件 | 未設定 | 設定時 |
|---|---:|---|
| CUDA/HIP: `src/prefill/prefill.cpp` | CPU share が閾値を設定していればその値。そうでなければ 1024 | 変換値が 0 以上ならその値を直接使用。負値なら未設定時と同じ fallback |
| SYCL: `sycl/src/prefill/prefill.cpp` | 1024 | 変換値をそのまま使用。負値も clamp されない |

CUDA/HIP では `STRATA_PREFILL_STREAM_MIN=` や `=abc` は 0 となり、非負 token 数の chunk は閾値を満たします。`=-1` は閾値を無効化する値ではなく、share がない場合は 1024 に戻ります。SYCL では `=-1` が閾値として残ります。異常な負値を渡したときの全後続計算の意味は保証されていません。

根拠: `src/prefill/prefill.cpp:148-153`; `sycl/src/prefill/prefill.cpp:118-122`。

## 有効になる条件

- prefill 経路で GPU cache にない expert を読み込む必要があること。全 expert が GPU cache にある場合は送る expert がなく、閾値を満たしてもコピー対象はありません。
- CUDA/HIP では実際の全 expert stream に `m.ring > STAGE`、`T >= stream_all_min()`、expert source があることが必要です。ring が staging 容量以下なら閾値を満たしても routed-only です。`STRATA_PREFILL_RING`、layer split の ring override、pinned share などが ring 容量を変えます。
- HIP の `STRATA_HIP_WMMA` 経路では、`STRATA_PREFILL_RING` が未設定で ring override もない場合、閾値以上の chunk に 96-slot ring、未満に staging ring を選びます。その他の ring 選択も閾値と chunk サイズを見ます。
- SYCL も threshold を ring slot 選択と stream-all 判定に使います。fused experts のみのスイッチではありませんが、`STRATA_PF_FUSED` が有効な SYCL 経路では fused path の適用下限にもなります。
- `STRATA_PREFILL_EQUAL=1` の chunk 分割は、最後の chunk がこの閾値以上のときに限り均等 chunk へ変更します。閾値未満なら通常の chunk rounding を使います。
- CUDA/HIP の CPU prefill share が有効で、その値が `STRATA_PREFILL_STREAM_MIN` による非負 override で置き換わっていない場合、`arm_cpu_share()` が `STRATA_PREFILL_CPU_SHARE_MAX` を stream 閾値として設定します。share が有効な短い chunk は GPU cache 外の expert を CPU に渡せるため、全 expert を stream する分岐から外れます。share 自体の適用条件は CUDA/HIP 実装と呼び出し元に依存します。

根拠: `src/prefill/prefill.cpp:277-299, 2301-2314, 1918-1931`; `src/program/generate.cpp:6978-6986, 12556-12561`; `sycl/src/prefill/prefill.cpp:204-227`; `src/program/generate.cpp:6333-6349`; `sycl/src/program/generate.cpp:5980-5997`。

## 実行時の詳細

各実装は `stream_all_min()` の関数ローカル `static` として環境変数からの変換値を一度だけ保存します。したがって、最初にこの値を使った後に同一プロセス内で環境を書き換えても、設定値は再読込されません。CUDA/HIP では CPU share が閾値を設定するグローバル値は `Prefill::arm_cpu_share()` で更新されますが、環境変数の明示値が 0 以上ならそちらが優先されます。

CUDA/HIP の prompt chunk は、ring 容量が staging 容量を超え、chunk 長が閾値以上で、expert source がある場合に、GPU cache 外の expert を層順に stream-all します。そうでない chunk は routed-only 側に進みます。SYCL の ring 選択・fused buffer sizing・prefill 実行も同じ閾値関数を参照します。公開 accessor `Prefill::stream_all_min_tokens()` は chunk 計画側から閾値を参照するために使われます。

この変数専用のログ出力は確認できません。値が不正でも警告やエラーを出すコードは見つからず、変換値が各分岐へ使われます。

根拠: `src/prefill/prefill.cpp:148-153, 2301-2303, 1823`; `sycl/src/prefill/prefill.cpp:118-122, 119-121, 1849`。

## 文書との照合

`docs/STRIX_HALO.md:116-125` は、`STRATA_PREFILL_STREAM_MIN=128` で 128〜1,023 token の prompt に fused experts を適用する例と、既定値 1,024 を説明しています。これは fused path の適用下限の一側面について実装と整合します。実装全体では変数は fused 専用ではなく、stream-all の閾値、ring 選択、chunk 計画でも使われます。

`docs/DETAILS.md:1572-1578` の CPU share の説明は、share が有効な CUDA 経路で `STRATA_PREFILL_CPU_SHARE_MAX` が短い chunk の扱いを変える点と一致します。CUDA/HIP 実装では `STRATA_PREFILL_STREAM_MIN` の非負値を指定すると、その閾値が share 由来の値より優先されます。
