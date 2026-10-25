# `STRATA_UMA_RESERVE_GIB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。調査対象ツリーは `main` で、調査開始時点の `git status --short --branch` は `## main...origin/main`（変更なし）。

## 役割

Linux の HIP ビルドで、統合 GPU が使う expert cache の**自動 sizing**に適用するシステム RAM の reserve を GiB 単位で指定します。GPU の空きメモリだけを使った自動 sizing ではなく、OS が報告する利用可能 RAM から reserve を引いた値も sizing 上限にします。`--expert-cache N` で明示した cache 数は変更しません。この変数は、同じ Linux HIP の統合 GPU で手動・自動 cache が現在の host memory headroom を超える場合に出す警告の閾値にも使われます。

## 値と判定

`include/strata/core/uma_cache.hpp:18-26` の `uma_desktop_reserve_bytes()` が `std::getenv()` で値を受け取り、空でない値には `std::strtod()` を適用します。文字列全体の parse 成功は要求せず、少なくとも先頭から数値を一部変換でき（`end != env_gib`）、変換値が `0` 以上なら、その値を GiB 倍して byte 数に変換します。

| 環境値 | reserve |
|---|---|
| 未設定、空文字 | 既定値 `max(8 GiB, total RAM の 8%)` |
| 非負の数値（例 `0`, `2.5`, `1e1`） | 数値 × 1 GiB。小数 GiB も byte に換算し、整数 byte へ切り捨て |
| 数値で始まる後続文字付き値（例 `2GiB`, `2.5x`） | 数値として読めた先頭部分を採用。後続は検査しない |
| 数値に変換できない値、負数、NaN | 既定値へ戻る |

`strtod` のため、符号・小数・指数などの受理は C ライブラリの変換規則に従い、数値全体の書式検証や大文字小文字の比較はありません。reserve に上限 clamp はありません。極端に大きい値は GiB から `uint64_t` への変換可能範囲を超え得るため、その場合の結果はこの実装から保証できません。

## 有効になる条件

- **自動 sizing の変更**は `STRATA_USE_HIP` が定義され、`_WIN32` が未定義のビルドに限られます。さらに、選択中デバイスの properties 取得に成功して `integrated` であり、`host_available_memory()` が成功する必要があります。`o.expert_cache < 0` の自動 cache 経路でだけ、この情報を `free_b` の上限へ反映します（`src/program/generate.cpp:5939-5965`）。
- reserve 後の host memory room が GPU reported free memory (`free_b`) より小さい場合だけ、`free_b` をその room に置き換えます。reserve が `0` のときは条件式が reserve の正値も要求するため、この調整・説明ログは行われず、従来の GPU 空きメモリ基準の sizing になります。
- 置換した `free_b` は、その後 `--vram-reserve-mib`、prompt buffer、draft head、pipeline window 分の reserve を差し引いて slot 数に換算されます。後続 sizing が cache 数を制約することはありますが、`STRATA_UMA_RESERVE_GIB` 自体は明示指定 `--expert-cache N` の値を上書きしません（`src/program/generate.cpp:5972-6015`）。
- **警告閾値**は同じ Linux HIP・統合 GPU・host memory 取得成功条件で参照されますが、自動 sizing の `if (o.expert_cache < 0)` の外にあるため、手動 cache にも適用されます（`src/program/generate.cpp:6016-6034`）。
- CUDA、SYCL、Windows HIP では、これらの呼び出し箇所がコンパイル条件から外れます。ヘッダの helper 自体は共通コードですが、環境変数を読む主な呼び出しは上記の HIP 経路です。

## 実行時の詳細

自動 sizing では、Strata は GPU free bytes を取得した後、統合 GPU と host available memory を確認し、`total_physical_memory()` と環境値から reserve を計算します。room は `available > reserve` なら差分、そうでなければ `0` です。その room が GPU free bytes より小さく、reserve が正なら stderr に次の起動メッセージを出し、以後の expert slot 計算の基準を room に下げます。

```text
strata generate: expert cache auto: this GPU shares system RAM: ... free on the GPU, but the OS has ... available; ... GiB stay for the desktop, so the cache is sized from ... (STRATA_UMA_RESERVE_GIB changes the reserve, --expert-cache N sets the cache)
```

値は static cache されず、helper 呼び出しのたびに `getenv()` から読み直します。通常の generate 起動では自動 sizing 用と host headroom 警告用の両箇所で呼ばれます。

同じ条件で、選択された cache の byte 数が `host available - reserve` を超えると、stderr に `WARNING` を出します。この警告は cache を変更しません。警告文字列は「less 4 GiB for the OS」と固定表示ですが、比較に使う値は同じ環境変数で変わる reserve（未設定時は `max(8 GiB, 8%)`）です。従って表示上の 4 GiB と実際の閾値は一致しない場合があります（`src/program/generate.cpp:6026-6032`）。

## 根拠

- `include/strata/core/uma_cache.hpp:16-31` — 環境値の読み取り、既定 reserve、bytes 変換、room の下限 0。
- `src/program/generate.cpp:5939-5969` — 自動 cache のみの HIP/Linux 統合 GPU 分岐、host-memory 条件、free memory 上限への反映とログ。
- `src/program/generate.cpp:5972-6015` — 調整後の free bytes を slot 数へ換算。
- `src/program/generate.cpp:6016-6034` — 手動 cache にも及ぶ host-headroom 警告と、警告文の固定 `4 GiB` 表記。
- `docs/STRIX_HALO.md:143-150` — 統合 GPU の自動 cache と reserve 変数を説明。ただし「`0` = old sizing」は、自動 sizing で reserve による調整を無効にする意味としてソースと整合します。性能値の記載はなく、この調査でも測定していません。
