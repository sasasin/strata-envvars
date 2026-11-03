# `DS4_STREAM_DIRECT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Maya DS4.1 の decode PCIe lane が統合 GPU で使う pinned staging slot の扱いを選びます。direct mode では GPU kernel が pinned staging をそのまま読み、copy mode では VRAM staging slot にコピーしてから同じ expert kernel で計算します。これは expert の CPU/GPU 分担を決める環境変数ではなく、起動時の lane 計時で比較する二つの経路を制限する設定です。

## 値と判定

実装は `std::atoi` の戻り値が 0 かどうかだけを見ます。文字列全体の検証や範囲チェックはありません。

| 値 | 新規計時時の扱い |
| --- | --- |
| 未設定 | 統合 GPU で direct と copy の両方を計時し、速い方を採用 |
| `atoi(value) == 0` | direct を計時せず copy mode を計時 |
| `atoi(value) != 0` | direct mode だけを計時。copy mode は計時しない |

`0`, `00`, 空文字、数字で始まらない文字列は copy mode 側です。`1`, `-1`, `2`, `1tail` など `atoi` が非ゼロを返す値は direct 側です。先頭の空白や符号を含む整数表記も `atoi` の規則で変換され、後続文字は検査されません。数値範囲外の文字列に対する `atoi` の結果は移植可能な設定手段として扱えません。

## 有効になる条件

- `strata-dsv41` の Maya DS4.1 実装で使われます（`CMakeLists.txt:943`）。
- GGUF で、PCIe lane が無効でなく、token decode 経路であり、同期 decode でない場合に lane allocation/setup へ進みます。lane 自体は `DS4_STREAM`（なければ `STRATA_DS4_STREAM`）による opt-in です。
- layer が lane 対象（MXFP4、単一 MoE、pick 数が対応範囲内）で、GPU に全 expert を置けず、pinned staging をその GPU がアドレスできる必要があります。
- `DS4_STREAM_DIRECT` が分岐に作用するのは、統合 GPU かつ `host_dev` が利用でき、新規計時でその GPU の mode がまだ選択されていない場合です。離散 GPU では直接読み取り比較をせず copy mode になります。
- 有効な lane-times calibration があり、その direct/copy mode が現状の GPU で再確認できれば、記録済み mode が使われ、この環境変数の値は参照されません。`DS4_STREAM_FORCE` が設定されるとその calibration lookup は省略されます。

## 実行時の詳細

モデルの load 処理で `lane_setup()` が呼ばれ、lane の適格性・pinned host pointer を確認した後、format class ごとの計時を行います。`DS4_STREAM_DIRECT` はこの計時ループ内で読み取られ、`static` cache には保存されません。同じ GPU の最初の class で mode が確定すると、後続 class はその GPU 共通の mode で計時され、変数を再読しません。通常の実行中に環境を書き換えても、既に終わった load 時の選択は変わりません。

未設定の統合 GPU では direct/copy の両方について lane cost を計時し、`pcie::split` の推定値が小さい方を採用します。値が非ゼロなら direct 候補のみ、ゼロなら copy 候補のみを計時し、二方式の比較はしません。選択された mode は同じ GPU の後続 class に共有され、calibration file が有効なら lane calibration file に記録されます。direct mode では decode plan の slot pointer が pinned host staging を指し、fetch kernel への `copy` 引数は false です。copy mode では plan は VRAM slot を指し、fetch kernel が staging からコピーします。lane が使われない経路では `DS4_STREAM_DIRECT` は効果を持ちません。

既存 calibration の再確認に失敗すると `the times file's ... do not hold now ... - timed again` が stderr に出て再計時します。計時に失敗した場合は `timing failed - the CPU lane alone`、pinned staging を device がアドレスできない場合は `cannot address the pinned slots - its CPU lane alone` が stderr に出ます。成功時の lane summary には direct mode のとき `read in place` と表示されます。`DS4_STREAM_DIRECT` 自体の値を報告する専用ログはありません。

## 根拠

- 候補の説明と `LaneDev` の direct flag / slot pointer: `src/dsv41/ds4_model.cu:9604-9639`。
- `DS4_STREAM` / `STRATA_DS4_STREAM` による lane opt-in と lane allocation 条件: `src/dsv41/ds4_model.cu:9711-9719,9753-9757`。
- lane layer 条件、GPU の integrated 判定、pinned host pointer の設定: `src/dsv41/ds4_model.cu:9722-9725,9789-9794,10469-10478`。
- load 時の呼び出し順: `src/dsv41/ds4_model.cu:3789-3793`。
- cached calibration の採用条件と `DS4_STREAM_DIRECT` の `atoi` 分岐・比較計時・fallback: `src/dsv41/ds4_model.cu:10520-10589`。
- fetch の copy flag、kernel slot pointer、direct mode の calibration 保存とログ: `src/dsv41/ds4_model.cu:10303-10312,10330-10336,10604-10613,10631-10642`; fetch kernel 呼び出し: `src/dsv41/ds4_pcie.cuh:150-160`。
- 対象 executable のソース構成: `CMakeLists.txt:943`。
