# `STRATA_TEST_PINNED_SHARE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata リポジトリの作業ツリーは clean。外部ライブラリの環境変数は対象外。

## 役割

プロンプト処理のリングバッファ sizing に使う「expert blob 全体に対する pinned source の割合」をテスト用の値で置き換えます。`generate.cpp` のコメントは Windows のような ring rule をテストする用途としています。実際の pin 状態やコピー方式を変更する変数ではなく、`Prefill` の sizing 判断に渡す割合を上書きします。

この名前の読み取りは本番ソース `src/program/generate.cpp` に1か所だけあります。テストソース、setup、同梱ツールには読み取りがなく、通常利用者向けの設定として文書化された形跡もありません。環境変数名に `TEST` が含まれるだけでなく、実装コメントもテスト用途を示します。

## 値と判定

`std::atof()` で文字列を `double` に変換します。文字列全体の妥当性は検証せず、変換できない文字列や空文字は `0` になります。数値の後ろに続く文字列は変換結果に影響しません（例: `0.5junk` は `0.5`）。未設定時は環境変数による上書きがなく、実データから割合を計算します。

リング選択では値そのものではなく `share >= 0.9` だけを使います。

| 状態・値 | sizing 上の扱い |
|---|---|
| unset | pinned byte 数 / 全 blob byte 数を使用。全体 byte 数が 0 の場合は `1.0`。 |
| 数値変換結果が `0.9` 以上 | pinned 側の既定リング規則。 |
| 数値変換結果が `0.9` 未満 | unpinned 側の既定リング規則。 |
| 無効な文字列、空文字 | `atof()` の変換結果 `0` となり、unpinned 側。 |

値の範囲制限や clamp はありません。負値も `0.9` 未満として扱われ、`NaN` は比較が偽になるため unpinned 側です。`Inf` などの扱いも `atof()` の変換結果と比較に従います。

## 有効になる条件

- `srcp != nullptr` かつ `o.prefill_chunk > 0` の場合だけ読み取られます。それ以外では、この環境変数は参照されず、`Prefill` の pinned share もこの箇所からは設定されません。
- 設定値が sizing に影響するには、後続処理で `Prefill` のリング規則を既定選択する必要があります。`STRATA_PREFILL_RING` が明示されている場合は `ring_slots()` がその値を先に使うため、既定リング段の選択は置き換えられます。layer split に設定された ring override や auto scan の ring budget もリング数に関与します。
- `STRATA_RING_BYTES=0` は byte-budget ring を無効にします。HIP の一部では `STRATA_HIP_WMMA=1` と ring 未指定時に別の 96-slot 規則が優先されます。
- `generate.cpp` 内でリング設定を参照する初期化より前にこの環境変数を設定しておく必要があります。コードは環境を変更する機能を持ちません。

## 実行時の詳細

`generate.cpp` は、実際の source arena について各 layer/expert の blob byte 数を合計し、`srcp->pinned(l, e)` のものを pinned byte 数に加算します。全体が 0 byte なら比率を `1.0`、それ以外は `pinned / total` とし、環境変数が設定されていれば `atof()` の結果で上書きして `Prefill::set_pinned_share()` に渡します。この setter は `prefill.cpp` のグローバル状態を直接更新し、static cache はしません。

既定リングでは share が `0.9` 以上なら、通常 384 slot、fused ring なら 1024 slot を基準にし、未満なら 96 slot を基準にします。byte-budget ring の byte 数も同じ閾値で変わります。pack による slot 上限、prompt chunk の長さ、ring budget、明示 ring 設定により実際の slot 数はさらに変わるため、環境変数の値がリングサイズを直接指定するわけではありません。

注意点として、`generate.cpp` の split-auto 計画・probe はこの上書き箇所（6297行）より前に pinned share を読む経路があります（3776-3779行、5386-5389行）。その経路が参照する `kAutoLendPct` は static 初期化されるため、`STRATA_TEST_PINNED_SHARE` の値ではなく、その時点の既定 share に基づきます。6297行以降の prompt sizing では上書き後の状態を使います。

環境変数の読み取り自体は stderr/stdout にログを出しません。後続のメモリ計画やリング割り当てが変わりうるものの、ログが出る場合も個別にこの環境変数が原因だと表示する処理はありません。

## 根拠

- `src/program/generate.cpp:6287-6298` — 適用条件、実割合の計算、`getenv` / `atof` による上書き、setter 呼び出し。
- `src/program/generate.cpp:3776-3779,5386-5389` — 上書きより前に share を参照する split-auto の割合設定。
- `src/program/generate.cpp:6351-6363` — 上書き後の既定 lend cap の選択。
- `src/prefill/prefill.cpp:198,245-250,271-298` — pinned share による byte budget / ring slot の既定選択と明示 ring の優先。
- `src/prefill/prefill.cpp:1816-1823,1893-1917` — share setter/getter と、リング sizing が share を参照する関数。
