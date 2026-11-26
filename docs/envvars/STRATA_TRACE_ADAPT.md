# `STRATA_TRACE_ADAPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

speculative decode の適応 VRAM expert tier が行う交換ラウンドについて、検討開始・保留・交換件数と、前ラウンドの非同期コピーが次の window までに完了したかを stderr に記録する診断用変数です。値は適応処理の有効化や交換候補の選択には使われず、ログ出力条件にだけ使われます。実際に適応処理が走るには、別途 `adapt_every` と `adapt_swaps` によって usage 計測が有効である必要があります（CUDA/HIP/GFX906: `engine/src/program/generate.cpp:24570,25188-25191`、SYCL: `engine/sycl/src/program/generate.cpp:13800,14185-14188`）。

## 値と判定

CUDA/HIP/GFX906 の共有 GPU 実装と SYCL 実装で `std::getenv("STRATA_TRACE_ADAPT") != nullptr` を使います。文字列の変換や内容の比較はありません。したがって未設定だけが無効で、空文字、`0`、`false`、大文字小文字を含む任意の設定値はいずれも有効です。数値・空白・境界値の検査はありません（CUDA/HIP/GFX906: `engine/src/program/generate.cpp:24670-24717`、SYCL: `engine/sycl/src/program/generate.cpp:13822-13871`）。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP/GFX906 共有 GPU 実装の speculative decode | ログなし | 値の内容を問わず、例: 空文字、`0`、`1`、`false` | なし（環境変数自体が未設定の場合だけ無効） |
| SYCL speculative decode | ログなし | 値の内容を問わず、例: 空文字、`0`、`1`、`false` | なし（環境変数自体が未設定の場合だけ無効） |

## 有効になる条件

- CUDA/HIP/GFX906 共有 GPU 実装 (`engine/src/program/generate.cpp`) または SYCL (`engine/sycl/src/program/generate.cpp`) の該当 speculative decode 実装を使うこと。両実装に同じ名前の読み取り箇所が各 2 箇所あります。
- 適応 tier が有効で、decode loop が適応ラウンドを開始すること。共有 GPU 実装は usage が空でなく、pending 交換がなく、`(rounds + 1) % o.adapt_iv(rounds) == 0` のとき、SYCL は usage が空でなく、pending 交換がなく、`(rounds + 1) % o.adapt_every == 0` のときにラウンドを開始します。既定値は `adapt_every=4`、`adapt_swaps=96` で、`--adapt-every` と `--adapt-swaps` がそれぞれを設定します（`engine/src/program/generate.cpp:1045-1048,1084-1085,4058,4202,25188-25191`、SYCL の呼び出し条件は `engine/sycl/src/program/generate.cpp:14185-14188`）。
- pending コピーの着地ログは、前ラウンドからの pending がある状態で次の window が `apply_pending` を呼んだ場合に限られます。pending が空ならこの関数は先に戻るため、そのログは出ません（CUDA/HIP/GFX906: `engine/src/program/generate.cpp:24670-24682`、SYCL: `engine/sycl/src/program/generate.cpp:13822-13837`）。
- `STRATA_TRACE_ADAPT` 自体に OS、CLI、モデル状態、別環境変数による値の上書きはありません。適応 tier の条件を満たさない場合、この変数を設定しても該当ログは出ません。

## 実行時の詳細

`adapt` lambda 内と `apply_pending` lambda 内に独立した関数内 `static const bool` があり、それぞれの lambda が初めて呼ばれた時点で環境変数の有無を一度だけ読みます（CUDA/HIP/GFX906: `engine/src/program/generate.cpp:24670-24717`、SYCL: `engine/sycl/src/program/generate.cpp:13822-13871`）。このため、プロセス起動後に環境変数を変更しても、該当 static の初期化後はそのログ条件に反映されません。2 つの static は初回評価時期も独立しています。

`adapt` は pending が残っている場合は `SKIPPED` を記録してラウンドを終え、pending がなければ `considering` を記録して通常の候補選定・交換処理を続けます。終了時には交換数を記録します。`apply_pending` はイベントを待つか完了状態を調べ、未完了なら「未着地・この window では非 resident」のログを出して戻り、完了していれば「着地・resident になる」ログの後に residency table などの通常処理を進めます。ログ用 bool はこれらの処理分岐の条件ではありません（CUDA/HIP/GFX906: `engine/src/program/generate.cpp:24670-24717,24739-24804`、SYCL: `engine/sycl/src/program/generate.cpp:13822-13871,13889-13951`）。

## ログと測定値

値が設定され、該当処理に到達した場合に stderr に次の文字列を出します（両 backend 共通）。`%lld` と `%zu` / `%d` は実行時のラウンド番号・件数・上限で置換されます。

- `strata: PENDING not landed, %zu stay non-resident this window`
- `strata: PENDING landed, %zu experts become resident`
- `strata: ADAPT round=%lld SKIPPED, %zu swaps still in flight`
- `strata: ADAPT round=%lld considering`
- `strata: ADAPT round=%lld swapped %zu of %d slots, usage decayed`

ログが無効でも適応交換や pending の処理自体は同じコード経路で行われます。ただしログ出力は適応処理のスレッド上でも実行され、非同期コピーの完了タイミングが変わる余地があります。ソースにはコピー時期により GPU / CPU のどちらで expert を処理するかが変わり得るとの説明があります（`engine/src/program/generate.cpp:25099-25103`）。よってこの診断を有効にした実行が、ログなしの実行と timing-sensitive な結果まで常に一致するとは断定できません。測定値は該当なしです。

## 根拠

- `engine/src/program/generate.cpp:24670-24717` — 共有 GPU 実装の pending / adapt ログ条件と文字列。
- `engine/src/program/generate.cpp:24739-24804` — CUDA/HIP/GFX906 共有 GPU 実装の交換候補処理、失敗経路、交換完了ログ。
- `engine/src/program/generate.cpp:1045-1048,1084-1085,4058,4202,24570,25188-25191` — 適応 tier の既定値、CLI 設定、usage とラウンドの条件。
- `engine/src/program/generate.cpp:25099-25103` — 非同期コピーの完了時期に関する経路。
- `engine/sycl/src/program/generate.cpp:13822-13871` — SYCL の pending / adapt ログ条件と文字列。
- `engine/sycl/src/program/generate.cpp:13889-13951,14185-14188` — SYCL の交換処理と適応ラウンド開始条件。
