# `STRATA_SPILL_OFF`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`src/program/generate.cpp` の `generate` 起動準備で、VRAM 不足時に Strata が自動で行う一連の spill walk（GPU 上の配置やキャッシュを小さくする処理）の一部を止める。実装は `std::getenv("STRATA_SPILL_OFF") == nullptr`、つまり値ではなく環境変数の設定有無で判定する。設定すると自動 fallback を行わないため、同じメモリ不足が残り、既存の失敗経路に進むことがある。これは GPU spill の自動調整を制御するもので、明示指定の `--trim-stage-weights` / `STRATA_STAGE_TRIM` などを一律に無効化するスイッチではない（`src/program/generate.cpp:5461-5475`, `5701-5731`）。

対象になる主な自動調整は次のとおり。

- `--layer-split auto` で空きの足りない GPU を split から外す処理（`src/program/generate.cpp:4519-4539`）。
- layer split の重み trim と、auto split の早期 trim（`src/program/generate.cpp:5477-5485`, `5698-5729`）。
- split の配置を開始できない場合に KV window を小さくして再探索する処理（`src/program/generate.cpp:7080-7100`）。
- キャッシュが小さい場合に prompt buffer の借用で残す cache slot 数を減らす処理（`src/program/generate.cpp:8622-8640`, `9335-9350`）。
- 単一 GPU の自動 cache が小さい場合に prompt path 用の独立 buffer と小さい chunk を選ぶ処理、および cache に空きがない場合に output head を pinned host memory に移す処理（`src/program/generate.cpp:8668-8696`, `8698-8725`）。
- layer split の head 保持 GPU で cache の余地が足りない場合に output head を pinned host memory に移す処理（`src/program/generate.cpp:9222-9237`）。
- multi-GPU split で MTP / DFlash2 drafter を外す spill walk（`src/program/generate.cpp:7646-7678`）。ただし、単一 GPU の MTP drafter 判定は別条件で残る（後述）。

いずれも `generate.cpp` 内で GPU の空き容量やモデル配置を調べる初期化中の分岐であり、推論 token の選択を直接変更する処理ではない。spill 判定は Metal build と integrated GPU では許可されず、CUDA/HIP 互換 API から discrete GPU と判定された場合に限られる（`src/program/generate.cpp:306-319`, `include/strata/core/spill_gate.hpp:8-14`）。

## 値と判定

| ビルド / 実行条件 | unset | 設定時に有効になる値（spill を止める） | 無効になる値（spill を止める） |
|---|---|---|---|
| 全条件 | `getenv` が `nullptr`。他の条件を満たせば spill walk の各分岐を評価する | 値の内容を問わず、環境変数が存在すれば該当分岐を止める。例: 空文字、`0`、`1`、`false`、空白 | 該当なし。文字列 parse や値の妥当性検査はない |

したがって `STRATA_SPILL_OFF=0` も spill を止める。大文字小文字、数値境界、負値の規則はなく、文字列を比較・変換しない（`src/program/generate.cpp:4521`, `5483`, `5703`, `7083`, `7654`, `8627`, `8674`, `8703`, `9225`, `9339`）。

## 有効になる条件

- 変数が **unset** で、かつ個々の spill walk の条件が揃うと、自動調整候補が実行される。設定済み（空文字を含む）なら、明示指定や他条件による処理を除き、その候補は飛ばされる。
- ほとんどの spill walk は `spill_discrete_gpu()` が true の場合だけ動く。Metal build では常に false、非 Metal では GPU device property を一度調べ、integrated GPU なら false、discrete GPU なら `strata::spill_allowed(false, ...)` が true となる（`src/program/generate.cpp:306-319`, `include/strata/core/spill_gate.hpp:8-14`）。GPU 情報取得に失敗した場合も false。
- 利用モードや設定が個々の分岐を制限する。たとえば GPU を減らす処理と早期 trim は `--layer-split auto` が必要（`src/program/generate.cpp:4521`, `5483-5485`）。KV window の再探索は split auto の初回探索が配置を見つけられない場合だけ（`src/program/generate.cpp:7080-7095`）。
- trim walk は `trim_user_asked` が false で、`STRATA_STAGE_TRIM=0` でも `STRATA_SPLIT_EARLY_OFF` でもないことが条件。明示的な `--trim-stage-weights` / `STRATA_STAGE_TRIM` による trim は `STRATA_SPILL_OFF` の getenv 判定を通らず、別ルールで適用される（`src/program/generate.cpp:5461-5475`, `5483-5485`, `5703-5704`）。
- 単一 GPU の cache / prompt buffer / head 調整は、cache が不足していること、自動 cache などの条件、未指定の reserve など各分岐の条件が必要。output head の host 移動はさらに `STRATA_HEAD_HOST_OFF` が unset であることが必要（`src/program/generate.cpp:8622-8627`, `8668-8675`, `8702-8704`）。split 側の host 移動には `STRATA_HEAD_HOST_OFF` unset、reserve 未指定、cache の余地不足が必要（`src/program/generate.cpp:9222-9226`）。
- split の MTP / DFlash2 退避は `split_walk_drafter` にこの変数の unset 判定を一度格納しており、変数設定時は multi-GPU split での該当処理を止める。一方、単一 GPU の MTP 退避は `(!multi_gpu && stages.empty())` の別枝で評価され、`STRATA_SPILL_OFF` を見ない。従って設定しても、discrete GPU・MTP・`STRATA_MTP_KEEP` unset などの条件が揃えば単一 GPU の drafter は従来どおり外され得る。DFlash2 はビルド macro `STRATA_HAVE_DFLASH2` の下で別途判定される（`src/program/generate.cpp:7609-7616`, `7646-7678`）。
- CLI の明示設定は個別分岐に従う。例として `--vram-reserve-mib` 指定時には単一 GPU の cache buffer 変更や host head fallback が止まり、明示 cache/chunk 指定も prompt spill 条件に関わる（`src/program/generate.cpp:8626-8627`, `8672-8675`, `8702-8704`）。

## 実行時の詳細

候補名の全参照は `src/program/generate.cpp` にあり、同ファイルの直接 `getenv` 判定 10 箇所と、コメント中の説明を確認した。値を helper に動的に渡す経路はない。helper `spill_discrete_gpu()` 自体は GPU 種別を判定するだけで、この環境変数は読まない（`src/program/generate.cpp:306-319`）。設定値は parse されず、各 spill 判定地点で `getenv` が呼ばれるため、対象機能のための共通 static cache はない。ただし split drafter 判定は `split_walk_drafter` というローカル bool にその地点で一度格納される（`src/program/generate.cpp:7654-7655`）。

設定時は、たとえば split auto が使える GPU を減らさず、split 配置探索の失敗後も KV window を縮めずに既存の経路へ進む。auto split の探索が最後まで空の場合、stderr に `strata generate: layer split auto: no placement can start the prompt path on the figures here; choosing by decode speed alone` を出して制約なしの再探索を行い、それでも配置がないと `strata generate: --layer-split auto: no valid split for %d GPUs (this model has %lld layers)` を出して return 2 する（`src/program/generate.cpp:7101-7113`）。

単一 GPU で自動 cache が 0 のままなら既存の不足診断に進み、stderr に `strata generate: no VRAM is left for the expert cache: it needs at least ...` を出す（`src/program/generate.cpp:8727-8747`）。この変数自体の専用警告や確認ログはない。環境変数を実行中に変更する経路や子プロセスへの転送は、Strata 所有ソースで確認できなかった。

## ログと測定値

`STRATA_SPILL_OFF` を設定したこと自体を示すログはない。変数を unset にして spill が実行された場合は、条件に応じて「short of GPU memory」等の各処理ログが出る。たとえば GPU を split から除く場合は `src/program/generate.cpp:4532-4537`、cache に余地がなく host head fallback を試みる場合は `src/program/generate.cpp:8721-8725` に文字列がある。設定によって spill を飛ばした場合は、その分岐固有の理由ログは出ない。

`docs/MULTI_GPU.md:224-235` は spill walk の説明と過去の測定例を掲載し、`STRATA_SPILL_OFF=1` で全段階を止めると記す。ただしコードは値を見ず存在だけで判定し、単一 GPU の MTP drafter spill は設定時にも残るため、「every step off」という説明はコード上の全 spill 経路には当てはまらない。測定例は過去の条件付き記録であり、ここでは現行動作の測定値として扱わない。

## 根拠

- `src/program/generate.cpp:306-319` — discrete GPU / Metal / integrated GPU の spill gate。
- `src/program/generate.cpp:4519-4539` — layer split auto の GPU 除外。
- `src/program/generate.cpp:5461-5485`, `5698-5731` — trim の既定値、spill walk trim と明示 trim の区別。
- `src/program/generate.cpp:7080-7113` — KV window 再探索と split 配置失敗時のログ・終了。
- `src/program/generate.cpp:7646-7678` — single / multi GPU の drafter spill 判定。
- `src/program/generate.cpp:8622-8640`, `8668-8725`, `8727-8747` — cache / prompt buffer / head fallback と不足時ログ。
- `src/program/generate.cpp:9222-9237`, `9335-9350` — split head fallback と cache loan 調整。
- `include/strata/core/spill_gate.hpp:8-14` — Metal / integrated GPU を spill 対象外にする gate。
- `docs/MULTI_GPU.md:224-235` — spill walk の説明とコードとの差異を確認。
