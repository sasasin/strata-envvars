# `STRATA_RAM_KEEP_GIB`

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

expert arena（expert 全体を起動時に RAM へ読み込む領域）の判定で、ロード後も RAM を指定量残す設定。値は GiB で、内部では byte 数に変換する。arena が使えない場合の RAM copy にも headroom として反映される。対象は strata generate の expert 初期化経路であり、生成 token や expert 選択を変える設定ではない（engine/src/program/generate.cpp:4277-4285; engine/include/strata/core/ple_residency.hpp:140-155）。

デスクトップ host は Work プロファイルで対応 engine（0.1.56 以上）を起動する際、ユーザー指定の RAM setting / mode がなければ、この変数を run config の起動環境に設定する。値は総 RAM の 20% を切り上げ、5〜8 GiB に制限する。Full performance と strata serve には自動設定しない（app/host/server/native-resources.mjs:89-112,130-158）。

## 値と判定

argv の解析後に一度 getenv で読み取る。--ram-keep-gib W が指定されている場合は環境値を無視し、CLI が優先する。CLI の W=0 も環境値に優先する。CLI 指定がない場合、未設定・空文字・atof の結果が 0 以下なら既定値 0 GiB のまま（engine/src/program/generate.cpp:4230-4235,4277-4285）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効・無効果になる値（例） |
|---|---|---|---|
| CLI flag なし | 0 GiB | 1, 2.5, 2GiB（数値 prefix の 2）, 前後に空白のある数値 | 0, 0anything, -1, true, abc。atof の結果が正でなければ適用しない |
| --ram-keep-gib W あり | 環境値を無視 | CLI の W >= 0。0 も環境値に優先 | 負値または NaN は stderr に strata generate: --ram-keep-gib needs N >= 0 を出し終了コード 2。数値でない文字列は atof が 0 とするので 0 として通る |

atof は文字列全体の形式を検証せず、後続の非数値文字を無視する。大文字小文字による判定はない。ram_keep_from_gib は 0 以下を 0 にし、正数を byte に換算して整数 byte に切り捨てる。1024 GiB 以上は 1024 GiB に clamp。1 byte 未満となる小さな正数は変換後 0 byte となり実質無効果（engine/include/strata/core/ple_residency.hpp:148-155）。

## 有効になる条件

- 値が有効でも、起動時に expert arena または RAM copy を使う経路に限って効果がある。読み取りと設定に backend / build macro の条件分岐はない（engine/src/program/generate.cpp:3838-3842,4277-4285）。
- ArenaExpertSource は共有 arena を使わず、host RAM 情報を取得できた場合に arena + 追加 blob + keep 値で必要 RAM を判定する。共有 arena 指定時はこの host RAM 判定を通らず、keep 値で共有 arena の選択を判定しない（engine/src/core/expert_source.cpp:6530-6537）。
- Windows 以外で STRATA_ARENA_MMAP=1 かつ既存 experts ファイルのサイズが期待値に一致し、mmap に成功すれば、通常の RAM 判定より前にその経路で返るため keep 値は効かない（engine/src/core/expert_source.cpp:6484-6522）。
- --mmap-experts / --ssd-experts で arena を使わず、RAM copy も作らない経路では RAM を keep 値分予約しない（engine/src/program/generate.cpp:4218-4219,4236-4240,8621-8628）。
- --resident-experts または正の --resident-budget-gib では、keep 値が正で STRATA_RESIDENT_HEADROOM_GIB が有効でなければ resident_headroom を少なくとも keep 値まで上げる。STRATA_RESIDENT_HEADROOM_GIB の atof 値が 0 以上ならそちらが優先し、0 も指定値。resident_headroom は pin_cache_complement に渡る（engine/src/program/generate.cpp:4221-4228,4242-4257,4283-4285,12077-12080）。
- arena 不足時の RAM copy fallback は expert profile があり、既に resident CPU mode でなく、STRATA_ARENA_FALLBACK_RESIDENT=0 でもない場合に選ぶ。headroom は STRATA_RESIDENT_HEADROOM_GIB が 0 以上ならその値、そうでなければ max(keep, safety headroom)。safety headroom は Windows 8 GiB、その他 4 GiB（engine/src/program/generate.cpp:8602-8618,8890-8908; engine/include/strata/core/ple_residency.hpp:157-177）。
- fallback 自体は --ple-io ram、共有 arena 指定、または STRATA_ARENA_RAM_FALLBACK=0 で無効になる。不足時は警告を伴い要求どおりロードを続けるか、hard memory limit により拒否する（engine/src/program/generate.cpp:8602-8604,8860-8863; engine/include/strata/core/ple_residency.hpp:60-73）。

## 実行時の詳細

値は engine 起動時、argv 解析の直後に読み、Options::ram_keep に byte 数で保持する。static cache やリクエスト単位の再読み込みはない。実行中の環境変更は反映されず、次の engine 起動から反映（engine/src/program/generate.cpp:3838-3842,4277-4285）。

arena 判定では arena + 追加 blob + keep を必要 RAM として比較する。hard memory limit では fallback が許される場合に fallback headroom も判定に含める。RAM が不足すれば既存の待機・fallback 判定へ進む（engine/src/core/expert_source.cpp:6533-6537,6560-6569; engine/include/strata/core/ple_residency.hpp:159-177）。Linux の file cache / huge pages を考慮した不足判定もこの need を用いる（engine/src/core/expert_source.cpp:6604-6637）。

fallback 時は通常 file source に切り替える。profile があり fallback resident copy の条件を満たす場合、headroom を差し引いた利用可能 RAM の範囲で profile 上の高頻度 experts を RAM copy にし、残りはファイルから読む。明示 RAM mode でも resident_headroom が copy 処理に渡される（engine/src/program/generate.cpp:8876-8911,12077-12080）。

## ログと測定値

keep 値が正なら、arena open 前に stderr に次の形式で出る。環境変数経由でもログ上は --ram-keep-gib と表示する。0 byte の場合はこの行を出さない（engine/src/program/generate.cpp:8862-8869）。

strata generate: --ram-keep-gib %.2f: the expert arena is used only if %.2f GiB of RAM stay available after it; otherwise the RAM copy of the hottest experts leaves %.2f GiB free (the larger of that and the %.0f GiB safety headroom, STRATA_RESIDENT_HEADROOM_GIB decides when set)

Linux で通常のRAMが不足しても file cache / huge pages が arena を支えられると判定した場合、engine はロードを続け、stderr（--serve では stdout にも）へ次の WARNING を出す。STRATA_ARENA_FILE_CACHE=0 はこの経路を無効にする（engine/src/core/expert_source.cpp:6618-6648; engine/src/program/generate.cpp:8934-8935）。

strata generate: WARNING: the experts need %.2f GiB of RAM and %.2f GiB is free, but free memory, file cache and reserved huge pages can hold them, so they load anyway (same answers). STRATA_ARENA_FILE_CACHE=0 reads them from the file instead.

必要RAMに届かないと、既定で最大20秒、STRATA_ARENA_RAM_WAIT_S で設定された時間まで空きRAMを待つ。待機のログは stderr に「strata generate: the expert arena needs ... and ... is available; waiting up to ... s for it (another engine still exiting?) - ... s so far (STRATA_ARENA_RAM_WAIT_S changes this)」の形式（engine/src/core/expert_source.cpp:6560-6588）。

fallback では stderr に次の形式の通知が出る。--serve では同じ通知を stdout にも出す（engine/src/program/generate.cpp:8880-8888）。arena open が失敗し RAM shortage fallback 以外の error の場合、engine は error を stderr に出して終了コード 1 を返す（同ファイル:8913-8915）。fallback が無効な場合、RAM 不足時は警告または hard-limit 拒否となり、詳細は ArenaExpertSource::open の error に含まれる（engine/src/core/expert_source.cpp:6543-6558,6652-6674）。

strata generate: not enough RAM for the expert arena (...): this run reads the experts from the file, like --mmap-experts (slower; the answers are the same). To get the arena back, free that RAM and start again

## 根拠

- engine/src/program/generate.cpp:4230-4235,4277-4285 — CLI 優先、環境値の読み取り、明示 RAM mode との連携。
- engine/include/strata/core/ple_residency.hpp:140-182 — 単位変換、上限、arena と fallback headroom の計算。
- engine/src/core/expert_source.cpp:6484-6537,6543-6569,6604-6677 — mmap 早期経路、RAM 判定、待機、fallback / 警告。
- engine/src/program/generate.cpp:8602-8618,8860-8911,12077-12080 — fallback 条件、headroom、通知と RAM copy。
- app/host/server/native-resources.mjs:89-112,130-158 — desktop Work profile が起動環境へ設定する条件。
