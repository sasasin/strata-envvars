# `STRATA_VERIFY_LEAN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の verifier が decode window の SYCL graph を記録するとき、ホストが応答しない条件下で不要になる doorbell 公開、flag 待ち、plan のコピー、PCIe-share の staging と grouped kernel を省きます。`STRATA_VERIFY_LEAN` はこの省略を許可するスイッチで、単独では有効化しません。

## 値と判定

`Verifier::record_window()` 内の関数ローカル `static const bool` として一度評価します。文字列全体や数値は parse せず、先頭文字だけを見ます。

| 値 | `lean_env` |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効 |
| 先頭文字が `0`（例: `0`, `00`, `0false`） | 無効 |
| それ以外（例: `1`, `true`, `false`, 空白） | 有効 |

大文字小文字や後続文字は検査されません。環境変数を最初の `record_window()` 呼び出し後に変更しても、そのプロセスの `lean_env` には反映されません。

## 有効になる条件

実際の `lean` は次の条件の論理積です: `lean_env`、`STRATA_VERIFY_NO_HOST` の有効判定、`device_plan_`、`step_hook_` と `step_hook2_` が未設定、`remote_opt_` が未設定、`always_publish_` が偽、`g_stepped` が偽。条件の一つでも満たさなければ通常の graph nodes を記録します。

このファイルの主役である変数以外の条件について、コード上の判定は次のとおりです。

- `STRATA_VERIFY_NO_HOST` は `record_window()` 内で未設定・空文字・文字列全体が `0` のとき無効。それ以外は有効です。空白、`00`、`false` も有効です。
- `device_plan_` は `STRATA_VERIFY_DEVICE_PLAN` が設定され、`atoi()` の結果が非ゼロで、かつ all-resident window と `always_publish_` のどちらでもない場合に設定されます。割り当てに失敗すると `device_plan_` は解除されます。
- SYCL 以外の backend にはこの変数の読み取り箇所が見つかりません。

同梱の `sycl/serve/strata-sycl.sh` 経由では環境変数の `0` または空文字を Docker に渡さず、既定値を渡します。そのため、この wrapper 経由で `STRATA_VERIFY_LEAN=0` を指定しても、engine には届かず lean の既定有効を無効化できません。直接 SYCL engine を起動した場合は `0` で無効化できます。

## 実行時の詳細

lean が成立すると、各 layer の graph から `doorbell_publish_res()`、device plan 用の flag 待ちと plan copy、PCIe staging の fetch/rebase、PCIe-share の `grouped()` launch を省きます。また device-plan の rows に対する mapped-memory の flag 待ちも省略します。device plan は cache の resident table から計画を作り、CPU share を使わないため、この条件下ではこれらのホスト応答・PCIe-share nodes が不要だと実装コメントに説明されています。

`STRATA_VERIFY_NO_HOST` が有効でも `device_plan_` が無効、または上記の別条件が不成立なら、lean による graph node 省略は行われません。`STRATA_VERIFY_NO_HOST` の実行経路では、`steps` 回のホスト per-layer polling / serving loop を行わず、queue 全体の `cs_->wait()` に進みます。これは `STRATA_VERIFY_NO_HOST` による挙動で、LEAN の graph node 省略とは別です。env の判定は function-local static なので、少なくとも `lean_env` とこの polling 経路の `no_host` はそれぞれ初回評価後にキャッシュされます。

## 文書との照合

`docs/INTEL.md` は `STRATA_VERIFY_NO_HOST` 下の「誰も応答しない graph nodes」を `STRATA_VERIFY_LEAN=0` で無効化できると記述しています。コード上も `0` 始まりの値で無効化されます。ただし、同梱 wrapper は `0` を engine に転送しないため、同じ指定が wrapper 経由でも効くとは限りません。同資料は Arc Pro B70 / Flash-Next IQ3_S の測定項目でこの graph node 省略を -2% と記録しています（`docs/INTEL.md:806-810,830`）。これは資料に記載された構成での測定であり、他の構成の性能を示すものではありません。

## 根拠

- `sycl/src/core/verify.cpp:800-809` — env の読み取り・parse、`lean` の追加条件。
- `sycl/src/core/verify.cpp:723-729,748-772` — `device_plan_` の条件と割り当て失敗時の解除。
- `sycl/src/core/verify.cpp:1351-1359,1452-1483` — lean 時に省かれる doorbell、wait、copy、PCIe staging/grouped nodes。
- `sycl/src/core/verify.cpp:2180-2203,2302-2309` — `STRATA_VERIFY_NO_HOST` による per-layer host loop の省略と window-wide queue wait。
- `sycl/serve/strata-sycl.sh:25-35` — wrapper の既定値と `0` / 空文字を転送対象から外す処理。
- `docs/INTEL.md:806-810,830` — 対応する測定構成と報告値。
