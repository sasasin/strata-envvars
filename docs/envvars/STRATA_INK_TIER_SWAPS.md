# `STRATA_INK_TIER_SWAPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2-Mini CUDA hybrid 実装の適応型 expert tier について、1 回の tier round で許す swap 数の基準値を設定しようとする変数です。ただし、この commit では値を読む順序が遅く、実際のポリシーには反映されません。`InkHybridEngine::tier_plan()` が `tier_swaps_per_round`（初期値 16）から各 expert サイズ class の `cfg.swaps_cap` を計算して `tc.pol.init()` にコピーした後で、`tier_alloc()` がこの環境変数を読みます。後からメンバーを書き換えても初期化済みポリシーの設定は変わらないため、実際の swap 上限は環境変数の値ではなく、計画時の初期値 16 を基準に決まります（[ink_hybrid.cuh:2169-2171](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_hybrid.cuh:2255-2262](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_hybrid.cuh:2288-2295](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_expert_policy.hpp:48-50](../../../../Niko1221/Strata/engine/include/strata/core/ink_expert_policy.hpp)）。

変数がセットされると、その値は tier 開始時の stderr ログ `; a round every %d tokens, %d swaps` に表示されます。したがってログ上の swap 数表示と、ポリシーに実際に設定された上限が食い違うことがあります（[ink_hybrid.cuh:2291-2296](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)）。

## 値と判定

`tier_alloc()` で `std::getenv` の設定有無を確認し、値があれば `std::atoi` で整数変換した後、`std::max(1, ...)` で最低 1 にします。文字列全体の妥当性確認やエラー処理はありません。`atoi` が読み取れる先頭の整数部分を使うため、先頭空白は許容され、数値の後ろの文字は無視されます。数値に変換できない文字列や空文字は 0 となり、1 に丸められます。整数として表現できない入力に対する `atoi` の結果はこのコードで定義されていません（[ink_hybrid.cuh:2288-2289](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)）。

| 条件 | unset | 有効になる値（変数に保存される値） | 無効な入力・境界例 |
|---|---:|---|---|
| CUDA hybrid tier の初期化 | 初期値 `16` | `atoi` の結果が 1 以上ならその整数（例: `3`, `3x` → `3`） | ``, `abc`, `0`, `0x`, `-2` はいずれも 1 に clamp。大きすぎて `int` に収まらない入力は `atoi` の範囲外で結果不定 |

このメンバー値は初期化ログには使われますが、ポリシーの swap 上限には使われません。ポリシー側では計画時に class ごとの slot 比率で基準値を配分し、さらに `ink_policy_swaps_cap()` が resident 比率に応じて上限を絞ります（resident が全体の 12.5% 未満なら最大 16、25% 未満なら最大 32）。どちらの制限も、この変数の値を読む前に設定されています（[ink_hybrid.cuh:2255-2262](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_expert_policy.hpp:29-35](../../../../Niko1221/Strata/engine/include/strata/core/ink_expert_policy.hpp)、[ink_expert_policy.hpp:91-108](../../../../Niko1221/Strata/engine/include/strata/core/ink_expert_policy.hpp)）。

## 有効になる条件

- `engine/src/inkling2/cuda/ink_hybrid.cuh` を使う CUDA Inkling-2-Mini 実行経路であること。この名前の実コード参照は同ファイルの `getenv` だけで、HIP 実装に同名参照はありません（[ink_hybrid.cuh:2289](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_runner.cuh:9-10](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)）。
- 適応型 tier 自体が選ばれること。実装は `STRATA_INK_TIER` が未設定、または先頭文字が `'0'` でない場合に tier を許可します。値全体の比較ではないため、`0anything` は無効化、空文字や `false` は無効化しません（[ink_hybrid.cuh:2185-2188](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)）。
- CUDA runner の配置条件を満たすこと。通常の経路では VRAM とホスト RAM の両方に expert 配置があり SSD 配置がなく、RAM にカード上 expert の追加コピーを置ける必要があります（[ink_runner.cuh:452-479](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)）。別の配置経路では layer split と dual-GPU expert parallelism が無効、SSD 配置がなく、ホスト側に expert があり、カード側 expert もあることが必要です（[ink_runner.cuh:1342-1352](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)）。
- tier plan の slot pool が `tier_alloc()` で確保できること。tier が成立しない場合、変数は読まれず、caller は `[InkTier] off: ...` の理由を stderr に出して tier を無効にします（[ink_hybrid.cuh:2269-2271](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_runner.cuh:504-522](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)、[ink_runner.cuh:1383-1400](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)）。
- 上記を満たしても、現状では読み取りが `tier_plan()` 後なので、環境変数はポリシーの実動作を変更しません。CLI 引数や設定ファイルによる優先順位も、この変数については実装されていません。

## 実行時の詳細

両方の runner 経路は、条件成立時に `hybrid.tier_plan(...)` を呼び、その後 staging buffer を準備して `hybrid.tier_alloc()` を呼びます（[ink_runner.cuh:481-505](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)、[ink_runner.cuh:1354-1384](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_runner.cuh)）。計画段階では、初期値 16 を各サイズ class の slot 数に応じて配分した `cfg.swaps_cap` を作り、`InkExpertPolicy::init()` が構成を内部コピーします（[ink_hybrid.cuh:2170-2171](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_hybrid.cuh:2255-2262](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_expert_policy.hpp:48-50](../../../../Niko1221/Strata/engine/include/strata/core/ink_expert_policy.hpp)）。その後 `tier_alloc()` が環境値を読み、メンバー `tier_swaps_per_round` を更新しますが、以降そのメンバーの参照は開始ログだけです（[ink_hybrid.cuh:2288-2295](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)）。

環境値は tier 初期化時に一度読み取られ、リクエストごとの再読込や static cache はありません。実際の round は decode step の後に定期的に走り、各 `tc.pol.round()` が事前にコピーされた `cfg_.swaps_cap` を使います（[ink_hybrid.cuh:2313-2326](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_expert_policy.hpp:91-108](../../../../Niko1221/Strata/engine/include/strata/core/ink_expert_policy.hpp)）。この変数が token の選択・生成内容・実際の swap 数を変える経路は、対象 commit では確認できません。

## ログと測定値

成功時は stderr に `[InkTier] adaptive expert tier on: ...` と、続く `; a round every %d tokens, %d swaps` が出ます。後者の swaps 表示は環境変数で変更されますが、ポリシー上限の実値を示すものではありません（[ink_hybrid.cuh:2291-2296](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)）。tier round の実 swap 数は `[InkTier] round %llu: %d swaps (total %llu)` として stderr に出ますが、これは `STRATA_INK_TIER_LOG` が設定され、round 数が 64 で割って 1 余る場合だけです（[ink_hybrid.cuh:2290](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)、[ink_hybrid.cuh:2355-2358](../../../../Niko1221/Strata/engine/src/inkling2/cuda/ink_hybrid.cuh)）。

## 根拠

- 変数の唯一のソース参照とログ: `engine/src/inkling2/cuda/ink_hybrid.cuh:2288-2296`
- ポリシー上限の作成、初期化、round 時の適用: `engine/src/inkling2/cuda/ink_hybrid.cuh:2255-2262`; `engine/include/strata/core/ink_expert_policy.hpp:48-50,91-108`
- 2 つの CUDA runner 経路での計画・割り当て順序と tier 条件: `engine/src/inkling2/cuda/ink_runner.cuh:470-505,1342-1384`
- tier 自体の `STRATA_INK_TIER` 判定: `engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2188`
