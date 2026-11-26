# `STRATA_PREFILL_COPY_WAIT_DEDUPE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。調査時の checkout は `main...origin/main` で、作業ツリーに変更はなかった。

## 役割

ストリーミング prefill の issuer thread が、expert 用 ring slot を再利用するときに copy stream へ積む release event wait を重複排除する。直前の slot と同じ release event が必要で、かつ同じ event が同じ flush で記録されたと分かる場合、前の wait が後の slot も保護するため、その slot の `cudaStreamWaitEvent` を省く。コピーする blob、順序、ring slot は変えず、待ちの投入だけを減らす実装である（`engine/src/prefill/prefill.cpp:4883-4914`、判定関数 `engine/include/strata/prefill/copy_events.hpp:35-42`）。

この判定は `engine/src/prefill/prefill.cpp` の `Prefill::run_impl` にある。リポジトリ全体の名前検索では環境から値を読む箇所はここだけだった。Metal と SYCL はそれぞれ別の prefill ソースをビルドする構成であり、そこでこの名前を読む実装は見つからなかった（`engine/metal/CMakeLists.txt:136-146`、`engine/sycl/CMakeLists.txt:303-308`）。

## 値と判定

`std::getenv` で値を読み、未設定なら false、設定されていれば `std::atoi(v) != 0` を使う。空文字・数字に変換できない文字列・`0`・`0anything` は false。`1`、`-1`、`2`、`1anything` は atoi の結果が非ゼロなので true。先頭空白の後の数字は変換され、後続文字は全体検証されない。大文字小文字の判定や追加の数値範囲チェックはない。値は bool に変換され、数値の大小は機能に影響しない（`engine/src/prefill/prefill.cpp:4765-4768`）。

| 条件 | unset | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| `Prefill::run_impl` のこの実装 | false | atoi の結果が非ゼロ（例: `1`, `-1`, `1anything`） | atoi の結果が 0（例: 空文字, `0`, `0anything`, `true`） |

## 有効になる条件

- その chunk が `stream_all` 経路であること。コード上は `m.ring > STAGE`（`STAGE` は 8）、`T >= stream_all_min()`、かつ `m.src != nullptr` のすべてが必要（`engine/src/prefill/prefill.cpp:321-324, 4625-4629`）。
- `STRATA_PREFILL_ISSUER` が issuer thread を無効化していないこと。`issuer_on` は未設定なら true、設定値は `atoi(v) != 0` で判定し、`threaded_issue = stream_all && issuer_on` のときだけ dedupe の待ち処理が実行される（`engine/src/prefill/prefill.cpp:4753-4760, 4807, 4883-4895`）。
- 既存 slot の再利用であること（`m.stage_live[sl]` が true）。さらに、ring が `MMQ_GROUP`（16）より長く、現在の entry index が ring 長より大きく、今回の slot と直前 slot の release event index が同じ場合に限って wait を省略する。それ以外の再利用では従来どおり wait する（`engine/src/prefill/prefill.cpp:1913-1916, 4883-4898`; 判定式は `engine/include/strata/prefill/copy_events.hpp:40-42`）。
- `STRATA_PREFILL_COPY_EVENT_EVERY` はこの dedupe 判定の無効条件ではない。両方を有効にできるが、`STRATA_PREFILL_ROUTED_STREAM` の routed walk は `copy_wait_dedupe` が true だと適用対象外になり、理由ログにより既定 issuer に戻る（`engine/src/prefill/prefill.cpp:4761-4768, 4777-4795`; `engine/include/strata/prefill/routed_stream.hpp:42-57`）。
- この判定に CLI 引数や別設定値からの上書きはない。値は当該環境変数から直接決まり、他の環境変数との相互作用は上記の issuer 有効条件と routed-stream の適用除外である（`engine/src/prefill/prefill.cpp:4757-4780, 4807`）。

## 実行時の詳細

値は関数内 `static const bool` の初期化ラムダで初回に読み取られ、その後はプロセス内で cache される。したがって、プロセス起動後に環境を変更しても再読み込みされない。CLI の設定やリクエストごとの再評価も行わない（`engine/src/prefill/prefill.cpp:4214, 4765-4768`）。

issuer thread は entry ごとに ring slot を決め、slot が既に使われていれば release event `m.used[rel]` を待ってから次の copy を enqueue する。対象条件を満たしたときだけその wait 呼び出しを飛ばし、`iss_dedup` を増やす。それ以外は `cudaStreamWaitEvent` を呼んで `iss_waits` を増やす。後続の host-to-device copy と copied event 記録はどちらの分岐でも続く。slot の最初の使用時には release wait 自体がない（`engine/src/prefill/prefill.cpp:4883-4914`）。

この変数専用の timeout、終了条件、fallback、エラー文字列はない。ここでの `cudaStreamWaitEvent`、copy、event record の戻り値を調べてこの変数固有の失敗処理へ分岐するコードもない（`engine/src/prefill/prefill.cpp:4890-4914`）。

## ログと測定値

threaded issuer で `copy_event_every > 1` またはこの変数が有効なら、プロセス内で一度だけ stderr に次の形式を出す。末尾は `one wait per release event`（dedupe 有効）または `a wait per slot`（dedupe 無効）になる。

```text
strata: prompt copies: a copied event every %d streamed experts (STRATA_PREFILL_COPY_EVENT_EVERY), %s (STRATA_PREFILL_COPY_WAIT_DEDUPE)
```

また、`STRATA_PREFILL_COPY_WAIT_DEDUPE` が有効で、`STRATA_PREFILL_TIMING` が設定されている場合は、issuer join 後に chunk ごとの実 wait 数と省略数を stderr に出す。`STRATA_PREFILL_TIMING` はここでは値ではなく設定有無で判定される（`engine/src/prefill/prefill.cpp:4016-4022, 4816-4824, 7730-7743`）。

```text
strata prefill copies: %lld slot waits, %lld skipped as the same release event
```

この変数単独の性能測定値は、調査対象のソースと `docs/DETAILS.md` で確認できなかったため記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:4757-4768` — issuer と対象変数の読み取り、既定値、cache。
- `engine/src/prefill/prefill.cpp:4625-4629, 4807-4817` — streamed chunk と threaded issuer の適用条件。
- `engine/src/prefill/prefill.cpp:4883-4914`、`engine/include/strata/prefill/copy_events.hpp:35-42` — wait 省略条件と後続 copy。
- `engine/src/prefill/prefill.cpp:4816-4824, 7730-7743` — stderr ログ条件と文言。
- `engine/include/strata/prefill/routed_stream.hpp:42-57` — dedupe 有効時に routed stream を適用しない条件。
