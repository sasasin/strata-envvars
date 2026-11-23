# `STRATA_SPIN_LOG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL backend で GPU の待ち上限を初めて決めたとき、その上限を stderr に表示する診断用スイッチ。GPU の待ち上限自体や decode・verify の計算を変更せず、ログを出すかどうかだけに関わる。実装は `strata::spin_max` にある。`STRATA_SPIN_LOG` の直接参照はこの 1 箇所で、他の読み取り箇所は見つからなかった（`engine/sycl/include/strata/sycl_doorbell.hpp:164-179`）。

## 値と判定

文字列を変換せず `std::getenv(...) != nullptr` で設定の有無だけを見る。未設定なら、そのデバイスで最初に `spin_max` が呼ばれたときのログを抑制する。空文字を含め、何らかの値が設定されていれば最初のログを許可する。`0`、`1`、`true` などの内容・大文字小文字・空白・数値としての妥当性は判定しない（`engine/sycl/include/strata/sycl_doorbell.hpp:173-176`）。

| 条件（build など） | unset | 設定時にログが有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL backend の `spin_max` | 各デバイスの初回ログを抑制 | 空文字、`0`、`1`、`true`、その他すべての文字列。値の内容は無視 | なし（設定値の内容による無効値はない） |

## 有効になる条件

- SYCL backend を含む実行ファイルで、`strata::spin_max` が呼ばれること。呼び出し箇所には doorbell wait と SYCL verify の flag wait がある（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:404-420`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2829-2844,2891-2905`）。
- デバイスごとの初回呼び出し時に環境変数が設定済みなら、その時点でログを出す。初回に未設定でキャッシュが作られた後、変数だけを設定しても、上限が変化しない限り追加ログは出ない。上限が変化した場合は `STRATA_SPIN_LOG` の有無にかかわらず変更ログを出す（`engine/sycl/include/strata/sycl_doorbell.hpp:164-177`）。
- ログに表示する待ち上限は `STRATA_SPIN_LOG` の値ではなく、`spin_max` が別途決めた読み取り回数である。上限の選択には `STRATA_SPIN_MAX`、SYCL build macro `STRATA_SYCL_SPIN_MAX`、driver/device 情報、host wait / long-drafts の状態が関わる（`engine/sycl/include/strata/sycl_doorbell.hpp:126-162,169-176`）。

## 実行時の詳細

`spin_max(queue)` は呼び出しごとに実行され、デバイスごとの直近の上限を `static std::unordered_map` に保持する。このキャッシュは上限変更の検知とログ抑制に使われる。初回呼び出しでは、`STRATA_SPIN_LOG` が設定されていれば `strata: GPU wait bound %u reads on a device` を stderr に出す。後続呼び出しで同じ上限なら何も出さず、異なる上限なら ` (changed)` 付きの行を stderr に出す。`STRATA_SPIN_LOG` 自体は上限計算に使われず、プロセス実行中に設定・解除しても待ち回数は変わらない（`engine/sycl/include/strata/sycl_doorbell.hpp:164-179`）。

この変数による終了・失敗経路はない。待ちが実際に上限切れとなった際の window/token 破棄やエラーは待ち処理側の結果であり、このログスイッチによるものではない（例: `engine/sycl/src/core/session.cpp:1447-1456`、`engine/sycl/src/core/verify.cpp:480-498`）。

## ログと測定値

初回ログの実装文字列は `strata: GPU wait bound %u reads on a device\n`、上限変更時は `strata: GPU wait bound %u reads on a device (changed)\n`。出力先は stderr。測定値はこの変数のログ条件には該当しない（`engine/sycl/include/strata/sycl_doorbell.hpp:175-176`）。

## 根拠

- `engine/sycl/include/strata/sycl_doorbell.hpp:164-179` — per-device cache、環境変数の設定有無判定、ログ文字列・条件。
- `engine/sycl/include/strata/sycl_doorbell.hpp:126-162` — 表示対象となる待ち上限の選択要因。
- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:404-421`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2829-2844,2891-2905` — SYCL の wait kernel 起動前に `spin_max` を呼ぶ箇所。
- `engine/sycl/src/core/session.cpp:1447-1456`、`engine/sycl/src/core/verify.cpp:480-498` — 待ち上限切れ時に別途エラーとして報告する経路。
