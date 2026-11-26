# `--adapt-swaps`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`strata generate`） |
| オプション | `--adapt-swaps` |
| 別名 | なし |
| 値 | 整数 `N`。適応ステップで入れ替える expert 数の上限。 |

## 役割

GPU expert cache の適応型 tier が有効なとき、1 回の適応ステップで VRAM cache に入れ替える expert 数の上限を指定する。利用率の高い非 resident expert を、利用率の低い resident expert と交換する。既定値は 96、0 以下なら適応型 tier は無効になる（`engine/src/program/generate.cpp:1045-1047`, `1084-1085`, `15001-15002`）。

## 使い方

```sh
strata generate --pack ./pack/full --tokens "1,2,3" --adapt-swaps 0
```

この例では CUDA/HIP 系 parser で適応 swap を無効にする。`strata generate` の引数形式は `engine/src/program/generate.cpp:1208-1214`、オプションの解析は同 `:4202`。

## 値と既定値

- 指定値は `std::atoi` で整数化され、既定値は `96`。専用の範囲検証は parser にない。値を省略すると `--adapt-swaps needs a value` を stderr に出して終了コード 2 で終了する（`engine/src/program/generate.cpp:1084-1085`, `3844-3847`, `4202`）。
- 数字に変換できない文字列や空文字列は `atoi` の結果 0 として扱われ、適応型 tier を止める。負数も正数条件を満たさず適応型 tier は無効になる。複数回指定した場合は、解析のたびに同じ設定値を更新するため最後の値が残る（同 `:3842-3847`, `4202`, `15001-15002`）。
- 指定値が正でも、適応処理は `--adapt-every` が正で、かつ VRAM cache に空き枠があり全 expert が resident ではない場合などに限られる。0 以下なら使用量カウンタも作られず、swap は実行されない（同 `:15001-15002`, `24570`; 適応周期判定は同 `:22055-22059`, `25188-25191`）。

## 実行時の動作

各適応ステップでは、routing 利用数に基づき不足 expert と追い出し候補を順位付けし、指定数を超える候補を切り詰める。decay は各ステップ後に利用数へ適用される。実際の交換は expert の読み出し元と cache 構成に応じ、CPU/RAM 側の expert と GPU cache の間で行われる（`engine/src/program/generate.cpp:15342-15346`, `15349-15379`）。

CUDA/HIP 系の CUDA 実装では、VRAM cache が全 routed expert の 15% 以上 65% 以下で適応 tier が既に有効なとき、`STRATA_ADAPT_MID` と build 既定値に応じて既定値を `--adapt-swaps 192` に変更する。明示的に `--adapt-swaps` を渡した場合はその値を保持する。この coverage 調整は resident RAM 初期化、serve、非 serve decode の各経路にある（`engine/include/strata/core/adapt_coverage_rules.hpp:20-39`, `engine/src/program/generate.cpp:12145-12164`, `14943-14964`, `24558-24568`）。詳細は [`STRATA_ADAPT_MID`](../../../envvars/STRATA_ADAPT_MID.md)。

`--serve` では、cache coverage が 15% 未満で `STRATA_TINY_CACHE=1` のとき、未指定の既定値を抑制する規則が適用される。resident slot が 0 なら 0、12.5% 未満なら最大 16、12.5% 以上 25% 未満なら最大 32 に抑える。明示値（0 を含む）は保たれる（`engine/src/program/generate.cpp:14965-14973`, `engine/include/strata/core/low_vram_rules.hpp:100-115`）。詳細は [`STRATA_TINY_CACHE`](../../../envvars/STRATA_TINY_CACHE.md)。

`STRATA_EXPERT_NIBBLE` の nibble 経路が起動条件を満たすと、parser 値にかかわらず `adapt_swaps` と `peer_adapt_swaps` を 0 にする（`engine/src/program/generate.cpp:5475-5493`）。

## 適用条件と副作用

適応処理は利用状況に応じて GPU cache の expert residency を変更し、後続の decode / verify 窓で使う expert を変える。peer GPU tier がある場合、peer 側の swap 上限には `--peer-adapt-swaps` が指定されていればその値、未指定なら本オプションの値が渡される（`engine/src/program/generate.cpp:15505-15513`）。

通常の交換バッファ確保では `adapt_swaps` を最大 192 に制限する。確保に失敗し、値が 96 を超えていて未指定の既定値であれば 96 で再試行し、設定値も 96 に下げる。再試行できない場合はエラーを stderr に出して終了コード 1 で失敗する（`engine/src/program/generate.cpp:12166-12189`）。

SYCL parser にも同名引数があり、既定値 96 と `atoi` 変換は同じだが、明示指定を記録する flag や上記 coverage/tiny-cache 補正は確認できない。また SYCL の交換バッファ確保・適応上限は最大 96 である。したがって CUDA/HIP 系の補正規則を SYCL に当てはめない（`engine/sycl/src/program/generate.cpp:721`, `1884-1887`, `2166`, `7126-7129`, `8877`）。

## 出力とエラー

指定値の形式・範囲を理由にした専用 validation error は parser にない。値の欠落時は stderr に `--adapt-swaps needs a value` を出して終了コード 2。resident RAM mode で交換バッファ確保に失敗し、96 件への fallback もできないときは `strata generate: CPU expert residency: ...` を stderr に出して終了コード 1（`engine/src/program/generate.cpp:3844-3847`, `12181-12188`）。

起動時の coverage 補正が値を変更した場合は変更前後の値を stderr に出す。tiny-cache 規則が値を抑制した場合も、その変更を stderr に出す（同 `:12159-12164`, `14965-14973`）。

## 根拠

- parser の既定値・明示指定追跡・引数解析: `engine/src/program/generate.cpp:1084-1085`, `3844-3847`, `4202`
- 適応ステップの候補選定と上限: `engine/src/program/generate.cpp:15342-15379`
- 適応を有効にする条件と周期実行: `engine/src/program/generate.cpp:15001-15002`, `22055-22059`, `25188-25191`
- coverage 補正と tiny-cache 補正: `engine/src/program/generate.cpp:12145-12164`, `14943-14973`, `24558-24570`; `engine/include/strata/core/adapt_coverage_rules.hpp:20-39`; `engine/include/strata/core/low_vram_rules.hpp:100-115`
- peer tier への値の引き渡しと nibble 経路: `engine/src/program/generate.cpp:5475-5493`, `15505-15513`
- SYCL parser / 交換上限: `engine/sycl/src/program/generate.cpp:721`, `2166`, `7126-7129`, `8877`
