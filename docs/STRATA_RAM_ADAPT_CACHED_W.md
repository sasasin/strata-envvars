# `STRATA_RAM_ADAPT_CACHED_W`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata serve` の resident RAM 用 adaptive promotion (`STRATA_RAM_ADAPT2`) が、Linux のファイル page cache に全 blob が載っている候補 expert の見込みコストを調整する重みです。RAM に置く候補の選定スコアに掛け、page cache にない候補（ファイルから読む候補）と比べるときに使います。OS の page cache や実際の読み込み方法は変更しません。

この値だけでは機能は有効になりません。`STRATA_RAM_ADAPT2` と正数の `STRATA_RAM_ADAPT` を含む適用条件が必要です。詳しい選定フローは [`STRATA_RAM_ADAPT2.md`](STRATA_RAM_ADAPT2.md) を参照してください。

## 値と判定

`RamAdapt2` の初期値は `0.15f` です。serve の初期化中に環境変数が設定されていれば、`std::atof` で変換し、`std::clamp(..., 0.0, 1.0)` で範囲を制限します。文字列全体の妥当性確認はありません。

| 値 | 設定後の重み |
|---|---:|
| unset | `0.15` |
| 空文字、数値に変換できない文字列 | `0` |
| `0.4tail` | `0.4`（数値部分を変換） |
| `-1` など 0 未満 | `0` |
| `1.4` など 1 超 | `1` |
| 通常の有限数値 0〜1 | その数値 |

`atof` の変換結果をそのまま clamp するため、`nan` のような非数値表記を有限の範囲値へ直す検証はありません。

## 有効になる条件

この重みが候補スコアへ反映されるには、少なくとも次が必要です。

- `STRATA_RAM_ADAPT2` の `atoi` 結果が 0 以外。
- `STRATA_RAM_ADAPT` が正数。
- resident RAM copy が使える単一 GPU の serve で、最初の decode window 後、usage があり、adaptive swap が pending でなく、非同期 adaptive round が idle。
- peer device、remote expert optimization、`--batch` を使っていない。

これらの条件が満たされない場合、この重みは読み込まれても候補選定に使われません。Linux 以外では `tier_of()` は page-cache tier を返さないため、この重みを掛ける候補はありません。

## 実行時の詳細

環境値は `generate.cpp` の `RamAdapt2` を初期化する際に一度読み、状態へ保存します。`static` ではないためプロセス共通のキャッシュではありませんが、その serve 初期化後に環境を書き換えても、既に作られた状態には反映されません。

対象候補は GPU cache 外かつ resident RAM copy にない expert です。そのスコアは decode usage と prompt routing seed の合計から作られます。候補 blob 全体が page cache にある場合 (`tier_of() == 1`) に限り、この値を `STRATA_RAM_ADAPT_CACHED_W` 倍します。Linux の `tier_of()` は `cached_bytes >= total_bytes` で page-cache tier と判定し、非 Linux では resident RAM 以外を tier 2 とします。重みを小さくすると page cache に載った候補の見込みコストが低くなり、RAM promotion の候補順位が下がります。重み 0 なら、その候補の選定スコアは 0 になります。

この重みは page-cache tier の候補だけに掛かり、RAM resident 候補の退避スコア、decode routing、GPU tier の選定規則には掛かりません。候補スコアから promotion 候補を組み合わせた後、利得が 1 未満の組み合わせは除外され、残ったものが `STRATA_RAM_ADAPT` の件数まで I/O thread に stage されます。

## 文書との照合

`docs/DETAILS.md:172-181` は `STRATA_RAM_ADAPT` による同期読み込み方式を説明しています。`STRATA_RAM_ADAPT_CACHED_W` を使う `STRATA_RAM_ADAPT2` の page-cache 候補スコア補正は同資料の記述対象ではありません。同資料の `STRATA_RAM_ADAPT` の測定値を、この重みや新しい promotion 選定方式の効果として扱う根拠は確認できません。

## 根拠

- `src/program/generate.cpp:8266-8283` — `RamAdapt2` の既定値と環境値の `atof` / clamp。
- `src/program/generate.cpp:14801-14813,14820-14829` — promotion の条件、候補の usage スコア。
- `src/program/generate.cpp:14855-14867` — queued 候補の除外、page-cache tier のスコア補正、promotion 利得の判定。
- `src/core/expert_source.cpp:4469-4479` — `tier_of()` が resident RAM、Linux page cache、その他を分類する規則。
- `docs/DETAILS.md:172-181` — 既存資料の `STRATA_RAM_ADAPT` の説明範囲。
