# `STRATA_VERIFY_TRACE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の handshake と GPU の進行位置を記録し、Verifier の診断出力や timeout 時に stderr へ trace を出す診断用スイッチです。通常の計算結果を選択する設定ではありません。CUDA/HIP 実装と SYCL 実装の両方に同名の読み取りがあります。

## 値と判定

両実装とも `env_on()` で `getenv()` の戻り値と先頭文字を判定します。文字列全体の parse や大文字小文字の変換はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字列 | OFF |
| 先頭文字が `0` | OFF（例: `0`, `0abc`） |
| その他の先頭文字 | ON（例: `1`, `false`, `off`, ` 1`, `2abc`） |

値はソースファイル内の `const bool g_trace` 初期化時に一度読み取られます。プロセス起動後に環境値を変更しても、この判定は更新されません。

## 有効になる条件

- Verifier を含む CUDA/HIP または SYCL の実行経路で有効です。各 backend の `verify.cpp` に同じ判定があります。
- `g_trace` が ON でも、GPU breadcrumb 用 mapped memory の確保に失敗すると breadcrumb の記録は行われません。ホスト側イベント ring の記録・表示は別に動きます。
- `STRATA_VERIFY_TRACE` 自体は検証器の実行を有効化する設定ではなく、Verifier が実行されなければ記録もありません。

## 実行時の詳細

ON の場合、各 Verifier の `trace_ev()` が呼ばれるたびに handshake event をプロセス共通の 4096 件 ring に記録します。dump ではそのうち末尾最大160件を時刻、Verifier/window/step/layer、フラグ値とともに出します。さらに verifier 初期化時に layer・profiler stamp 点・group 数に応じた mapped breadcrumb 領域を確保し、GPU が通過した stamp を記録します。確保できない場合は領域を null に戻して breadcrumb 部分を省きます。

trace は毎 window 標準出力へ出るものではありません。Verifier の診断 `diag()` が呼ばれた場合に dump が追加され、timeout 経路では stderr に診断、GPU wait 解放後の trace の順に出ます。CUDA/HIP/SYCL 共通の verifier で layer が GPU に通知されないエラー経路にも `trace_dump(stderr)` 呼び出しがありますが、dump 関数自身が `g_trace` OFF なら何も出しません。

trace が ON で mapped breadcrumb の初期化に到達すると stderr に `strata verify trace (#649): on` が出ます。HIP build では同じ行に coherent words、doorbell と関連する HIP 環境値も添えて表示します。このログの表示は trace 開始を示し、breadcrumb 領域確保の成否を保証するものではありません。

## 根拠

- `src/core/verify.cpp:220-228` — CUDA/HIP 側の `env_on()` と `g_trace`。未設定・空・先頭 `0` の判定。
- `sycl/src/core/verify.cpp:93-101` — SYCL 側の同じ判定と `g_trace`。
- `src/core/verify.cpp:468-480,533-558`、`sycl/src/core/verify.cpp:289-301,344-369` — 4096 件 ring、イベント記録、末尾最大160件の出力。
- `src/core/verify.cpp:862-878,1071-1074`、`sycl/src/core/verify.cpp:621-635,837-842` — breadcrumb buffer の確保、初期化ログと GPU stamp。
- `src/core/verify.cpp:592-601,2864-2887`、`sycl/src/core/verify.cpp:403-411,2240-2273` — 診断出力と timeout／layer-not-rang 経路での dump。
- `docs/TROUBLESHOOTING.md:177-179` は同じ issue #649 の resident budget stall と `STRATA_RESIDENT_PIN` を説明しますが、`STRATA_VERIFY_TRACE` の使い方や性能測定値は記載していません。この文書では性能・正確性の測定値を主張しません。
