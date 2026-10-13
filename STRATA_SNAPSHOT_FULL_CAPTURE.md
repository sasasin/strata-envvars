# `STRATA_SNAPSHOT_FULL_CAPTURE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査対象の作業ツリーは `main` で clean。外部ライブラリの環境変数は対象外。

## 役割

サーバーの会話 cache が parked conversation を復元した後、復元済み K/V を次の parking 用に再利用できるよう保持する最適化を無効にします。設定すると、後でその会話を再び park するとき、以前の復元済み K/V を使い回さず、通常の snapshot capture 経路に進みます。Strata の `docs/DETAILS.md` も、この変数が retention を無効化して診断比較に使われると説明しています。

この変数は conversation cache 自体の有効・無効を切り替えません。復元処理や会話状態の保存を省略するものでもありません。

## 値と判定

値の parse はありません。CUDA と SYCL の実装はいずれも `std::getenv(...) == nullptr` かどうかだけを調べます。

| 環境変数の状態 | 復元後の K/V retention |
|---|---|
| 未設定 | retention を試みる |
| 空文字を含む、何らかの値が設定済み | retention を行わない |

`0`、`false`、`off` なども、値の文字列にかかわらず設定済みなら無効化側です。大文字小文字、数値変換、空白、境界値の扱いはありません。判定は `static` 変数に保存されていないため、該当する復元分岐に入るたびにプロセス環境を読みます。通常の起動後に外部から親プロセスの環境を変更しても実行中プロセスの環境は変わらないため、その方法では設定は反映されません。

## 有効になる条件

- `generate.cpp` のサーバー会話 cache 経路であること。会話 cache の容量は `--conversation-cache-mib` と prompt cache の設定から構成され、容量または slot 数が 0 なら cache は有効になりません。
- cache から `incoming` conversation を選び、snapshot の検証・復元に成功して、復元後の処理に進むこと。
- 変数が未設定の場合も、`ConversationCache::retain()` は cache が有効で、保持対象の K/V が残り budget に収まるときだけ retention を採用します。収まらない場合は保持されません。

従って、変数を設定しても、cache が無効、cache hit がない、または復元が成功しない状況では、この分岐による追加の変化はありません。CUDA と SYCL の両実装に同じ判定があります。

## 実行時の詳細

会話 cache から復元した後、通常は snapshot 内の K/V と各 stage の K/V を `conversations.retain(...)` に渡します。cache はそれを次回の parking 時に `take_reuse()` で受け取り、変更されていない K/V ページを snapshot capture に再利用します。`STRATA_SNAPSHOT_FULL_CAPTURE` が設定されている場合は `retain()` 呼び出しを丸ごと飛ばすため、次回の parking は保持済み K/V なしでサイズ見積もりと capture を行います。retention は復元した K/V の追加保持であり、実行中のモデル状態そのものを破棄する処理ではありません。

読み取りは復元後の分岐で行われ、プロセス起動時の一度だけではありません。専用の有効・無効ログはありませんが、通常の会話 cache の restore / park ログには保持 bytes や `reused_kv_bytes` が含まれます。診断比較時はそれらの数値で reuse の有無を観測できます。

## 根拠

- `src/program/generate.cpp:7804-7806` — conversation cache の構成。prompt cache が無効なら容量を 0 にする。
- `src/program/generate.cpp:7923-7965` — 次の parking 時に retained K/V を取り出し、snapshot capture の見積もりと reuse 判定を行う。
- `src/program/generate.cpp:10539-10544` — 復元後の環境変数チェック。未設定時のみ各 stage の K/V を `retain()` に渡す。
- `sycl/src/program/generate.cpp:7512-7554,9792-9797` — SYCL 側の同じ retention / reuse 経路。
- `include/strata/core/conversation_cache.hpp:199-201,217-232` — cache が有効な条件、retention の budget 判定、保持 K/V の取り出し。
- `docs/DETAILS.md:994-1003,1098-1105` — snapshot が復元後に K/V を保持して次の parking で利用する設計と、この変数が retention を診断比較用に無効化する説明。
