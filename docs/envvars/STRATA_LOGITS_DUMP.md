# `STRATA_LOGITS_DUMP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

verify の最終段が正常に完了したウィンドウについて、`head_logits_` の全 `T × n_vocab` FP32 値を、指定パスのバイナリファイルへ追記していく診断用 tap です。通常のトークン出力先を変更する処理ではなく、この環境変数を読むコード自体はサンプリング結果 `out` を書き出しません。CUDA/HIP 実装では、条件を満たす head bitplane 経路もこの tap が有効と判定された場合に選ばなくなります（条件は「有効になる条件」参照）。CUDA/HIP と SYCL の verify 実装に読み取りがあります。Metal 経路は `Verifier::run` 内で別経路として先に return するため、この読み取り箇所を通りません。`engine/src/core/verify.cpp:3792-3818,3025-3027,4242-4273`、`engine/sycl/src/core/verify.cpp:2962-2975`。

## 値と判定

値の内容は parse されず、`getenv` が null かどうかだけで判定します。未設定は無効、空文字を含む設定済みの値は有効です。設定値はファイルパスとして `fopen(path, "wb")` に渡されます。`1`、`true`、空白を含む値も真偽値として解釈せず、その文字列をパスとして使います。空文字や開けないパスでは `fopen` が失敗し、記録は行われません。大文字小文字・数値形式・範囲の検査はありません。`engine/src/core/verify.cpp:4250-4253`、`engine/sycl/src/core/verify.cpp:2962-2965`。

| 条件 | unset | 有効になる値 | 無効になる値・結果 |
|---|---|---|---|
| CUDA/HIP または SYCL の verify 最終段 | dump 分岐を通らない | `dump.bin`、`1`、`true` など、空でない任意の文字列（文字列をパスにする） | `""` は設定済みだが空パスで open に失敗し、記録なし。存在しない親ディレクトリなど open 失敗時も記録なし |
| Metal の `Verifier::run` | 環境変数をこの dump 実装では読まない | 該当なし | 該当なし |

他の CLI 引数や環境変数によるパスの上書き・fallback はありません。既存ファイルは最初の open 時に `wb` で切り詰められます。`engine/src/core/verify.cpp:3806,4250-4252`、`engine/sycl/src/core/verify.cpp:2962-2964`。

## 有効になる条件

- CUDA/HIP または SYCL の verify 実装が使われること。Metal の `run` は `window_run` の後に戻り、dump の読み取り箇所を通りません。`engine/src/core/verify.cpp:3792-3818,4185-4191`。
- ウィンドウが `Verifier::run` の head 側まで成功して到達すること。CUDA/HIP では layer split の先行段は `le_ < g.n_layers` の分岐で戻り、SYCL でも `le_ < g.n_layers` で次段へ渡して戻るため、その段自身は記録しません。最終段で dump します。`engine/src/core/verify.cpp:4185-4191,4242-4250`、`engine/sycl/src/core/verify.cpp:2942-2963`。
- `getenv` 時点で値が設定されていること、および出力ファイルを開けること。open 失敗時の代替パスや明示的な警告はありません。`engine/src/core/verify.cpp:4250-4253`、`engine/sycl/src/core/verify.cpp:2962-2966`。
- CUDA/HIP では head bitplane 経路を避ける効果は、head がロード済みで bitplane を持ち、`T <= 16` かつ `(head_->type() == 8 || T >= 4)` の場合に限られます。値の有無は関数内 `static` に保存されます。SYCL の同じ用途の bitplane 判定はこの名前では行われず、dump 分岐だけです。`engine/src/core/verify.cpp:3025-3027`。

## 実行時の詳細

各 verify ウィンドウの通常処理後、トークン出力 `out` へのコピーと `note_nonfinite` の後に環境変数を読みます。CUDA/HIP ではその前に sampling が必要な場合の処理と `cudaStreamSynchronize` があり、そこで失敗すると `false` を返すため dump まで到達しません。SYCL でも sampling 同期の失敗時は先に `false` を返します。したがって、プロンプト処理・生成の全呼び出しではなく、この verify 経路を通り、head 段まで正常に完了したウィンドウが対象です。`engine/src/core/verify.cpp:4192-4233,4242-4254`、`engine/sycl/src/core/verify.cpp:2946-2967`。

dump 分岐に初めて入ったとき、関数内 `static FILE*` が現在の値を使って `wb` で一度だけファイルを開き、ハンドルを保持します。以後のウィンドウも同じファイルへ書きます。分岐の `getenv` 自体は毎ウィンドウ再評価されるため、初回 open 前に設定すれば実行中の設定変更で有効化できます。一方、最初の open 後に値を unset するとその間の記録はスキップされ、別のパスに変更して再設定しても保持中のハンドルを使います。`engine/src/core/verify.cpp:4250-4263`、`engine/sycl/src/core/verify.cpp:2962-2974`。

各記録は 24-byte 相当のヘッダー（`int32 magic=0x53474F4C`、`int32 T`、`int32 n_vocab`、`int32 record`、`int64 position`）の後に `T × n_vocab` 個の float を書きます。`position` はウィンドウ開始位置 `pos0`、各行は順にその位置からの logits です。record 番号は静的カウンターで、CUDA/HIP では device-to-host copy が成功した記録だけ増えます。行は `head_logits_` から取得します。CUDA/HIP は `ensure_full_logits(T, true)` を呼んで split head の logits を materialize し、ホストへ copy します。SYCL は queue の memcpy と wait でホストへコピーします。いずれも各記録後に `fflush` します。`engine/src/core/verify.cpp:4254-4263,5851-5861`、`engine/sycl/src/core/verify.cpp:2966-2974`。

CUDA/HIP では copy 失敗時に最初の一度だけ stderr に `strata verify: STRATA_LOGITS_DUMP copy failed: %s` を出し、CUDA error state を取得します。ファイル open 失敗、`fwrite` / `fflush` の戻り値は検査せず、専用エラーや終了にはつなげません。SYCL の queue copy / wait は例外を投げると verify の外側 catch に進み、`record_verify_sycl_exception("window run", ...)` でエラーを記録して `false` を返します。`engine/src/core/verify.cpp:4250-4272`、`engine/sycl/src/core/verify.cpp:2962-2974,3000-3003`。

CUDA/HIP では別の関数内 `static const bool logits_dump` が head 処理の最初の到達時点で設定有無を一度だけ cache し、その値で条件付き bitplane head 経路を抑止します。空文字も設定ありです。この cache と dump 側の毎回の `getenv` は別の評価です。たとえば cache 初期化後に環境変数を変更すると、dump の on/off は次のウィンドウから反映され得ますが、bitplane 判定は変わりません。SYCL にはこの cache 判定がありません。`engine/src/core/verify.cpp:3025-3027,4250`。

## ログと測定値

CUDA/HIP device-to-host copy の失敗ログは上記のとおりで、同一プロセス中一度だけです。SYCL は専用の `STRATA_LOGITS_DUMP` 失敗文言を出しません。KVA 資料は本変数を「各 verify window の sampler logits を path に書く debug tap」と説明していますが、設定一覧の値型は `on / off` と記載されています。コードでは on/off 値ではなくパスとして扱うため、資料の型表記は実装と一致しません。ログ出力形式と実装は `engine/src/core/verify.cpp:4245-4273`、`engine/sycl/src/core/verify.cpp:2959-2975`。資料の記述は `docs/KVA.md:123`、型表記は `docs/SETTINGS.md:153`。

## 根拠

- `engine/src/core/verify.cpp:3025-3027` — 設定有無の cache と head bitplane 経路の条件。
- `engine/src/core/verify.cpp:4185-4191,4192-4233,4242-4273` — 先行 stage の return、sampling / 同期、record 書き込み、エラー処理。
- `engine/src/core/verify.cpp:5851-5861` — split logits の materialize。
- `engine/sycl/src/core/verify.cpp:2942-2975,3000-3003` — SYCL の先行 stage return、dump と例外経路。
- `docs/SETTINGS.md:153`、`docs/KVA.md:123` — 設定一覧・説明との照合（実装動作の根拠ではない）。
