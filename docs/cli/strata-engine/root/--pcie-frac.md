# `--pcie-frac`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root 引数 parser） |
| オプション | `--pcie-frac` |
| 別名 | なし |
| 値 | 数値を取る。未指定時は pack・GPU・リンク測定などから初期 share を決める |

## 役割

各 verify window で、VRAM にない distinct expert miss のうち、GPU が PCIe 経由で読む割合を指定します。残りの miss は CPU pool が計算します。内部では割合を 256 段階の整数にし、router の順で後ろにある miss から PCIe 側へ割り当てます（`src/program/generate.cpp:867-870,12165`, `include/strata/core/expert_source.hpp:612-615`, `src/core/expert_source.cpp:4914-4917,4930-4939,4964-4966`）。

## 使い方

```sh
strata --native /path/to/model.gguf --pack /path/to/model.pack \
  --tokens "1,2,3" --pcie-frac 0.15
```

`--pcie-frac` は `src/program/generate.cpp` のエンジン引数 parser に属します。`strata` は Terminal CLI の同名 wrapper とは別プログラムです（`docs/cli/README.md` の `strata-engine` 対象境界）。

## 値と既定値

- parser は次の argv を `std::atof` で `double` に変換します。option 固有の形式検査や範囲エラーはありません（`src/program/generate.cpp:3295-3298,3502`）。値を省略すると `--pcie-frac needs a value` を stderr に出し、status 2 で終了します（同 `:3295-3297`）。
- 明示値が 0 以上ならその値を使い、実行時の整数化で `round(value * 256)` 相当にして 0〜256 に制限します。したがって有限値の有効 share は 0〜1 に収まり、範囲外の値は実効上 0 または 1 に丸められます（`src/program/generate.cpp:12165,17173-17179,19733-19737`）。
- 0 未満の値は「明示値なし」と同じ判定になり、モデル既定値と probe の経路に入ります（`src/program/generate.cpp:3901-3903,4567`）。数値でない文字列も `atof` の変換結果を使うため、厳密な入力検証はありません。
- 明示値がない場合の開始値は、canonical pack が 0.2、NVFP4 native pack が 0.25、その他 native pack が通常 0.55、HIP gfx12 native pack が条件により 0.15 です。`STRATA_DEFAULTS=026`、`STRATA_PCIE_FRAC_DEFAULT=old` などはこの既定値の選択に関係します（`include/strata/core/defaults_026.hpp:32-39`, `src/program/generate.cpp:2421-2435,4567-4587`）。

## 実行時の動作

起動時に `--pcie-frac` が 0 以上なら `pcie_given` が立ちます。この場合、既定値決定の PCIe link probe と自動 share 調整は行わず、`STRATA_PCIE_BALANCE=1` による測定ベースの share も選ばれません（`src/program/generate.cpp:3901-3903,4567,4613-4620`）。layer split では同じ明示 share を全 stage に使い、各 GPU ごとの probe を飛ばします（同 `:5532-5541`）。

実際に PCIe lane が使われるのは、対象 layer の source が PCIe read に対応し、miss があり、選ばれた expert blob 全体が pinned である場合です。割当対象でも pinned source が得られなければ PCIe fetch にはせず、CPU miss のままです（`src/core/expert_source.cpp:4964-4971,4996-5009`; pinned 判定: `:4700-4713`, `include/strata/core/expert_source.hpp:233`）。`STRATA_ARENA_MMAP=1` の arena は pinned でないため、ソースコメントは `--pcie-frac 0` で実行するよう案内しています（`src/core/expert_source.cpp:5825-5830`）。

serve 経路では、CLI で明示しなかった share に限り、対応条件下で起動時の link probe と CPU pool の測定から PcieAuto が share を調整します。明示値はこの自動調整を無効にします（`src/program/generate.cpp:4585-4610,12142-12165,12218-12245`）。ただし serve の request protocol には request 専用 `pcie_frac=` tuning key があり、値は 0〜1 に clamp されます。request にこの key があれば、その request 中は CLI の share を上書きし、自動調整を pause します（同 `:15118-15129,15169-15170,17173-17179`）。

PCIe 割当数は `floor(nmiss * pcie_num / 256)` を初期値として決まり、ルーティング順の末尾側 miss を GPU に回します。`--pcie-mode` は割当率ではなく、その対象の転送方式を決める別 option です（`src/core/expert_source.cpp:4914-4917,4964-4966`; `src/program/generate.cpp:11265-11269`）。

## 適用条件と副作用

- 対象は主に GPU verifier の expert miss 経路です。resident expert、peer/helper GPU が保持する expert、PCIe read 非対応の source/layer はこの share の対象外です（`src/core/expert_source.cpp:4921-4928,4935-4939,4986-5008`）。
- layer split に明示値を使うと全 stage に共通の割合が適用されます。異なる PCIe link ごとに異なる CLI 値を指定する機能はありません（`src/program/generate.cpp:3901-3903,5532-5541`）。
- CPU pool と GPU lane は native expert の計算丸めが異なることがあり、share を変えると出力 token の値が変わる場合があります。ソースコメントは `--pcie-frac 0.15` と 0.55 の出力差について KL 測定例を記していますが、これは特定機材・prompt の記録であり、性能効果の一般保証ではありません（`src/program/generate.cpp:2421-2428`）。
- `--pcie-frac` 固有の範囲 validator や値不正時の専用エラーはありません。値なしは status 2、未知の option 名は usage を stderr に出して status 2 です（`src/program/generate.cpp:3295-3297,3683-3688`）。

## 根拠

- 値の初期状態・parser: `src/program/generate.cpp:867-872,3295-3298,3502`
- 既定 share と環境設定: `include/strata/core/defaults_026.hpp:32-39`, `src/program/generate.cpp:2421-2435,4567-4611`
- 明示値による probe/balance の抑止と layer split: `src/program/generate.cpp:3901-3903,4613-4620,5532-5541`
- serve の自動調整と request override: `src/program/generate.cpp:12142-12165,12218-12255,15118-15129,15169-15170,17173-17179`
- miss の選定、整数化、pinned 判定、PCIe lane dispatch: `include/strata/core/expert_source.hpp:612-619`, `src/core/expert_source.cpp:4914-4917,4964-5009`
- pinned arena の適用条件: `src/core/expert_source.cpp:4700-4713,5825-5830`
- 値欠落・未知引数の失敗経路: `src/program/generate.cpp:3295-3297,3683-3688`

調査制約: CLI バイナリの `--help` は実行していません。parser と使用箇所をソースで確認しました。Qwen3.5 系 GGUF は main parser より前に family 専用実装へ振り分けられるため、本書は通常の `src/program/generate.cpp` parser の説明であり、専用 parser 上でのこの option の挙動は確認していません（`src/program/generate.cpp:3270-3283`）。Release artifact、GPU/backend 別の実動作、および実性能は確認していません。
