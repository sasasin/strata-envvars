# `STRATA_MMQ_DIRECT_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_MMQ_DIRECT=1` の direct MMQ 経路で、prompt 処理後に各 prefill stage の resident expert 読み取り数と streamed expert 数を stderr に出す診断用スイッチ。読み取り先は `Prefill::run` の成功経路末尾だけで、MMQ の選択・計算・出力はこの変数では変わらない。`mmq::direct_mode() == 1` のときに限り値を評価する（`engine/src/prefill/prefill.cpp:9715-9725`）。

## 値と判定

`std::getenv` で値を取得し、未設定なら false、設定されていれば `std::atoi(v) != 0` を判定する。文字列全体の検証、末尾文字の検査、エラー処理はない。`atoi` は先頭の空白と符号の後にある十進数字の接頭辞を変換し、数字以外に達したところで止まるため、例えば `1`、`-1`、`1tail` は有効、`0`、`0anything`、`true`、`false`、空文字は無効。先頭が数字（または空白・符号の後の数字）でない文字列も 0 として扱われる。数値の範囲制限や clamp はなく、`atoi` の変換可能範囲外の入力はコードで扱いを定めていない（`engine/src/prefill/prefill.cpp:9717-9719`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `mmq::direct_mode() == 1` かつログ判定箇所に到達 | ログなし | `atoi` の結果が非ゼロ（例: `1`, `-1`, `1tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0anything`, `true`） |
| `mmq::direct_mode() != 1` | この箇所では読み取らない | 該当なし | 該当なし |

## 有効になる条件

- `mmq::direct_mode()` が `1` であること。ヘッダーの契約では `1` は guard layout と resident experts の in-place 読み取り、`0` は通常の gather であり、`!tab_built()` の場合は `0`。pointer-table MMQ のビルド条件は CUDA の `STRATA_MMQ_TAB` が有効な場合で、同ヘッダーは HIP、gfx906、SYCL、MMQ なしでは `tab_built()` が false と説明している（`engine/include/strata/prefill/moe_mmq.hpp:146-170`）。
- `Prefill::run` が通常経路で `run_impl` と pipeline drain の両方を成功させ、末尾の診断箇所まで進むこと。`run_impl` または drain が失敗すると `false` で戻り、診断ログは出ない（`engine/src/prefill/prefill.cpp:9705-9725`）。
- Metal 実装は `Prefill::run` 内で先に return する。また layer-major prefill が採用された場合も `run_layer_major` 後に先に return するため、これらの経路ではこの診断ログは出ない（`engine/src/prefill/prefill.cpp:9633-9650`, `9677-9692`）。
- `STRATA_MMQ_DIRECT_LOG` は `STRATA_MMQ_DIRECT` の動作を有効化しない。direct mode 自体が有効でない場合、この変数だけ設定してもログは出ない（`engine/src/prefill/prefill.cpp:9717-9719`）。

## 実行時の詳細

`Prefill::run` の通常経路で prompt body と pipeline drain の成功を確認した後、`mmq::direct_mode() == 1` の条件内で関数ローカル `static const bool` を初期化する。したがって環境値はプロセス起動時ではなく、この条件に初めて入った時に一度だけ読み取られ、その後の呼び出しでは cache された真偽値を使う。初期化後に環境値を変更しても、このログ判定には反映されない。`log` が true なら `this` から `next_` の chain をたどり、各 stage について `stats_.experts_direct`、`stats_.experts_resident`、`stats_.experts_streamed` を出力する（`engine/src/prefill/prefill.cpp:9715-9725`）。

生成経路では `generate` が `prefill.run(...)` を呼び、失敗時は `strata generate: %s` を stderr に出して終了コード `1` を返す。失敗経路では上記の stage 集計ログに到達しない（`engine/src/program/generate.cpp:24163-24167`）。この変数を子プロセスへ転送または上書きする処理は確認できなかった。

## ログと測定値

有効時、各 stage について stderr に次の書式で出力する（値は実行時の統計値）。

```text
strata prefill: layers <開始層>..<終了層>: <in-placeで読んだresident experts数> of <resident experts数> resident experts read in place, <streamed experts数> streamed (STRATA_MMQ_DIRECT, totals)
```

ログは `std::fprintf(stderr, ...)` によるもので、Strata の資料にこの診断変数に関する測定値はない（`engine/src/prefill/prefill.cpp:9719-9724`）。

## 根拠

- `engine/src/prefill/prefill.cpp:9715-9725` — direct mode 条件、`getenv` / `atoi` / static cache、stage ごとの stderr 集計ログ、成功経路。
- `engine/src/prefill/prefill.cpp:9633-9650`, `9677-9692` — Metal と layer-major 経路の早期 return。
- `engine/include/strata/prefill/moe_mmq.hpp:146-170` — pointer-table MMQ のビルド条件と `direct_mode()` の契約。
- `engine/src/program/generate.cpp:24163-24167` — CLI 呼び出し元と prefill 失敗時の stderr・終了。
