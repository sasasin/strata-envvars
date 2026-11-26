# `STRATA_QSA_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の prompt prefill で各 QSA 層が選んだ cell ID を、指定ファイルへバイナリ追記する診断出力先です。選択や attention の設定値を変えるスイッチではありません。CUDA/HIP 共通の Prefill::run_impl と SYCL の同名 prefill 実装に読み取りがあります。QSA 層の選択処理後、attention の前に実行されます（engine/src/prefill/prefill.cpp:5222-5233, 5347-5350, 5507-5531; engine/sycl/src/prefill/prefill.cpp:3559-3570, 3664-3667, 3820-3845）。

この hook は run_impl 内にあります。CUDA/HIP で layer-major の lm_run 経路が選ばれた場合はこの箇所を通りません（engine/src/prefill/prefill.cpp:8200-8209, 8435-8437）。Metal の prompt は engine/metal/src/engine/window.cpp:3735-3775 の window 経路で処理され、この hook の読み取り箇所はありません。SYCL は独立した engine/sycl/src/prefill/prefill.cpp に同じ読み取り処理を持ちます。

## 値と判定

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP run_impl、SYCL prefill | getenv が nullptr なら出力なし | 値の文字列をそのままファイルパスとして使用。空文字も設定済みとして分岐する | STRATA_QSA_DUMP 自体には文字列の妥当性検査なし。空文字や開けないパスはファイルを開けず出力されない |

値を真偽値や数値に変換せず、getenv(...) != nullptr で有無だけを見ます。1、true、false、0anything はいずれも設定済みで、値の違いは fopen に渡すパスだけです。大小文字や前後空白の正規化もありません（engine/src/prefill/prefill.cpp:5512, 5520; engine/sycl/src/prefill/prefill.cpp:3823, 3838）。

同じ箇所で関連設定も読みます。STRATA_QSA_DUMP_LAST は未設定なら 4096、設定時は atoll で long long に変換します。空文字・数字で始まらない文字列は 0、数字の後ろに続く文字は変換時に無視されます。負数も拒否されず、範囲 clamp はありません。各 chunk の終端 p0 + T が pos0 + n - last より大きいと、その chunk 全体を記録します。そのため last は出力行を厳密に切り詰める上限ではなく、記録する chunk を選ぶ閾値です（CUDA/HIP: engine/src/prefill/prefill.cpp:5513-5516; SYCL: engine/sycl/src/prefill/prefill.cpp:3824-3826）。

CUDA/HIP ではさらに STRATA_QSA_DUMP_LAYER を atoi で読み、未設定時は -1、負値なら全 QSA 層、0 以上ならその QSA 層 index だけを記録します。空文字や不正な先頭文字は 0 になり、後続の非数値文字は無視されます。STRATA_QSA_DUMP_STEPS は値を読まず、設定有無だけで判定し、空文字を含め設定されていれば選択 step 配列も追記します。これら2変数の読み取りは CUDA/HIP 側だけで、SYCL 側は層絞り込みと step 追記を行いません（engine/src/prefill/prefill.cpp:5515-5516, 5524-5528; engine/sycl/src/prefill/prefill.cpp:3823-3842）。

## 有効になる条件

- STRATA_QSA_DUMP が engine プロセスの環境に存在し、該当プロセスが QSA 層を含むモデルの prefill で上記の run_impl / SYCL prefill の処理を通る必要があります。値が未設定なら追加の出力処理はありません（engine/src/prefill/prefill.cpp:5222-5233, 5512; engine/sycl/src/prefill/prefill.cpp:3559-3570, 3823）。
- CUDA/HIP の layer-major lm_run と Metal の window prompt 経路にはこの読み取りがありません。SYCL の同じ prefill 実装には読み取りがあります（engine/src/prefill/prefill.cpp:8200-8209, 8435-8437; engine/metal/src/engine/window.cpp:3743-3775; engine/sycl/src/prefill/prefill.cpp:3823-3826）。
- 判定に CLI 引数や他環境変数との優先順位はありません。CUDA/HIP では STRATA_QSA_DUMP_LAST が対象 chunk を絞り、STRATA_QSA_DUMP_LAYER が記録する層を絞ります。SYCL では STRATA_QSA_DUMP_LAST のみがこの出力の範囲を変えます（同上）。
- ファイルを ab で開ける必要があります。開けなければ記録されません。CUDA/HIP の場合、QSA 選択 ID の device-to-host copy と stream 同期は fopen より前に行われるため、パスが開けなくてもそのコピー・同期は発生します（engine/src/prefill/prefill.cpp:5516-5521; SYCL: engine/sycl/src/prefill/prefill.cpp:3826-3839）。

## 実行時の詳細

各翻訳単位の Prefill::run_impl / SYCL prefill 内にある static const char* dump が、最初に QSA の出力箇所へ到達した時点の getenv 結果を保持します。STRATA_QSA_DUMP_LAST と CUDA/HIP の STRATA_QSA_DUMP_LAYER もブロック内の static で、該当分岐が初めて実行された時の値を保持します。したがって、その後の同一プロセス内で環境を変更しても反映されません。STRATA_QSA_DUMP_STEPS は記録ごとに設定有無を調べます（engine/src/prefill/prefill.cpp:5512-5515, 5524; engine/sycl/src/prefill/prefill.cpp:3823-3825）。

ファイルは "ab" で開き、1 record ごとに int32 4 個の header（QSA 層 index、chunk の p0、T、cap）と T * cap 個の int32 cell ID を追記します。CUDA/HIP では STRATA_QSA_DUMP_STEPS が設定されていれば続けて T * kStepCount 個の step 値も追記します。SYCL は header と cell ID のみです。記録直前に selection ID を host 側へコピーして stream を同期します（engine/src/prefill/prefill.cpp:5516-5529; engine/sycl/src/prefill/prefill.cpp:3826-3843）。

fopen が失敗してもエラー文字列、警告、終了処理はなく、その record は書かれません。fwrite と fclose の戻り値も検査されません（同上）。この hook は選択 ID と step のコピーを行い、selection や attention の入力を書き換える処理はありません（engine/src/prefill/prefill.cpp:5517-5528, 5533-5535; engine/sycl/src/prefill/prefill.cpp:3827-3847）。

## ログと測定値

この変数によるログ出力はありません。成功時の観測結果は指定先へのバイナリ追記です。ファイル open / 書き込み失敗も Strata からは報告されません（engine/src/prefill/prefill.cpp:5520-5529; engine/sycl/src/prefill/prefill.cpp:3838-3843）。性能や正確性の測定値は該当資料にありません。

## 根拠

- engine/src/prefill/prefill.cpp:4214-4224, 5222-5233, 5347-5350, 5507-5535 — CUDA/HIP の Prefill::run_impl、QSA の選択後の出力、後続 attention。
- engine/sycl/src/prefill/prefill.cpp:3559-3570, 3664-3667, 3820-3847 — SYCL の QSA 選択と dump 出力。
- engine/src/prefill/prefill.cpp:8200-8209, 8435-8437 — layer-major lm_run の存在と実装箇所。
- engine/metal/src/engine/window.cpp:3735-3775 — Metal prompt が window 経路で処理される箇所。
