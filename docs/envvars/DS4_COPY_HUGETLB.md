# `DS4_COPY_HUGETLB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 エンジンが CPU lane の expert を RAM にコピーするとき、そのコピー用 arena を OS の明示 huge-page pool 上に割り当てるかを選びます。対象の allocator は Linux 系で `MAP_HUGETLB` を使い、2 MiB 単位で確保します。これは Strata 自身が読む設定です。

この値は、DSV4.1 の MXFP4 GGUF 読み込みで、RAM tier ではなく、未 VRAM 配置 expert の warm list があり、`copy_experts()` が呼ばれる場合に評価されます。`--mmap-experts on` はこのコピー処理を早期 return で飛ばします。適用されるのはコピー arena の割当方式で、コピーする expert 数そのものは別の RAM 予算判定で決まります。

## 値と判定

`env_tri()` は `std::getenv()` の結果を `std::atoi()` に渡し、変数が未設定なら `-1`、設定されていて変換結果が 0 なら `0`、それ以外なら `1` にします。文字列全体の検証やエラー報告はありません。

| 環境変数の値 | 判定 | 効果 |
|---|---:|---|
| 未設定 | `-1` | 既定値判定に進む |
| 空文字、非数値文字列、数値として 0 の文字列 | `0` | huge-page arena を明示的に無効化 |
| `atoi()` の結果が非 0 の文字列（例: `1`, `2`, `-1`, `1tail`） | `1` | huge-page arena を明示的に要求 |

したがって `true` は非数値なので無効、`1tail` は先頭の数値部分が 1 なので有効です。空白や符号の扱いも `atoi()` に従います。数値変換の overflow は Strata 側で検査しません。

未設定時は `DS4_DEFAULTS` が `026`, `0.2.6`, `v0.2.6` のいずれかと完全一致すれば OFF です。それ以外では、読み取れた予約 pool の空きがコピー対象全体以上のときだけ ON になります。明示値 0/非 0 は `DS4_DEFAULTS` より優先されます。

CLI の `--mmap-experts on` はコピー処理自体を飛ばし、`--mmap-experts off` はコピー可能な RAM 量を予算にします。`DS4_COPY_GB` が設定されると、コピー量の予算をその値で上書きします（`atof(value) * 1e9`）。これらは huge-page の ON/OFF 判定を上書きしませんが、予算が 0 以下なら arena は確保されません。

## 有効になる条件

- `copy_experts()` が対象 expert のコピー予算を得て、実際に layer の arena を確保するときに割当方式として使われます。`--mmap-experts on`、空の warm list、RAM tier の経路ではこの関数が呼ばれないため、この変数は評価されません。
- `DS4_DEFAULTS=026` 系の値は未設定時の既定を OFF にしますが、`DS4_COPY_HUGETLB=1` など明示的な非 0 は引き続き優先されます。アプリの「DeepSeek speed-ups」設定を OFF にする構成は `DS4_DEFAULTS=026` とともに本変数へ `0` を渡します。
- huge-page pool の空きは `HugePages_Free × Hugepagesize` で読み取られます。Windows では常に 0、他の非 Windows では `/proc/meminfo` が開けない場合も 0 です。macOS では huge-page allocator が常に失敗する実装です。
- Linux で pool が不足していても明示値 1 は要求を止めません。コピー全体の RAM 予算では、選択が ON の場合にのみ pool の空き bytes を通常の `MemAvailable` ベースの予算へ加算します。

## 実行時の詳細

設定は `copy_experts()` の実行時、expert copy の初期化中に読みます。`DS4_COPY_HUGETLB` 自体に static cache はなく、関数が呼ばれるたびに読みますが、すでに確保した arena の方式は後から変わりません。別の `DS4_DEFAULTS` は `defaults_026()` 内の `static const bool` に初回評価結果を保存します。その評価後に環境を変更しても、cache は更新されません。

ON の場合、各 layer の arena chunk を huge-page pool から割り当てます。未設定のまま pool がコピー全体を保持できるため自動 ON になった場合、stderr に空き pool とコピー量、および `DS4_COPY_HUGETLB=0` で通常 arena を使える旨を出します。明示値で ON にした場合、この自動選択ログは出ません。

chunk の huge-page 割当が失敗すると、stderr に `ds4: the 2 MB huge-page arena was asked for but the pool ran out ...; using the ordinary arena` を一度出し、その chunk を通常 arena に切り替えます。通常割当も失敗した layer は `ds4: no RAM for layer ...; they stay in place` と出て、その layer の expert はコピーされません。成功したコピーについては、完了後にコピー数、合計 GB、NUMA part 数などを stderr に出します。モデルファイルからのコピー読み込み失敗は `copy_experts()` を失敗させ、呼び出し元へエラーを返します。

`DS4_COPY_PIN` が別途有効ならコピー済み arena を GPU 登録する処理へ進みますが、登録に失敗した場合は「prompt path stages them」と stderr に出します。huge-page 選択だけで pinning は有効になりません。

## 根拠

- 値の変換: `src/dsv41/ds4_model.cu:97-101`。
- 適用経路と pool に基づく既定値判定、自動 ON ログ、RAM 予算への pool 加算、`DS4_COPY_GB` による予算上書き: `src/dsv41/ds4_model.cu:4959-4990`。
- `copy_experts()` の呼び出し条件: `src/dsv41/ds4_model.cu:4876-4881`。`--mmap-experts on` で早期 return する条件: `src/dsv41/ds4_model.cu:4959-4960`。
- huge-page 選択規則、`DS4_DEFAULTS` の完全一致と cache: `src/dsv41/ds4_experts_rule.hpp:16-28,182-187`。
- 空き pool の読み方と OS 別条件: `src/dsv41/ds4_os.hpp:441-459`。2 MiB allocator と失敗条件: `src/dsv41/ds4_os.hpp:462-477`。
- arena の割当、pool 枯渇時の通常 arena fallback、layer 単位の失敗ログ: `src/dsv41/ds4_model.cu:5041-5072`。
- コピー処理の失敗返却と完了ログ: `src/dsv41/ds4_model.cu:5118-5130`。
- 関連する pin の条件と結果ログ: `src/dsv41/ds4_model.cu:5131-5159`。
- UI 設定が渡す値: `strata_control/speed_switches.py:48-55`, `apps/host/server/native-settings.mjs:49-53`。
