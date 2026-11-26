# `STRATA_DF2_NO_PROMPT_CTX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の `strata serve` で DFlash2 を使うとき、プロンプト読み込み中に計算した tap 行を DFlash2 drafter の context に渡す処理を省略する、測定用フラグです。prompt callback はこの変数が設定されていると即座に成功を返し、`df2.context(...)` を呼びません。コードコメントは、プロンプト行を drafter に渡さないため最初の draft の品質が下がり、プロンプト読込時間から drafter の処理分を切り分けられる用途としています（`engine/sycl/src/program/generate.cpp:7905-7914`）。

この分岐が対象にするのはサーバーの prompt-read callback です。通常の `strata generate` では別の callback が同じ prompt taps を `df2.context(...)` に渡し、この変数を確認しません（`engine/sycl/src/program/generate.cpp:13373-13389`）。

## 値と判定

`std::getenv(...) != nullptr` による設定有無だけの判定です。値の parse、数値変換、文字列比較はありません。未設定なら通常どおり context を更新し、空文字を含め何らかの値が設定されていれば更新をスキップします（`engine/sycl/src/program/generate.cpp:7907-7912`）。

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `strata serve` の DFlash2 prompt callback | skip=false。`df2.context(...)` を実行 | 空文字、`0`、`1`、`false`、その他すべて（設定値の内容は見ない） | 該当なし。環境変数が存在すれば値にかかわらず有効 |
| SYCL `strata generate` の prompt callback | この callback では参照しない | 該当なし | 該当なし。この変数による制御はない |

大文字小文字、前後の空白、数値としての妥当性は判定に影響しません。既定は未設定時の skip=false です（`engine/sycl/src/program/generate.cpp:7908-7912,13373-13376`）。

## 有効になる条件

- SYCL の実行経路であること。名前を読む箇所は `engine/sycl/src/program/generate.cpp` に 1 箇所あり、CUDA/HIP 等の別 backend で同名を読む実装はこの checkout の全参照検索では見つかりません（`engine/sycl/src/program/generate.cpp:7907-7908`）。
- `strata serve` で `--draft dflash2` を選び、DFlash2 の setup が成功していること。DFlash2 には `--draft-model PACK`、`--spec 2` 以上、`--mtp DIR` または `--mtp-draft-vocab FILE` が必要で、複数 GPU、`--batch`、`--pipeline-windows` はこの build では拒否されます（`engine/sycl/src/program/generate.cpp:4499-4517,4557-4567,7892-7903`）。
- DFlash2 tap が設定され、prompt のチャンクに tap rows があると callback が呼ばれます。tap がない経路ではこのフラグの分岐も実行されません（`engine/sycl/src/program/generate.cpp:11105-11117`; `engine/sycl/src/prefill/prefill.cpp:2831-2833,5611-5614`）。
- `strata generate` では prompt callback が `df2.context(...)` を直接呼ぶため、この変数は効きません（`engine/sycl/src/program/generate.cpp:13373-13376`）。

## 実行時の詳細

サーバーはリクエストの DFlash2 tap layers を prefill に設定し、prefill は tap rows があるとき callback を呼びます。callback 内の関数ローカル `static const bool skip` が、最初に callback が実行された時点の環境を一度だけ読みます。したがってプロセス起動後でも初回 callback より前の環境変更は読み取りに反映されますが、初回 callback の後に変更しても、そのプロセス内では反映されません（`engine/sycl/src/program/generate.cpp:7907-7912,11105-11117`; `engine/sycl/src/prefill/prefill.cpp:5611-5614`）。

skip=true の callback は tap rows を `Dflash2Drafter::context` に渡さず `true` を返します。prefill 側は callback が false の場合だけ失敗を返すため、このスキップ自体は prompt 読み込みを失敗させません（`engine/sycl/src/program/generate.cpp:7910-7912`; `engine/sycl/src/prefill/prefill.cpp:5611-5614`）。通常経路では `df2.context` が各 tap row 群を処理し、`have_ctx_` と `ring_hi_` を進めます（`engine/sycl/src/core/dflash2.cpp:740-758`）。

このフラグは request-end の context update を抑止しません。その更新は別経路で `df2.context(...)` を直接呼びます（`engine/sycl/src/program/generate.cpp:12912-12918`）。また、コードコメントは prompt の行を drafter に渡さない場合「最初の drafts は poor」と記しています。draft の品質が変わり得る測定用設定であり、出力の同一性は保証されていません（`engine/sycl/src/program/generate.cpp:7905-7906`）。

## ログと測定値

この変数自体によるログ出力はありません。`STRATA_DF2_TIMING` が設定されていれば通常 callback は `strata serve: DFlash2: prompt context update, %lld rows at %lld, %.1f ms` を stderr に出しますが、skip=true の場合はその前に return するため、この prompt-update ログは出ません（`engine/sycl/src/program/generate.cpp:7908-7914`）。request-end update の timing log は別経路なので、この変数だけでは抑止されません（`engine/sycl/src/program/generate.cpp:12914-12918`）。

この変数を使った性能測定値は、調査対象ソースおよび `docs/DETAILS.md` では確認できません。

## 根拠

- `engine/sycl/src/program/generate.cpp:7905-7917` — 用途コメント、設定有無の static cache、skip 分岐、通常時の context 更新と timing log。
- `engine/sycl/src/program/generate.cpp:4499-4517,4557-4567,7882-7903` — DFlash2 の CLI 要件、非対応構成、serve 側 setup。
- `engine/sycl/src/program/generate.cpp:11105-11117,12912-12918,13373-13389` — リクエスト prompt taps、request-end update、通常 generate 経路との差。
- `engine/sycl/src/prefill/prefill.cpp:2831-2833,5611-5614` — tap rows がある場合の callback 呼び出しと false 時の失敗経路。
- `engine/sycl/src/core/dflash2.cpp:740-758` — 通常時の DFlash2 context 更新と状態の更新。
