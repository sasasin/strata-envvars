# `STRATA_PIPED_CONCURRENT_UNPIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

パイプライン同時読み込みが実行されるとき、プロンプト読取スレッドと doorbell スレッド、および条件によっては先行して作られていた host thread 継承スレッドを host の CPU から移す処理を切り替える。未設定または `atoi` の結果が非 0 なら移動処理を許可し、結果が 0 ならスレッド配置をそのままにする。これは `STRATA_PIPED_CONCURRENT` の機能を有効・無効にする変数ではなく、CPU 配置だけを変える（`engine/src/program/generate.cpp:21068-21111`）。

## 値と判定

値は、同時読み込み分岐に初めて入ったとき `std::getenv` で取得し、`std::atoi` の結果が 0 かどうかで判定する。文字列全体の妥当性検査や `true` / `false` の特別扱いはない。空文字、非数値文字列、`0` や `0anything` は `atoi` が 0 を返すため移動しない。`1`、`-1`、`1anything` などは非 0 となり移動を許可する。先頭の空白や符号を含む数値も `atoi` の変換規則に従う。未設定は移動を許可する（`engine/src/program/generate.cpp:21070-21073`）。

| 条件 | unset | 移動を許可する値 | 移動しない値 |
| --- | --- | --- | --- |
| 全プラットフォーム共通の値判定 | `true` | `atoi(value) != 0`（例: `1`, `-1`, `1abc`） | `atoi(value) == 0`（例: 空文字, `0`, `0abc`, `true`, `abc`） |

## 有効になる条件

- 設定値はプロセス内の配置分岐に限って作用する。`STRATA_PIPED_CONCURRENT` が有効であることに加え、`--batch` が正、`--batch-groups` が 1 より大きく、層分割で `n_pipe > 1` のパイプ経路である必要がある（`engine/src/program/generate.cpp:17529-17532`）。
- 対象リクエストに画像がなく、読み取る token 数が `STRATA_PIPED_CONCURRENT_MIN` 以上であることが必要。`STRATA_PIPED_CONCURRENT_MIN` は未設定なら 0（全ての長さ）、設定時は `atoll` 後に 0 未満を 0 に丸める（`engine/src/program/generate.cpp:21047-21054`）。
- 同時読み込み自体は、`STRATA_PIPED_CONCURRENT` が設定され `atoi` で非 0 の場合に opt-in される。`STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS` がそれぞれ `atoi` で非 0、`--pcie-mode dma`、helper cache の利用、GGUF source の staging、または GGUF source / arena 以外の expert source のいずれかがあると同時読み込みを止め、stderr に `strata batch: STRATA_PIPED_CONCURRENT is off beside <理由>` を出す。この場合、本変数の配置分岐にも到達しない（`engine/src/program/generate.cpp:21024-21045`; `engine/include/strata/program/batch_read.hpp:30-53`）。
- Linux では aux CPU 配置が有効なら、新規スレッドは `pin_current_thread()` でその配置先に移る。無効なら、本変数が移動を許可したときだけ `release_host_inheritors()` と `place_off_host()` が呼ばれ、host の CPU から外す配置を試みる（`engine/src/program/generate.cpp:21096-21111`; `engine/include/strata/platform/aux_cpus.hpp:256-263,315-348`）。`--aux-cpus` / `STRATA_AUX_CPUS` は配置先の設定であり、serve request の `strata_tune aux_cpus=0|1` はその request 中の aux CPU 配置を切り替える（`engine/src/program/generate.cpp:1463-1469,4715-4724,21431-21440`）。
- Windows では通常、本変数による CPU 配置処理はない。`STRATA_TEST_CONC_ON_HOST_CPU` が設定されている場合に限り、テスト用経路で読取・doorbell スレッドを host の CPU set に置き、その後、本変数が移動を許可すれば CPU set 指定を解除する。`STRATA_TEST_CONC_ON_HOST_CPU` は値の内容でなく設定有無で判定される（`engine/src/program/generate.cpp:21074-21093,21102-21109`）。Linux 以外の aux CPU helper は no-op である（`engine/include/strata/platform/aux_cpus.hpp:407-423`）。

## 実行時の詳細

本変数は `read_part` 内の、同時読み込みに進む条件を満たしたブロックで初めて評価される。値を関数内 `static const bool` に保持するため、そのプロセスでは最初に到達した時点の値が以後も使われ、実行中に環境値を変更しても再読込されない（`engine/src/program/generate.cpp:21054,21070-21073`）。

移動許可時、Linux かつ aux CPU 配置が無効なら、まず host の CPU を継承している既存スレッドを移す。続いて doorbell スレッドと各読取スレッドの冒頭で `conc_thread_cpus` を呼び、aux CPU 配置が無効ならそれぞれを host の CPU から外す。aux CPU 配置が有効なら `pin_current_thread()` による設定済み配置を使う。移動しない値では、既存スレッドの移動処理と新規スレッドの host 外配置を行わないが、別条件を満たせば concurrent read と doorbell service は通常どおり動く（`engine/src/program/generate.cpp:21096-21115,21138-21143,21190-21206`）。

Linux の affinity 設定 API の戻り値はこの呼び出し経路では無視されるため、配置に失敗した場合の専用エラーや fallback ログは確認できない。`release_host_inheritors()` が 1 本以上を移した場合だけ、移動本数を stderr に出す（`engine/src/program/generate.cpp:21098-21101,21110`; `engine/include/strata/platform/aux_cpus.hpp:318-348`）。

## ログと測定値

本変数が直接出すログはない。Linux で先行スレッドを 1 本以上移した場合は `strata batch: %d threads that ran on the host thread's core moved off it, for reads beside the slots` が stderr に出る。Windows の `STRATA_TEST_CONC_ON_HOST_CPU` 経路では初回に CPU set 数と、移動処理を行うかどうかを示す `strata batch: test: the read's and the doorbell threads start on the host thread's %zu CPU set(s)%s` が出る（`engine/src/program/generate.cpp:21086-21093,21098-21101`）。

同時読み込みが実行された場合は、別途読取 token 数・時間・並行して slot が decode した row 数の stderr 行が出るが、これは本変数の値や配置成功を示すログではない（`engine/src/program/generate.cpp:21263-21269`）。`docs/BATCHING.md` の同時読み込み説明と実装を照合したが、本変数自体の定量的な効果を示す測定値は確認できない。

## 根拠

- `engine/src/program/generate.cpp:21068-21111` — 値の取得、既定値、OS 分岐、既存および新規スレッドの配置処理。
- `engine/src/program/generate.cpp:17529-17532,21024-21054` — パイプ構成、同時読み込みの設定・抑止条件、画像と token 数の条件。
- `engine/src/program/generate.cpp:21138-21206` — doorbell と読取スレッドの起動、配置関数の呼び出し。
- `engine/include/strata/program/batch_read.hpp:30-53` — concurrent read を止める構成と理由。
- `engine/include/strata/platform/aux_cpus.hpp:256-263,315-348,407-423` — Linux の配置処理と Linux 以外の no-op 実装。
- `engine/src/program/generate.cpp:1463-1469,4715-4724,21431-21440` — aux CPU 配置の CLI・環境変数・request 単位の設定。
