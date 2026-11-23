# `STRATA_EXPERTS_SEQ_READAHEAD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux で `FileExpertSource` が expert ファイルを mmap したとき、マップ全体に `madvise(..., MADV_SEQUENTIAL)` を要求する opt-in の設定です。ファイルから読む byte や expert の計算を Strata 側で切り替えるものではなく、マップされた expert の読み出しに対する advisory を追加します。対象は `experts.bin` と、native pack に `experts.bin` がなく GGUF shard を直接マップする場合です（`engine/src/core/expert_source.cpp:1057-1076,1499-1580,1639-1660,1806-1883`）。

通常の `generate` は expert arena を使い、mmap source は `--mmap-experts` などで選ばれます。したがって環境変数を有効にしても mmap source を使わない実行では効果がありません（`engine/src/program/generate.cpp:872,4213-4249,8550-8560`）。

## 値と判定

Linux では `advise_mapped_experts` の初回呼び出し時に `std::getenv` で読み、値が存在し、かつ先頭 byte が ASCII `'1'` かだけを判定します。文字列全体の parse、数値妥当性検査、空白除去、大文字小文字変換はありません（`engine/src/core/expert_source.cpp:1067-1074`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Linux | 無効 | `1`, `10`, `1anything`（先頭 byte が `1`） | 空文字、`0`, `true`, ` 1`, `01`、先頭 byte が `1` 以外の値 |
| Linux 以外 | 無効 | なし（この helper 内では環境変数を読まない） | すべて |

負数・境界値という数値解釈はなく、文字列先頭の一致だけです。Linux で未設定または先頭が `1` 以外なら何もせず戻り、無効値についての警告や fallback はありません（`engine/src/core/expert_source.cpp:1069-1077`）。

## 有効になる条件

- Strata が Linux 向けにビルドされていること。`getenv` と `madvise` の実処理は `__linux__` guard 内です。
- 実行経路が `FileExpertSource` のファイル mmap に到達すること。通常は `strata generate --mmap-experts` が選択します。`--resident-experts`、`--ssd-experts`、`--resident-budget-gib` の値 0 または正値も parser で `mmap_experts` を有効にします（`engine/src/program/generate.cpp:4213-4249`）。
- expert arena の RAM 不足時に file source へ fallback した場合も対象になります。ただし `--ple-io ram` を明示した場合、`--shared-expert-arena` を指定した場合、または `STRATA_ARENA_RAM_FALLBACK` に空でない値を設定して `atoi` の結果が 0 になる場合（例: `0`, `true`）はこの自動 fallback が許可されません。unset または空文字なら fallback は許可されます。fallback 自体が起きなければ、この設定が呼ばれる mmap 経路もありません（`engine/src/core/ple_residency.hpp:67-74`; `engine/src/program/generate.cpp:8526-8533,8788-8820`）。
- GPU backend、モデル状態、CLI の mmap 選択を超えてこの変数が動作する条件はありません。Windows では helper がコンパイル対象外で、他の非 Windows OS でも helper の Linux 部分は no-op です（`engine/src/core/expert_source.cpp:1057-1084`）。

## 実行時の詳細

pack の `experts.bin` をマップした場合は mmap 成功直後に helper を呼びます。native pack に `experts.bin` がなく GGUF shard を直接読む場合は、各 shard をマップした直後に呼びます。同一 shard は path ごとに一度だけ map されるため、advice もその map ごとに一度です（`engine/src/core/expert_source.cpp:1570-1580,1655-1659,1815-1866`）。

Linux の関数内 `static const bool` が最初の呼び出しで評価されるため、設定値はプロセス内で一度だけ cache されます。プロセス起動後でも最初の mmap より前に値が設定されればその値が使われますが、最初の読み取り後の環境変更は反映されません。この helper は子プロセスを起動せず、環境変数の転送や上書きもしません（`engine/src/core/expert_source.cpp:1067-1074`）。

有効時、各マップの全長に `madvise(view, bytes, MADV_SEQUENTIAL)` を呼びます。戻り値が失敗でも `FileExpertSource::open` を失敗させず、マップはそのまま使います。別の CLI オプションや環境変数がこの helper の判定結果を上書きする処理はありません（`engine/src/core/expert_source.cpp:1073-1076,1655-1660,1857-1863`）。

## ログと測定値

有効値で各マップへの `madvise` が成功すると stderr に次の形式を出します。失敗時は末尾に ` (madvise failed: the default read-ahead stays)` が付き、処理を続けます。無効値や unset ではこのログは出ません（`engine/src/core/expert_source.cpp:1073-1076`）。

```text
FileExpertSource: STRATA_EXPERTS_SEQ_READAHEAD=1: <path> is read with sequential read-ahead
```

`docs/DETAILS.md:328-344` には、RX 6900 XT 16 GB、Ryzen 9 9950X、32 GB RAM、Gyro-M の 29.9 GiB `experts.bin`、NVMe RAID0、Linux 7.2、`--adapt-swaps 0`、各 run 前 cold page cache という一台の測定条件と、5 follow-up turns が unset 時 65.2 / 76.2 秒・有効時 23.5〜28.4 秒などの値が記録されています。これは同資料に記載された実測であり、一般的な性能保証ではありません。ソースのコメントも read-ahead の hint のみが変わり、読み取る byte は同じと説明しています（`engine/src/core/expert_source.cpp:1059-1066`）。

## 根拠

- `engine/src/core/expert_source.cpp:1057-1084` — OS guard、読み取り・cache、判定、madvise、ログ。
- `engine/src/core/expert_source.cpp:1499-1580,1639-1669` — `experts.bin` と native GGUF 経路の選択。
- `engine/src/core/expert_source.cpp:1655-1659,1806-1883` — mmap 成功後の呼び出しと shard ごとの map。
- `engine/src/program/generate.cpp:872,4213-4249,8526-8560,8788-8820`、`engine/include/strata/core/ple_residency.hpp:67-74` — CLI による mmap source 選択と arena fallback 条件。
- `docs/DETAILS.md:324-344` — 測定条件と値（Strata の説明資料。上記ソースの現行実装と区別して記載）。
