# `--spec-fixed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、root） |
| オプション | `--spec-fixed` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

DFly2 speculative decoding の適応制御を無効にし、生成可能な範囲でドラフトしたウィンドウ全体を検証する固定モードにします。通常の適応モードが行う検証幅の選択と、実測速度に応じた plain decode への backoff は行われません。

## 使い方

```sh
strata-hy4 --model model.strata --tokens prompt.txt --gen 128 --draft dfly2 --spec-fixed
```

`--draft dfly2` を指定したオフライン生成例です。`--spec-fixed` 単独では DFly2 drafter の有効化は行いません。サーバーモードでは、たとえば `strata-hy4 --serve --native model.strata --draft dfly2 --spec-fixed` のように指定します。

## 値と既定値

値を取らず、指定すると parser が `SpecCfg::adaptive` を `false` にします。指定しない場合は `SpecCfg` の初期値 `true` のままです。値の検証や数値境界はありません。後ろに別の単語を付けるとそれは別引数として扱われ、未知の引数として終了コード 2 になります。値を必要としないため「値不足」の経路はありません。

## 実行時の動作

- `Spec::choose_k()` と `Spec::choose_m()` は adaptive が false の場合、それぞれドラフト上限 `K` と `TreeSpec` の全検証幅 `tr.M` を返します。したがって `--spec-cut` の信頼度による幅選択もこの分岐では使われません。
- `note_iter()` は adaptive が false の場合に即時 return するため、実測時間から plain decode の連続実行や再プローブを決める backoff 制御は無効です。
- `--spec-k` が同時にある場合はその値が固定検証幅の基礎になります。`Spec` 構築時に `K` は `1..DFLY_KMAX` に丸められ、この実装の初期値は 7 です。コンテキスト上限で生成可能なドラフト長が短くなる場合や `d.can_draft()` が false の場合は plain step に進むため、固定指定があっても常に speculative verify されるとは限りません。
- `--spec-early` の早期終了閾値は `adaptive` が true かつ `cut < 0` などの条件でのみ渡されます。固定モードでは閾値を 0 としてドラフト処理へ渡します。
- `--spec-tree` など他の設定は別途有効です。サーバーでは parser の `SpecCfg` が `ServeOpts::spec` に渡され、実際に drafter の初期化に成功した場合に `Spec` が作られます。オフライン生成では `--draft dfly2`、正の `--gen`、`--dfly-alloc-only` でないことが speculative mode の条件です。

## 適用条件と副作用

このオプションは `Spec` が実行される経路で効果があります。オフライン CLI では `--draft dfly2` と正の `--gen` が必要です。サーバーでは `--draft off` なら適用されず、drafter を開始できない場合も speculative decoder は作られません。サーバーでは chunk が 8 未満の場合、明示的な `--draft dfly2` に対して drafter なしで開始する旨を stderr に出す実装です。

固定モード自体が追加のファイルやネットワーク操作を行う処理は確認できません。効果は推論中の検証制御に限られます。検証窓を適応的に短縮せず backoff もしないため、実行時間や性能が改善するとはソースだけから判断できません。

## 出力とエラー

生成完了時の speculative 統計行は stderr に出力され、`adaptive` が false のとき状態名は `fixed` と表示されます。オプション自体に固有の警告やエラー経路はありません。未知の引数は stderr に `unknown arg ...` を出して終了コード 2 になります。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-364` — `--draft` の初期値と `SpecCfg` の初期化。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,408-414` — 値なしの parser 分岐、関連する `--spec-k` / `--spec-cut` / `--spec-early` の設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数の stderr 出力と終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:550-570,700-715` — サーバーへの設定引き渡し、オフライン speculative mode の条件と drafter 初期化。
- `engine/src/hy4flash/run/hy4_serve.hip.h:320-341` — サーバー側で drafter が利用可能な場合にのみ `Spec` を作る処理、および小さい chunk の扱い。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30,74-91` — `SpecCfg` の既定値、`K` の `DFLY_KMAX` への clamp と下限補正、固定モードの設定反映。
- `engine/src/hy4flash/run/hy4_spec.hip.h:127-133,179-185,216-237,284-288` — 固定モードでの幅選択、backoff 制御の無効化、早期終了閾値の条件。
- `engine/src/hy4flash/run/hy4_spec.hip.h:513-516` — 統計出力の `fixed` / `adaptive` 表示。

調査範囲は索引で `strata-hy4` の root に指定された CUDA/HIP 実装です。索引で別 scope とされる Metal と SYCL の同名フラグの実装差は、本書の対象外です。既存バイナリの `--help` は実行しておらず、parser と実処理をソースで確認しました。
