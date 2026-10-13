# `STRATA_DECODE_TIMING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

serve の各リクエストで decode window の時間内訳を stderr に出す診断用スイッチです。通常の逐次 decode では verify、commit/emit、draft の平均時間と、CPU expert pool、VRAM hit、PCIe などの集計を `strata decode timing:` 行に出します。`--pipeline-windows` 経路では pipeline の追加内訳も出ます。

この変数は timing/profile の出力を切り替えます。decode の計算経路や値を選びません。CUDA/HIP 系実装と SYCL 実装の両方にあります。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_DECODE_TIMING") != nullptr` で設定有無だけを見ます。

| 状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | false | decode timing 行と pipeline 経路の追加 timing 行を出さない |
| 任意の値を設定 | true | 対象出力を有効にする。`1` 以外や空文字、`0` も有効 |

判定結果は関数内の `static const bool` に保存されます。サーバープロセスでは最初にこの箇所が実行された時に一度だけ読み、後から環境を書き換えても再評価されません。

根拠: `src/program/generate.cpp:11135-11138`, `sycl/src/program/generate.cpp:10393-10396`。

## 有効になる条件

- 対象は `--serve` のリクエスト処理です。通常の decode 経路では、処理した decode window が1つ以上あるリクエストで、最後の commit 待ちが成功した後に `strata decode timing:` 行を出します。window がない場合は出力しません。
- `--pipeline-windows` の経路では `STRATA_DECODE_TIMING` により `strata pipeline:` と `strata pipeline classes:` の行も有効になります。
- GPU の各 stage の時間を含む `strata decode GPU stages ...` 行は、独立した `STRATA_VERIFY_PROFILE` が設定されて verifier の計測が有効で、報告可能な window がある場合に出ます。`STRATA_DECODE_TIMING` だけでは GPU stage の計測を有効にしません。
- 各 stage の profile report が空なら、その stage の行は出ません。

`STRATA_VERIFY_PROFILE` も設定有無で判定され、GPU profile 用メモリの確保に失敗すると profile は無効になります。これは `STRATA_DECODE_TIMING` 自体の条件ではなく、GPU stage の内訳に関する条件です。

根拠: `src/program/generate.cpp:12027-12053,11788-11800`, `src/core/verify.cpp:711-715,1801-1803`; SYCL 側は `sycl/src/program/generate.cpp:11277-11300,11080-11092`, `sycl/src/core/verify.cpp:636-646,1642-1644`。

## 実行時の詳細

通常の serve request ごとに、decode 開始時の verifier/drive counters を記録し、window ごとに時間を集計します。リクエストの commit が完了した後、平均時間や window 数、tokens/window、CPU experts と VRAM hits、PCIe などを stderr に出力します。適応 overlap が有効な場合は `strata decode adapt overlap:` 行も同じ出力ブロックに現れます。CUDA/HIP 実装と SYCL 実装でこの処理の大枠は共通です。

`--pipeline-windows` が使われた場合も同じフラグで pipeline 全体と class 別の時間情報を出します。pipeline が使われていない経路ではこれらの追加行は出ません。

GPU stage profile を併用する場合は、verify の stage stamps を集計し、`profile_report()` が `GDN layers`、`QSA layers` などの内訳を返します。CUDA/HIP と SYCL では一部 stage 名が異なります。`docs/DETAILS.md` は `STRATA_DECODE_TIMING=1` と `STRATA_VERIFY_PROFILE=1` の併用を案内し、GPU profile は decode を少し遅くするため速度計測ではなく内訳の比較に使うよう記しています。

根拠: `src/program/generate.cpp:11135-11157,11973-11980,12027-12053`; pipeline 内訳は `src/program/generate.cpp:11788-11800`; SYCL 対応箇所は `sycl/src/program/generate.cpp:10393-10413,11249-11255,11277-11300,11080-11092`; profile 集計は `src/core/verify.cpp:1801-1824`, `sycl/src/core/verify.cpp:1642-1665`; `docs/DETAILS.md:299-306`。

## ログと測定値

出力は stderr です。主な行の接頭辞は `strata decode timing:`、GPU 内訳は `strata decode GPU stages (ms/window):`（追加 stage は `strata decode GPU stages, stage N (ms/window):`）、pipeline 内訳は `strata pipeline:` と `strata pipeline classes:` です。単独の `STRATA_DECODE_TIMING` で速度向上などの測定値が得られるわけではありません。本書では性能値を示しません。

資料: `docs/DETAILS.md:299-306`。
