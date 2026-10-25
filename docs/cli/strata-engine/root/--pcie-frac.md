# `--pcie-frac`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--pcie-frac` |
| 別名 | なし |
| 値 | 数値。parser は `double` に `std::atof` で変換する。通常の指定範囲は 0〜1。 |

## 役割

serve の decode verify window で、GPU cache にない distinct expert のうち、PCIe 経由で GPU が pinned host arena から読む割合を指定します。残りの miss は CPU expert pool が計算します。値は expert 数の比率であり、PCIe 帯域や GPU cache 容量そのものを指定するものではありません（`src/program/generate.cpp:682-685`、`src/core/expert_source.cpp:4828-4830`）。

## 使い方

```sh
engine/strata --serve --pack ./packs/model --native ./models/model.gguf --pcie-frac 0.25
```

この例は native model を serve し、PCIe へ割り当てる miss の割合を 0.25 にします。モデルや pack の指定は実際の配置に合わせてください。

## 値と既定値

- `--pcie-frac VALUE` の `VALUE` は `std::atof` で読み取られます。空値や数値として解釈できない文字列について独自の validation はなく、`atof` が返す 0 が設定されます（`src/program/generate.cpp:2420-2429`、`src/program/generate.cpp:2623-2626`）。
- 値が負数なら parser は拒否せず、後段の `pcie_frac < 0.0` 分岐で「未指定」と同じ自動既定値処理に入ります（`src/program/generate.cpp:3557-3558`）。0 は有効な明示値で、PCIe share を実質 0 にします。
- 指定値の 0〜1 範囲を parser で検証する処理はありません。serve の通常 dispatch では `pcie_frac * 256` を整数化した後に 0〜256 へ clamp します（`src/program/generate.cpp:9977`、`src/program/generate.cpp:13965`、`src/program/generate.cpp:16177`）。従って有限の値であれば範囲外も起動時にエラーにならず、負値は既定値分岐、1 より大きい値は実行時の最大 share に収まります。非有限値の変換結果はソースから安全な挙動を確認できないため、指定値として扱わないでください。
- 省略時の基準値は canonical Q2_0 pack が 0.2、native NVFP4 pack が 0.25、その他 native pack が 0.55 です。native pack では起動時に PCIe host-to-device 帯域を probe し、測定値が 20 GB/s 未満なら基準値に帯域比を掛けます。probe 失敗時は基準値を使います（`src/program/generate.cpp:3552-3557`、`src/program/generate.cpp:3587-3598`、`src/program/generate.cpp:2066-2070`）。
- 値を明示すると `pcie_frac >= 0.0` となり、起動時の share probe/default 決定を通らず、この値が各 stage の share として使われます（`src/program/generate.cpp:2975-2977`、`src/program/generate.cpp:4384-4393`）。

## 実行時の動作

dispatch は各 verify window で routed expert を重複排除し、VRAM resident・peer GPU・helper GPU が持つ expert を miss から除外します。残った miss 数に対し、share を 1/256 単位へ丸めて PCIe lane に割り当てる個数を決めます。PCIe 対象は routing 順の後ろ側です（`src/core/expert_source.cpp:4832-4844`、`src/core/expert_source.cpp:4877-4884`、`src/core/expert_source.cpp:4900-4910`）。

PCIe lane に選ばれた miss でも、source が pinned host memory を持つ場合だけ GPU fetch へ進みます。pinned でなければ `kd` は miss のままで、後続の CPU 経路が処理します（`src/core/expert_source.cpp:4906-4917`）。`--pcie-mode` は PCIe fetch の DMA / direct / kernel 経路を選ぶ別設定で、この option の share 値を変更しません（`src/program/generate.cpp:2633-2637`、`src/program/generate.cpp:16160-16179`）。

省略時の自動調整は backend・環境条件で異なります。CUDA 等の条件を満たす単一 GPU serve では、probe した share を最初の decode windows の CPU pool 実測に基づいて更新し、その変更を stderr に出します。明示指定時は `pcie_frac_auto` が立たず、この起動後の自動調整を有効にしません（`src/program/generate.cpp:3580-3595`、`src/program/generate.cpp:10031-10054`）。layer split で値を明示した場合は全 stage に共通の値となり、stage ごとの PCIe probe を省略します。省略時は native pack の各 stage が自身の link を probe します（`src/program/generate.cpp:2975-2977`、`src/program/generate.cpp:4384-4393`）。

serve の request line に `pcie_frac=...` が含まれる場合は、request ごとの値が 0〜1 に clamp され、CLI 起動時の share に優先して適用されます。layer split では request override が後段 stage にも適用されます（`src/program/generate.cpp:12317`、`src/program/generate.cpp:12350`、`src/program/generate.cpp:13965-13970`）。

## 適用条件と副作用

- 効果があるのは GPU verifier の expert miss を PCIe lane と CPU pool に分ける serve/decode 経路です。resident experts、peer/helper GPU が処理する expert、または miss のない window には PCIe 分担が発生しません（`src/core/expert_source.cpp:4832-4844`、`src/core/expert_source.cpp:4877-4884`）。
- 明示値はすべての layer split stage に共通です。異なる link 帯域の stage ごとに別値を CLI から設定する機能は、この parser にはありません（`src/program/generate.cpp:2975-2977`）。
- 明示値があると `STRATA_PCIE_BALANCE=1` による測定ベースの share 決定は無効です（`pcie_balance()` が `!pcie_given` を条件にするため）。一方、`STRATA_PCIE_MIN1` が有効で、1 層に 2 件以上の miss があり PCIe lane が使える場合は、計算 share が 0 に丸まっても最低 1 件を PCIe に割り当てることがあります（`src/program/generate.cpp:3601-3607`、`src/core/expert_source.cpp:4877-4884`）。
- share を増やすと、より多くの pinned host expert を GPU が PCIe から読み、CPU が計算する miss 数は減ります。これは実行経路を変える設定であり、性能改善の保証はソースからは導けません。
- 本ソース checkout の `usage()` 文字列には `--pcie-frac` の説明が見当たらず、`--help` だけではこの option を確認できません。一方、parser には定義があります（parser: `src/program/generate.cpp:2625`、help 実装: `src/program/generate.cpp:2423`）。
- `--native` の model が Qwen35 family と判定されると、通常 parser より前に専用 `src/qwen35` 実装へ全 argv が委譲されます。その family parser における `--pcie-frac` の受理・効果は本書の通常 engine parser の調査範囲外です（`src/program/generate.cpp:2394-2410`）。

## 出力とエラー

- `--pcie-frac` の値がない場合、共通の `next()` が `--pcie-frac needs a value` を stderr に出して exit code 2 で終了します（`src/program/generate.cpp:2420-2429`）。
- 数値の範囲外や不正な数値文字列について、この option 専用の parser error / warning はありません。未知 option は `unknown argument: ...` と usage を stderr に出し code 2 で終了します（`src/program/generate.cpp:2788-2792`）。
- 省略時の probe は pinned host buffer と device buffer を確保し、256 MiB copy を測定してから両 buffer を解放します。確保・測定失敗時は probe が失敗値を返し、既定 share に fallback します（`src/program/generate.cpp:2073-2114`、`src/program/generate.cpp:3597-3598`）。明示値ではこの起動時 probe を行いません。

## 根拠

- parser と値変換: `src/program/generate.cpp:2420-2429`, `src/program/generate.cpp:2623-2626`
- default / PCIe probe / 起動後の自動調整: `src/program/generate.cpp:3552-3600`, `src/program/generate.cpp:10031-10054`
- layer split の stage share: `src/program/generate.cpp:2975-2977`, `src/program/generate.cpp:4384-4393`
- 実際の miss 分類・PCIe fetch・pinned 条件: `src/core/expert_source.cpp:4828-4830`, `src/core/expert_source.cpp:4877-4917`
- request 単位 override: `src/program/generate.cpp:12317-12350`, `src/program/generate.cpp:13965-13970`
- help / family dispatch: `src/program/generate.cpp:2394-2423`
