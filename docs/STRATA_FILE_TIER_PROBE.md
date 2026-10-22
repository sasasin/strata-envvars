# `STRATA_FILE_TIER_PROBE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Linux の `--mmap-experts` と resident budget を使う経路で、ページキャッシュに読み戻し対象の半分未満しか置けないと見積もられた場合に行う、起動時の file-tier 速度測定を抑止できます。測定結果は unbuffered read（`O_DIRECT`）と mmap 経由の cached read のどちらを使うか決めるために使われます。この変数は選択を直接指定せず、`0` で測定を無効にするだけです。

## 値と判定

| 値 | 測定を抑止するか |
|---|---|
| 未設定 | 抑止しない |
| 空文字 | 抑止しない（先頭文字は `\0` で `0` ではない） |
| 先頭文字が `0`（例: `0`, `00`, `0abc`） | 抑止する |
| それ以外（例: `1`, `false`, `abc`, 空白始まり） | 抑止しない |

値全体の parse、数値変換、大文字小文字変換はありません。読み取り箇所は `getenv()` で、その値の先頭文字だけを比較します。環境変数を読んだ時点で `0` 以外でも、後述の条件が合わなければ測定自体は行いません。

## 有効になる条件

この変数が参照されるのは Linux の `file_tier_unbuffered()` です。さらに以下がすべて成立するときだけ測定の可否に影響します。

- room rule が cached read を選ぶ（`keepable` が真）。
- `STRATA_FILE_CACHE_OLD_RULE` による旧 room rule が選ばれていない。
- file tier の読み取り対象が 0 byte より大きい。
- 利用可能 RAM から RAM copy と 1 GiB の余裕を引いた後の保持可能量が、読み取り対象の半分未満（`held < 0.5`）。

`--mmap-experts` かつ `--resident-budget-gib` がある場合、`FileExpertSource::set_unbuffered()` から起動時の判定に到達します。resident RAM copy 構築後、条件により `recheck_unbuffered()` が再判定します。budget なしの経路ではこの probe に到達しません。Windows は `experts_unbuffered()` を使い、macOS など Linux/Windows 以外では file tier を buffered とするため、この変数を読みません。

## 実行時の詳細

測定は最大サイズのファイル一つを使い、ページキャッシュに載っていないランダムな 1 MiB 領域を direct read（8 thread）と mmap の初回ページ読み込み（3 thread）で読みます。各方式を2 round実行し、各 pass は最大1.5秒です。成功した場合は取得した帯域と保持可能割合から選択し、その説明を file-tier の理由文字列へ加えます。direct read を選ぶには direct 側が 4 GB/s 以上であることが必要で、保持割合が30%未満なら direct が cached の1.3倍以上、30%以上50%未満なら1.5倍以上速い必要があります。基準を満たさなければ file cache を維持します。

測定対象のファイルがない、最大ファイルが小さすぎる、`O_DIRECT` で開けないなど測定できない場合も file cache を維持し、理由に `the drive probe could not run, the file cache stays` を加えます。起動時の選択理由は `strata generate: the file tier reads ...` の stderr ログに出ます。環境変数の判定自体は呼び出しごとに行われ、`static` cache されません。一方、測定結果は mutex 保護された process 内 memo に一度だけ保存されるため、最初の測定が失敗しても同一 process 内では再試行しません。

測定はファイルキャッシュを使うページを `madvise(..., MADV_DONTNEED)` と `posix_fadvise(..., POSIX_FADV_DONTNEED)` で解放するよう試みます。測定値やその性能上の有効性はドライブ・負荷に依存します。release note は PCIe 5 の約8 GB/s drive の報告を導入動機として記載し、測定した 1.6–3.1 GB/s の drive では file cache を選び、4 GB/s 超の drive では未検証と明記しています。これらは release note の記載であり、本調査で性能を再測定したものではありません。

## 根拠

- `src/core/expert_source.cpp:747-858` — Linux 専用 probe、サイズ最大ファイルの選択、測定方式・回数・時間制限、process 内 memo。
- `src/core/expert_source.cpp:861-930` — 環境変数の読み取り、`held` 計算、適用条件、probe 失敗時の fallback、および Windows/Linux/その他 platform 分岐。
- `src/core/expert_source.cpp:2474-2523` — 起動時 `set_unbuffered()` と RAM copy 後の `recheck_unbuffered()`。
- `include/strata/platform/memory.hpp:63-78` — direct read の帯域・相対速度の採用基準。
- `src/program/generate.cpp:5610-5641,8168-8178` — `--mmap-experts` / resident budget の呼び出し箇所と stderr 出力。
- `docs/release-notes-0.2.1.md:49,93` — 変更の説明、記載された観測と未検証範囲。
