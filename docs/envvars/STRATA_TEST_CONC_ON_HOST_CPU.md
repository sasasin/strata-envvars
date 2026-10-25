# `STRATA_TEST_CONC_ON_HOST_CPU`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Windows でパイプ並行読み込みを実行する際、プロンプト読み込みスレッドと doorbell スレッドをホストスレッドと同じ CPU set に一度置くためのテスト用フックです。並行読み込みの有効・無効は切り替えず、そのスレッドの CPU set の初期配置だけに作用します。通常利用者向けの設定ではなく、実装コメントも Windows のテスト用としています。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む何らかの値を設定 | 有効 |

値の文字列や数値は parse せず、`std::getenv(...) != nullptr` で設定有無だけを見ます。値が `0`、`false`、空文字でも有効です。

## 有効になる条件

- Windows ビルドであること。この変数を読むコードと `GetThreadSelectedCpuSets` / `SetThreadSelectedCpuSets` の処理は `_WIN32` 内にあります。他 OS では読み取りません。
- `--batch-groups` を使う層分割の piped 経路で、`piped` が真、`STRATA_PIPED_CONCURRENT` が `atoi` で 0 以外、画像入力がないこと。
- `STRATA_PIPED_CONCURRENT` が要求されても、`STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS`、`--pcie-mode dma`、helper cache、blob を stage する GGUF source、またはその他の expert source がある場合は並行読み込みが停止されます。その場合、この変数の処理にも到達しません。

この変数が未設定でも並行読み込みは通常どおり実行できます。設定しても上記の並行読み込みを有効化するものではありません。

## 実行時の詳細

対象コードブロックに初めて入ったとき `static const bool` として一度読みます。その後の環境変更は同一プロセスでは再評価されません。読み取り後、ホストスレッド上で `GetThreadSelectedCpuSets` を使ってホストの CPU set を取得し、最初の1回だけ次の形式で stderr に出します（`%zu` と suffix は実行状態に応じて変わります）。

```text
strata batch: test: the read's and the doorbell threads start on the host thread's %zu CPU set(s)%s
```

読み込みスレッドと doorbell スレッドでは `conc_thread_cpus` が呼ばれます。Windows では `strata::aux_cpus::pin_current_thread()` は no-op です。対象変数が設定され、ホストの CPU set を取得できた場合は、その set をスレッドに設定します。その後、既定で有効な `STRATA_PIPED_CONCURRENT_UNPIN`（未設定、または `atoi` が 0 以外）も有効なら `SetThreadSelectedCpuSets(..., nullptr, 0)` を呼び、選択 set を解除します。したがって、テスト変数を設定しても最終的にホスト CPU set に留めるには `STRATA_PIPED_CONCURRENT_UNPIN=0` が必要です。CPU set を取得できず空のときは一時設定を行わず、解除呼び出しは `conc_unpin` と対象変数が有効なら行われます。

## 根拠

- 候補名の由来: `docs/000_envvers.md` は候補リストであり、調査対象ソースにおける唯一の読み取りは以下の Windows 実装です。
- `src/program/generate.cpp:12870-12893` — 並行読み込みの環境値判定と実行条件。
- `include/strata/program/batch_read.hpp:30-53` — 並行読み込みを止める設定条件。
- `src/program/generate.cpp:12907-12914` — `STRATA_PIPED_CONCURRENT_UNPIN` の既定値と対象変数の設定有無判定。
- `src/program/generate.cpp:12915-12933,12941-12950` — Windows CPU set の取得、診断ログ、読み込み/doorbell スレッドへの適用・解除。
- `include/strata/platform/aux_cpus.hpp:406-419` — Windows 等 Linux 以外での `aux_cpus` 関数は no-op。
- `docs/BATCHING.md:191-225` — `STRATA_PIPED_CONCURRENT` の用途と起動条件の説明。
