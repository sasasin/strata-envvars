# `STRATA_FILE_TIER_IDLE`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Linux の mapped file tier で、GPU cache に全 expert が収まってファイル層を読まない間に、Linux 既定の I/O prefetch と routing-aware look-ahead を自動停止し、GPU cache から expert が外れたら再開する idle policy を制御します。`0` を指定するとこの自動停止・再開を無効にします。これは file tier や prefetch 自体を無効にする設定ではありません。

## 値と判定

`src/program/generate.cpp` で `std::getenv` の結果を `std::atoi(v) != 0` で判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| `0`、`00`、`false`、数字で始まらない文字列 | 無効（変換結果 0） |
| `1`、`-1`、数字で始まり 0 以外になる文字列（例: `2x`） | 有効 |

`atoi` は文字列全体の妥当性を検査せず、先頭の空白・符号・数字列を変換し、後続文字を無視します。CLI 引数による上書きや、無効値時の fallback はありません。環境変数の判定は `generate` の初期化時に一度行い、ローカルの `const bool` に保持します。実行中に環境を変更しても再評価されません。

## 有効になる条件

- 自動判定が有効でも、処理対象は `srcp == &src`、すなわち `FileExpertSource` の file tier 経路です。pinned arena (`arena_src`) 経路には適用されません。
- Linux の file tier 既定 prefetch は `FileExpertSource::linux_io_defaults()` が Linux 以外では常に false を返し、Linux でも GGUF in-place または experts.bin の page-cache room 条件を満たす場合だけ true になります（`include/strata/core/expert_source.hpp:1047-1059`）。したがって Windows/macOS ではこの既定動作の自動停止・再開は起きません。
- 全 expert が GPU cache の live slot にある場合に停止対象になります。`count_gpu_held()` は layer ごとの cache slot を走査し、live slot にある expert 数を layer 数×expert 数と比較します（`src/program/generate.cpp:8864-8879,8940-8945`）。
- `STRATA_IO_PREFETCH` を明示して有効にした prefetch は `io_pf_by_default` にならないため、この policy による停止対象ではありません。明示値 `1` は `la_asked` も真にするため、通常の routing-aware look-ahead も維持します。`STRATA_LOOKAHEAD` の非ゼロ値も look-ahead を維持します（同ファイル `:7505-7516,8890-8892`）。
- `STRATA_FS_SLOTS` と `STRATA_FS_AHEAD` による Foresight 経路、または `STRATA_LOOKAHEAD_STATS` による統計経路は look-ahead の別条件です。idle policy は通常 look-ahead を切り離す場合でも、これらの経路を切り離しません（同ファイル `:8900-8905,8925-8927,8956`）。

## 実行時の詳細

起動時、file tier が `src` の場合に GPU cache の residency を数えます。全 expert が収まっていて、かつ Linux 既定 prefetch が実際に起動していた場合、`src.set_io_prefetch(false, 0)` を呼び I/O prefetch とそれに伴う decode gate を止め、stderr に `strata generate: every expert is in the GPU caches ...` を出します（`src/program/generate.cpp:8877-8888`）。通常の routing-aware look-ahead が起動済みで、明示的な I/O prefetch/look-ahead や Foresight・統計の要求がなければ、`drive.d.lookahead` を null にして decode から切り離します。look-ahead 自体の初期化・起動条件は別判定です（同ファイル `:8904-8936`）。

serve の `GEN` / `GENI` リクエスト開始時に residency を再確認します（同ファイル `:15699-15700`）。全 expert が cache にある状態へ変わると、policy が停止した既定 prefetch を停止し、通常 look-ahead を切り離します。全 expert がいなくなった状態へ変わると、policy が停止した prefetch を再開し、look-ahead を再接続します。遷移時は `strata serve: every expert is in the GPU caches again ...` または `strata serve: ... file tier's Linux defaults are on again` を stderr に出します（同ファイル `:8948-8974`）。変更はリクエスト開始時の quiet point で行われ、リクエスト中には residency を再評価しません。

この変数が無効でも、Linux 既定 prefetch と look-ahead は通常どおり起動条件を満たせば動作しますが、全 expert が GPU cache にあることを理由に自動停止・再開しません。`set_io_prefetch(false, ...)` は Linux 実装で gate を先に off にしますが、変数自体に警告・エラー・終了経路はありません（`src/core/expert_source.cpp:1171-1177`）。

## 根拠

- 候補名の全参照: `src/program/generate.cpp:8859-8860`（コメントと実読み取り）、`docs/DETAILS.md:297`（説明）。他の読み取り箇所や helper への動的な名前渡しはありません。
- 値の読み取り、既定 Linux prefetch の判定: `src/program/generate.cpp:7500-7516,8853-8862`。
- residency による初期動作と切替: `src/program/generate.cpp:8864-8888,8890-8936,8938-8974,15699-15700`。
- Linux 以外の既定値と Linux の file tier 条件: `include/strata/core/expert_source.hpp:1047-1059`。
- I/O prefetch 停止時の gate 処理: `src/core/expert_source.cpp:1171-1177`。
- 設計説明との照合: `docs/DETAILS.md:291-297` は、全 expert が GPU cache にある場合の既定動作停止、`STRATA_IO_PREFETCH=1` / `STRATA_LOOKAHEAD=1` による維持、および `STRATA_FILE_TIER_IDLE=0` による policy 無効化を説明しており、実装と整合します。
