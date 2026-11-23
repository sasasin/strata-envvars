# `STRATA_KFD_QUIET_LOAD`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

統合 AMD gfx11 GPU の Linux/HIP 経路で、エンジンのロード中に GPU/KFD を刺激する一部処理の順序を変えるスイッチです。ON の場合、hyper-connection check を expert arena の確保前へ移し、expert cache 確保後に KFD settle を行い、初回 prompt が使う一部の device/host buffer と pageable copy の経路をロード中に準備します。通常の条件ではこれらはロード後や最初の prompt に遅れて発生します。カーネル自体や計算内容を変更するスイッチではありません（`engine/include/strata/core/kfd_quiet.hpp:1-19,70-93`）。

この変数は実装で実際に `std::getenv` されます。`fix_env(Fix::Load)` が名前を返し、`load_moves()` が共通スイッチ判定へ渡します（`engine/include/strata/core/kfd_quiet.hpp:47-68,81-93`）。

## 値と判定

`std::getenv` の返す文字列全体を parse せず、先頭 1 文字だけを確認します。共通の `STRATA_KFD_QUIET` とこの変数のどちらかが、未設定でなく先頭文字が `0` なら OFF です。それ以外は ON です（`engine/include/strata/core/kfd_quiet.hpp:47-52,65,91-93`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_KFD_QUIET` が先頭 `0` でない | 個別変数は unset なら ON | 空文字、`1`、`true`、`false`、`0anything` 以外の任意の文字列 | `0`、`0anything` |
| `STRATA_KFD_QUIET` が先頭 `0` | 個別変数の値にかかわらず OFF | なし | `STRATA_KFD_QUIET=0`、`STRATA_KFD_QUIET=0anything` |

空文字は設定済みですが、先頭文字が `0` ではないため ON です。`1` や `true` の特別扱い、数値変換、空白除去、大文字小文字の変換はありません。たとえば `false` も ON、` 0` も ON、`0x` は OFF です。個別変数が未設定の場合は ON です（ただし共通変数が先頭 `0` なら OFF）。CLI 引数による上書きはこの判定経路にありません（`engine/include/strata/core/kfd_quiet.hpp:47-52,65,81-93`）。

## 有効になる条件

- `STRATA_USE_HIP` かつ `__linux__` のビルドであること。対象機能の設定と利用箇所はこの条件でコンパイルされます（`engine/src/program/generate.cpp:4332-4360,8436-8443,9665-9670,16221-16239`、`engine/src/prefill/prefill.cpp:2633-2675`）。
- 起動時に GPU が統合 GPU と判定され、`igpu_kfd_settle_default()` が true になること。現在の判定は Linux の統合 GPU で gfx1103、gfx1150、gfx1151、gfx1152、gfx1153 です（`engine/src/program/generate.cpp:4315-4335`; `engine/src/core/arch_defaults.cpp:152-160`）。`kfd_quiet.hpp` 冒頭コメントは gfx1103/gfx1150/gfx1151 と記しますが、実際の `igpu_arena_no_thp_default()` は gfx1152/gfx1153 も列挙しています。動作条件はコードの列挙に基づきます。
- このスイッチは LOAD の処理だけを制御します。兄弟スイッチ `STRATA_KFD_QUIET=0` は LOAD を含む共通の quiet switch を止めますが、`STRATA_KFD_QUIET_EXIT` など他の個別スイッチは LOAD を直接上書きしません（`engine/include/strata/core/kfd_quiet.hpp:47-68,81-93`）。
- hyper-connection check の先行実行は GPU 名が取得できた場合だけです（`engine/src/program/generate.cpp:8433-8443`）。
- 初回 prompt の device buffer 確保は `T > 0` の場合に行い、CPU prompt share の pinned buffer はさらに `cpu_pool_ != nullptr` かつ `cpu_share_on()` の場合だけです。KV copy stream/event の準備は `STRATA_KV_PREFETCH` が設定され、`atoi` の結果が 0 以外の場合だけです（`engine/src/prefill/prefill.cpp:2638-2656`）。これらの条件を満たさない処理は実行されません。
- ロード時の KFD settle は `STRATA_NO_KFD_SETTLE` が未設定・空文字・先頭 `0` 以外だと抑止されます。LOAD の判定が ON でもこの環境変数で settle 呼び出しが no-op になります（`engine/include/strata/core/kfd_settle.hpp:136-149`; 呼び出し元 `engine/src/program/generate.cpp:9665-9670`）。

## 実行時の詳細

環境変数は `load_moves()` の呼び出しごとに `std::getenv` で読み直され、環境値を保存する static cache はありません。デバイスクラスだけは起動時に `class_flag` に設定され、`load_moves()` はその atomic flag とその時点の環境値を組み合わせます（`engine/include/strata/core/kfd_quiet.hpp:40-45,65-68,81-93`; flag の設定 `engine/src/program/generate.cpp:4332-4335`）。したがって、プロセス環境が実行中に変更された場合、以後の `load_moves()` 呼び出しで値が再評価されます。ただし、すでに実行済みのロード処理は巻き戻りません。

ON のときの具体的な箇所は次のとおりです。

- GPU 名の取得後、expert arena が作られる前に `fused_gr_check()` を呼びます（`engine/src/program/generate.cpp:8427-8443`）。
- expert cache の確保後、profile fill 等へ進む前に `settle_before_ready()` を呼びます。settle は KFD eviction counter を読める場合に、counter が 2 秒動かない状態を待ち、最大 10 秒で終わります。counter がない・読めない場合は待ちません（`engine/src/program/generate.cpp:9665-9670`; `engine/include/strata/core/kfd_settle.hpp:113-149`）。
- 最初の prompt の `Prefill::init` で device buffer 等を先行確保します。確保失敗はここでは無視され、prompt 側が従来どおり後から試します（`engine/src/prefill/prefill.cpp:2633-2650`）。CPU share 用 pinned buffer の先行確保も失敗時は prompt 側に委ねます（同 `:2652-2674`）。
- READY 前に 2 MiB の device buffer を確保し、pageable host memory との H2D/D2H copy を一度ずつ試します。device buffer はプロセス中保持し、copy の失敗は無視します（`engine/src/program/generate.cpp:16221-16239`; サイズ `engine/include/strata/core/kfd_quiet.hpp:88-93`）。

別の `settle_before_ready()` 呼び出しが READY 直前にもありますが、こちらは LOAD 判定の外にあり、デバイスクラスと `STRATA_NO_KFD_SETTLE` に従います（`engine/src/program/generate.cpp:16239-16241`; `engine/include/strata/core/kfd_settle.hpp:136-149`）。

## ログと測定値

`STRATA_TRACE` が設定されている（空文字を含む）状態で対象クラスの GPU について LOAD が ON なら、stderr に次の行を出します。

```text
strata trace: kfd quiet: load order active (check first, settle after the expert cache, first prompt's buffers at init)
```

これはロード順を示すログです。LOAD が OFF、クラス外、または `STRATA_TRACE` が未設定ならこの行は出ません（`engine/src/program/generate.cpp:4351-4352`）。staged copy の試行後は、`STRATA_TRACE` があれば `strata trace: kfd quiet: staged copy before READY done` または `strata trace: kfd quiet: staged copy before READY skipped (no device memory)` が stderr に出ます。これは device buffer 確保の成否を示し、copy 自体の成功を報告するものではありません（`engine/src/program/generate.cpp:16226-16237`）。

settle 自体はログを出しません（`engine/include/strata/core/kfd_settle.hpp:136-149`）。この変数について参照できる測定値はなく、性能や失敗率の変化はここでは述べません。

## 根拠

- `engine/include/strata/core/kfd_quiet.hpp:47-93` — スイッチ値の判定、動的な変数名、LOAD の処理フラグ。
- `engine/src/program/generate.cpp:4332-4352` — HIP/Linux と GPU クラスの flag 設定、LOAD の trace log。
- `engine/src/core/arch_defaults.cpp:152-160` — 実際の統合 GPU 対象アーキテクチャ。
- `engine/src/program/generate.cpp:8427-8443,9665-9670,16221-16241` — check、cache 後 settle、READY 前 copy warm の呼び出し。
- `engine/src/prefill/prefill.cpp:2633-2675` — 初回 prompt と CPU share buffer の先行確保。
- `engine/include/strata/core/kfd_settle.hpp:113-149` — settle の待機条件、時間上限、抑止条件。
