# `--expert-cache-device3`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、`root/` scope） |
| オプション | `--expert-cache-device3` |
| 別名 | なし |
| 値 | `N`（slot 数）または `auto` |

## 役割

第3の補助 GPU（通常の device ordinal では CUDA3）に、主 GPU と先行する補助 GPU の cache に入らなかった expert blob を追加で常駐させます。helper cache は routed expert の計算をその GPU 上で行い、計算結果の行を pinned host memory 経由で主側へ返します。これは `strata` のトップレベル引数で、`generate.cpp` の通常 parser が受理します。Qwen3.6 専用 parser の scope ではありません。

## 使い方

```text
strata --serve --pack <pack> --native <model.gguf> --expert-profile <profile> \
  --expert-cache <CUDA0 の slot 数> \
  --expert-cache-device1 <CUDA1 の slot 数> \
  --expert-cache-device2 <CUDA2 の slot 数> \
  --expert-cache-device3 auto
```

device3 は device1 と device2 の後続 tier なので、正の slot 数を割り当てるには先行する二つのオプションにも正の slot 数が必要です。必要な GPU 数、空き VRAM、モデルと profile に合わせて各数値を決めてください。

## 値と既定値

- 値を省略すると parser は `--expert-cache-device3 needs a value` を標準エラーに出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3846`）。
- 未指定時は `Options::expert_cache_remote` の初期値が 0 のため、device3 cache は無効です（`engine/src/program/generate.cpp:903-907`）。
- `N` は `std::atoi` で整数化され、device3 用の配列要素 `r=2` に格納されます。`auto` は slot 値を `INT_MAX`、auto flag を true にします。parser 自体に数値書式や正の上限の厳密な検証はありません（`engine/src/program/generate.cpp:3988-3993`）。
- 変換結果が負なら後段 validation が拒否します。0 は cache を有効にせず、正の値では device1・device2 も正でなければ `invalid sampling or resource parameter` を標準エラーに出し、終了コード 2 になります（`engine/src/program/generate.cpp:5267-5274`）。したがって `--expert-cache-device3 auto` も device1・2 を要します。
- 同じオプションを複数回指定した場合、parser は同じ配列要素を更新するため後の値が残ります（`engine/src/program/generate.cpp:3842-3847,3988-3993`）。

## 実行時の動作

device3 は helper cache 配列の3番目（`r=2`）に対応します。通常は CUDA1、CUDA2、CUDA3 がそれぞれ helper 1〜3 です。`STRATA_PRIMARY_DEVICE` が指定される場合は primary 以外の可視 GPU を順に割り当てます。layer split 併用時には split stage が使わない可視 GPU を順番に割り当てるため、device3 の実際の ordinal は通常時と異なる場合があります（`engine/src/program/generate.cpp:4882-4893,4954-4968`）。

remote cache の初期化には `--expert-profile`、正の CUDA0 `--expert-cache`、expert pool が必要です。profile の順位を基に主 cache や既に別 tier が持つ expert を除外して候補を組み立てます。複数 helper が使われる場合、既定の `stripe` 配置では候補を各 cache の slot 数に応じて振り分け、`--expert-cache-remote-placement layer` では layer ごとに担当を決めます（`engine/src/program/generate.cpp:10123-10153,10155-10196`）。device3 の open が成功すると、選択した expert blob を GPU cache に割り当てて読み込み、最初の slot を検証します。各 routed layer では helper が対象 expert の行を計算し、完了時に pinned host row から出力へ戻します（`engine/src/program/generate.cpp:10197-10207`; `engine/src/core/remote_experts.cpp:136-205,265-359,361-391`）。

`auto` は profile に含まれない expert も候補に加え、実際の expert blob サイズと helper GPU の空き VRAMを見て cache 容量を決めます。slot 数の上限は全候補数でも制約され、主 cache や split stage が保持する expert は重複配置しません（`engine/src/program/generate.cpp:10139-10153,10192-10201`; `engine/src/core/remote_experts.cpp:153-175`）。

## 適用条件と副作用

- GPU helper cache のため、指定 device が可視で、正の slot 数に応じた VRAM が必要です。layer split と併用する場合、各 helper に split stage が使わない可視 GPU が必要です。足りない場合は `--expert-cache-remote with a layer split needs a GPU that runs no stage` を出して終了コード 2 になります（`engine/src/program/generate.cpp:4954-4968`）。
- `--peer-device` は helper cache と同時に使えません。device3 を有効化すると device1・2 も正になるため、peer tier との競合 validation に該当し、エラー終了します（`engine/src/program/generate.cpp:5284-5290`）。
- cache open 時に可視 GPU、cache slot、profile 順位、未割当 expert が確認されます。`auto` は空き VRAMから 512 MiB を残す容量だけ選びます。明示 slot 数でも 512 MiB を残せなければ `reduce --expert-cache-device3` を含むエラーで初期化を中止します（`engine/src/core/remote_experts.cpp:141-175,182-205`）。
- device3 の cache slot と helper の入力・出力 staging、stream、scratch 等の GPU/host memory が起動時に確保されます。起動 preflight や cache 構築で失敗するとエラーを標準エラーに出して終了し、cache open 中の失敗経路では確保済み資源を閉じます（`engine/src/program/generate.cpp:5511-5525,10197-10207`; `engine/src/core/remote_experts.cpp:100-134,207-225`）。
- helper cache がある構成では、prompt を別 thread で並行読込する経路が無効になります。また SYCL の自動 pipeline 条件も helper cache があると成立しません（`engine/src/program/generate.cpp:21037-21038`; `engine/include/strata/program/batch_read.hpp:30-52`; `engine/sycl/include/strata/pipeline_auto.hpp:24-29`）。
- `--remote-expert-opt` は `--serve` が必要です。remote helper tier に付ける追加最適化ですが、このオプション単体では有効になりません（`engine/src/program/generate.cpp:3994,5280-5283,10123-10125,10197-10201`）。

## 出力とエラー

成功時は、profile の拡張ランキングや helper への振り分けについて標準エラーにログを出し、各 device の実際に常駐した expert 数と GiB、結果が pinned host rows 経由で戻ることを表示します（`engine/src/program/generate.cpp:10139-10153,10187-10188,10202-10207`）。

主な失敗経路は、値なし（終了コード 2）、負数または device1・2 の slot 数不足（終了コード 2）、必要な profile / CUDA0 cache / expert pool の不足（終了コード 2）、layer split 用 helper GPU 不足（終了コード 2）、GPU 問合せ・VRAM・cache 確保・blob 読込や検証の失敗（終了コード 1）です。後者は `RemoteExperts::open` のエラー文字列を `strata generate:` 付きで標準エラーに出します（`engine/src/program/generate.cpp:10127-10203`; `engine/src/core/remote_experts.cpp:141-205`）。

## 根拠

- `engine/src/program/generate.cpp:903-907` — slot 数・auto flag の初期値と helper tier の設定。
- `engine/src/program/generate.cpp:1416-1428` — CLI usage にある device1〜3 の値形式と peer tier との非併用条件。
- `engine/src/program/generate.cpp:3842-3847,3988-3993` — 引数値の取得、共通 parser、device3 の配列添字と変換。
- `engine/src/program/generate.cpp:4882-4893,4954-4968` — helper device ordinal の割当と layer split 時の条件。
- `engine/src/program/generate.cpp:5267-5290` — slot 値・tier 順序、remote optimization、peer tier の validation。
- `engine/src/program/generate.cpp:10123-10207` — profile 候補の準備、multi-helper 配置、cache open と成功・失敗ログ。
- `engine/src/core/remote_experts.cpp:136-205,265-359,361-391` — helper cache の容量決定・確保・充填と expert 計算・結果返却。
- `engine/src/program/generate.cpp:21037-21038`, `engine/include/strata/program/batch_read.hpp:30-52`, `engine/sycl/include/strata/pipeline_auto.hpp:24-29` — helper cache の prompt read / pipeline 条件への反映。

調査範囲は上記 commit の parser、通常エンジンの helper cache 初期化・実行経路と関連条件です。GPU の実機可視性、driver/runtime のメモリ挙動、個別 build 構成での実行可否はソース確認だけでは確定できないため、ここでは記載していません。
