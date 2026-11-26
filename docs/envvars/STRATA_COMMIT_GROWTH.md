# `STRATA_COMMIT_GROWTH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows で、ページファイルが現在のサイズからさらに拡張できる量を見積もる処理を無効にするスイッチ。未指定または `atoi` の結果が 0 以外なら、`PagingFiles` レジストリ設定と各ボリュームの空き容量から拡張可能量を見積もる。`0` 扱いになる値ではその見積もりを 0 にする。見積もりは `commit_available()` で現在の空き commit に加算され、Windows Job Object の上限で制限される。この結果は Windows のホストメモリ予算や診断表示に使われる。実装は共通ヘッダー `strata::platform::commit_growth()` にある（`engine/include/strata/platform/commit.hpp:89-104`）。

この変数自体がページファイルを変更したり、メモリを確保したりするわけではない。CUDA/HIP の Windows 側では自動 RAM expert 上限の計算に使われ、一般の expert source と SYCL 側では RAM/commit に基づく resident 予算の clamp・安全確認に使われる（`engine/src/inkling2/cuda/ink_hybrid.cuh:64-71`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1095-1123`、`engine/src/core/expert_source.cpp:414-427,4044-4066`、`engine/sycl/src/core/expert_source.cpp:245-258,1739-1765`）。また Windows の conversation memory 計測にも使われ、serve の自動 conversation cache 容量や会話状態の読み込み可否に渡る空き RAM 値に反映される（`engine/src/core/conversation_memory.cpp:411-421`、`engine/src/program/generate.cpp:13849-13870`、`engine/sycl/src/program/generate.cpp:8448-8484`）。Windows の serve 起動時や SYCL の expert-cache 確保失敗時には、見積もりを含む診断にも使われる（`engine/src/program/generate.cpp:12352-12372`、`engine/sycl/src/program/generate.cpp:5136-5165`）。

## 値と判定

| 条件 | unset | 設定時に見積もりを無効にする値 | 設定しても無効化しない例 |
|---|---|---|---|
| Windows (`_WIN32`) | 見積もりを行う | `std::atoi(v) == 0`。例: `0`, `00`, `-0`, 空文字, `true`, `false`, `junk`, `0anything` | `1`, `-1`, `2`, `1anything`, ` 1` |
| Windows 以外 | 見積もり量は常に `0` | 該当なし。この build 経路では環境変数を読まない | 該当なし |

Windows では `getenv` が null かだけを確認し、設定があれば `std::atoi` の結果が 0 かを判定する。文字列全体の数値妥当性は検証せず、`atoi` が先頭から変換できた数値を使うため、後続文字は無視される。空文字や数値で始まらない文字列は結果 0 となり無効化側に入る。`atoi` のため、先頭の空白や符号も数値変換規則に従う。大文字小文字は数値変換に関与しない（`engine/include/strata/platform/commit.hpp:102-104`）。

無効化側では `commit_growth()` が直ちに 0 を返す。通常側は `advapi32.dll` のロード、`RegGetValueW` による `SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PagingFiles` の読み出しに失敗した場合も 0 を返す（`engine/include/strata/platform/commit.hpp:101-120`）。値の指定がない場合の計算は、Windows 管理ページファイルでは RAM の最大 3 倍（最低 4 GiB）とボリューム容量の 1/8 の小さい方を上限とし、固定設定では設定された最大値を上限とする。どちらも現在のサイズからの増加分をボリューム空き容量の 90% 以内で合算する（`engine/include/strata/platform/commit.hpp:121-149`）。

## 有効になる条件

- `_WIN32` でコンパイルされた処理だけがこの環境変数を読み、見積もりを計算する。非 Windows の分岐は `ram_total` を使わず 0 を返す（`engine/include/strata/platform/commit.hpp:102-104,150-153`）。
- 値が未設定、または `atoi` が 0 以外なら、呼び出し側が `commit_growth()` を使う場面で有効になる。設定は単独で実行時機能を起動せず、呼び出し側のメモリ計測・予算計算・診断が必要。
- `commit_available()` は見積もりを現在の `ullAvailPageFile` に加算し、加算 overflow を飽和させた後、Windows Job Object の残り commit 容量を上限にする。Job Object に制約がなければその上限は無制限扱い（`engine/include/strata/platform/commit.hpp:56-79,92-95`）。
- CUDA/HIP の自動 RAM expert 上限は Windows のみ `GlobalMemoryStatusEx` から得る空き RAM と推定可能 commit の小さい方を基に計算する。HIP 経路ではさらに 2–4 GiB の OS reserve と cgroup 上限が適用される。明示的な `ram_experts_gb` 指定、`ssd_experts`、または `ram_experts_gb == 0` では、この自動上限の分岐を通らない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1090-1132`）。
- 一般の resident expert copy では、`--resident-budget-gib` 等で要求された予算も空き RAM・commit と headroom により clamp される。見積もりが 0 になっても OS 側の確保を保証するものではなく、実際のサイズ超過は `FileExpertSource` の安全確認で失敗し得る（`engine/src/core/expert_source.cpp:4044-4066,4187-4217`）。SYCL 版にも同様の clamp と安全確認がある（`engine/sycl/src/core/expert_source.cpp:1739-1789,1793-1815`）。
- Windows の `available_host_bytes()` は空き RAM と推定可能 commit の小さい方を返し、serve の自動 conversation cache sizing や会話状態のメモリ admission がこの値を参照する。明示した `--conversation-cache-mib` は自動 sizing の対象外だが、会話状態の個別読込 admission は別途空き RAM を再計測する（`engine/src/core/conversation_memory.cpp:411-421,443-447`、`engine/src/program/generate.cpp:13849-13870`、`engine/sycl/src/program/generate.cpp:8448-8484,10454-10467`）。
- 直接の読み取り箇所に CLI 引数や別環境変数による上書き・優先順位分岐はない。呼び出し側の個別の予算指定は別途 clamp に参加するが、この環境変数の判定自体は変えない。

## 実行時の詳細

`commit_growth()` は関数内 static に値を保存せず、呼び出されるたびに Windows 環境から値を読み直す。したがって、呼び出し間でプロセス環境が変更されれば次回の呼び出しに反映される。Strata 内でこの変数を子プロセス用に設定・転送する箇所は見つからなかった（直接参照は `engine/include/strata/platform/commit.hpp:104` のみ。ソース全体の完全一致検索で確認）。

読み出しはモデル生成中の host memory probe や resident budget 計算、serve 中の自動 conversation cache sizing / 会話状態 admission で行われるほか、Windows の serve 起動時の commit 診断、SYCL expert-cache の確保失敗時の診断にも行われる。`available_host_bytes()` は呼び出しごとに `sample_host_memory()` を呼び、Windows ではその都度 `commit_growth()` が評価される（`engine/src/core/conversation_memory.cpp:411-421,443-447`）。SYCL expert-cache の失敗ログでは `commit_growth` は表示用の残り commit 数値を変える。自動 cache の縮小再試行条件そのものは `auto_cache`、失敗回数、縮小成功で決まり、この環境変数による分岐はない（`engine/src/program/generate.cpp:12354-12372,13849-13870`、`engine/sycl/src/program/generate.cpp:5136-5165`）。

## ログと測定値

- Windows serve の起動時診断は `strata serve: Windows commit: %.1f GiB left of a %.1f GiB limit (RAM + page file)` を出し、推定拡張量が正なら `; the page files may grow by %.1f GiB more` を追記する。`STRATA_COMMIT_GROWTH=0` 相当ではこの追記が出ない。commit verdict が警告を要するときは別途 `strata serve: %s` を出す（`engine/src/program/generate.cpp:12362-12371`）。
- `FileExpertSource` の Windows 診断には `available commit` と `(limit ...; the page files may grow by ... more)` が含まれる。値が 0 の場合も文面の項目自体は表示され、拡張量が 0.00 GiB となる（`engine/src/core/expert_source.cpp:604-617`）。
- SYCL の Windows expert-cache 確保失敗時、空き commit の補足値と拡張量が `strata generate: ... (Windows has ... of which the page files may still grow by ... GiB)` の形で retry ログに含まれる。最後まで失敗した場合は通常のエラーと Windows の page-file / `--expert-cache` 案内を stderr に出す（`engine/sycl/src/program/generate.cpp:5140-5165`）。
- `docs/DETAILS.md:1533` は Windows の GPU allocation が system commit に計上され得ることと `--expert-cache` の縮小 retry を説明しているが、この環境変数固有の設定値や効果の測定値は記載していない。ここでは性能・正確性の測定値を付さない。

## 根拠

- `engine/include/strata/platform/commit.hpp:89-153` — 加算と Job Object 上限、環境変数の判定、ページファイル拡張量の算定、OS 分岐。
- `engine/src/core/expert_source.cpp:414-427,563-572,4044-4066,4187-4217` — Windows memory snapshot、resident budget への適用と安全確認。
- `engine/src/core/conversation_memory.cpp:411-421,443-447`、`engine/src/program/generate.cpp:13849-13870`、`engine/sycl/src/program/generate.cpp:8448-8484,10454-10467` — Windows conversation memory telemetry の利用先。
- `engine/sycl/src/core/expert_source.cpp:245-258,354-360,1739-1815` — SYCL 側の同じ適用経路。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:64-71`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1090-1132` — CUDA/HIP 側の自動 RAM expert 上限。
- `engine/src/program/generate.cpp:12352-12372`、`engine/sycl/src/program/generate.cpp:5136-5165` — 診断出力と cache 失敗時の経路。
- `engine/src/core/expert_source.cpp:604-617` — FileExpertSource の Windows memory 診断。
- `docs/DETAILS.md:1533` — 関連する Windows system commit / expert-cache の説明。
