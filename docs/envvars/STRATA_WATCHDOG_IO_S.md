# `STRATA_WATCHDOG_IO_S`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリと OS の内部動作は対象外。

## 役割

`--serve` のエンジン watchdog が、進捗 heartbeat のない処理を停止と判断する前に与える、ファイル tier 読み込み中の追加猶予時間（秒）を設定します。値は最長時間の上限であり、その間に Linux のファイル読み込み活動が観測された場合に限って watchdog の停止判断を保留します。通常の生成・単発実行にはこの watchdog は作られません。

## 値と判定

値は `std::getenv()` でエンジンの serve 初期化時に一度読み、`std::atoi()` で整数化されます。文字列全体の検証、無効値のエラー、範囲 clamp はありません。

| 設定 | `io_limit` の値 | 実際の扱い |
|---|---:|---|
| unset | `STRATA_WATCHDOG_S` の有効値の10倍（同変数も unset なら `60` 秒の10倍） | `STRATA_WATCHDOG_S` より大きい場合、ファイル tier 活動が続く間、heartbeat 停止から最大600秒まで猶予 |
| 空文字 | `0` | 通常の watchdog 時間を超える追加猶予なし |
| 数字で始まる文字列 | 先頭の符号・空白と連続する十進数字を `atoi` が読む（例: `120abc` は120、` 120` は120） | `io_limit > STRATA_WATCHDOG_S` の場合だけ追加猶予の候補 |
| 数字として読めない文字列 | `0` | 追加猶予なし |
| 負値または base limit 以下 | その整数値 | `io_limit > limit` を満たさず、追加猶予なし |

`STRATA_WATCHDOG_S` は unset なら60秒で、これを `limit` と呼びます。`limit <= 0` の場合 watchdog thread 自体を起動しないため、この変数も効果がありません。`atoi` の範囲外入力は C/C++ の変換規則上、信頼できる値として扱えません。

## 有効になる条件

- エンジンが `--serve` で起動していること。
- `STRATA_WATCHDOG_S` の `atoi` 結果が正であること。
- `STRATA_WATCHDOG_IO_S` の結果が base の `limit` より大きいこと。
- heartbeat が `limit` 秒以上止まり、追加猶予時間の上限に達する前であること。
- Linux で、直前の約1秒間にファイル tier 活動カウンターが16以上増えること。

活動値はプロセスの `/proc/self/stat` から得る major page fault 数と、`/proc/self/io` の `read_bytes` を MiB 単位に切り捨てた値の合計です。カウンターはプロセス単位であり、Strata が個々のファイル tier 読み込みだけを識別しているわけではありません。Linux 以外では helper が常に0を返すので、環境変数を設定しても活動判定による延期は起きません。活動の有無を問わない単純な timeout 延長にはなりません。

## 実行時の詳細

serve 起動時に `STRATA_WATCHDOG_S` とともに読み取られ、thread に値をコピーします。稼働中の環境変更は再読込されません。watchdog は約1秒ごとに確認し、engine が idle になった時または heartbeat が進んだ時に通常 timeout と追加猶予の計時・活動基準をリセットします。

heartbeat が止まって `limit` 秒を超えた後、`io_limit > limit` かつ追加猶予の総時間内であれば、1秒のサンプル間で活動値が16以上増えた時に停止判定を保留します。最初に保留した時だけ stderr に次の行を出します（以後同じ stall 中は繰り返しません）。

```text
strata serve: no step finished for <limit> s, but the file tier is still being read (slow storage or low RAM): waiting up to <io_limit> s in all (STRATA_WATCHDOG_IO_S) (#1407)
```

活動が見られない、追加猶予の上限に達した、またはこの値が base limit 以下なら、他の明示的な処理猶予 `allow_until_ms` も過ぎた時点で通常の watchdog が stall report を出し、GPU wait を解放して engine を `abort()` します。`STRATA_WATCHDOG_S=0` は watchdog 全体を止めるため、この変数で再び有効にはできません。サーバー側はエンジンログから issue #29 の watchdog 終了を識別します。

## 根拠

- serve 経路と watchdog の読み取り・`atoi`・既定値・thread 起動: `src/program/generate.cpp:6859-6865,8997-9009`。
- 1秒周期、heartbeat ごとのリセット、追加猶予条件、16カウント閾値、ログ、stall 時の終了処理: `src/program/generate.cpp:9011-9049`。
- 活動値の実装（Linux の `/proc` 読み取り、他 OS では0）: `src/program/generate.cpp:1130-1160`。
- watchdog が追う progress heartbeat と明示的猶予の状態: `include/strata/core/progress.hpp:17-27,53-68`。
- サーバーのログ上の watchdog 終了判定: `serve/server.py:814-831`。
- `docs/DETAILS.md:1813` は `STRATA_WATCHDOG_S` の基本動作を説明していますが、`STRATA_WATCHDOG_IO_S` の追加猶予は記載していません。追加猶予の挙動は上記 HEAD の実装を根拠にしています。性能測定値は記載しません。
