# `STRATA_VERIFY_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

GPU の verify window 内の処理区間に時刻印を取り、GDN/QSA 層などの GPU ステージ時間を集計して出力する診断用スイッチです。通常の `--serve` decode では `STRATA_DECODE_TIMING=1` と併用すると、リクエストごとのログに `strata decode GPU stages (ms/window):` が出ます。これは処理時間を測る機能で、トークン選択や検証条件を設定する変数ではありません。ただし計測用の記録・読出しを行い、一部の融合・並行実行経路を無効にするため、計測時の実行時間は通常経路と同じではありません。`docs/DETAILS.md` も GPU profile は decode を遅くすると説明しています。`engine/src/core/verify.cpp:1516-1518,1548,1610,2621,2847-2860`、`docs/DETAILS.md:364-366`。

環境から値を読む実装は CUDA/HIP 側の `Verifier::init` と SYCL 側の `Verifier::init` にあります。Metal 用の `Verifier::init` はこの読み取り箇所より前に初期化から戻るため、このスイッチによる同じ計測は行いません。`engine/src/core/verify.cpp:956-993,1262-1276`、`engine/sycl/src/core/verify.cpp:624-626,816-829`。

## 値と判定

両実装とも `std::getenv("STRATA_VERIFY_PROFILE") != nullptr` で設定の有無だけを判定し、文字列を parse しません。値が空か、`0` / `false` か、`1` か、大文字小文字、前後の空白、文字列末尾の内容かは問いません。環境変数が存在すれば有効扱い、存在しなければ無効です。CUDA/HIP では記録バッファの確保に失敗すると無効に戻ります。SYCL も device バッファ確保に失敗すると無効に戻します。いずれもこの失敗をこの箇所で利用者向けログには出しません。`engine/src/core/verify.cpp:1262-1276`、`engine/sycl/src/core/verify.cpp:816-829`。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA/HIP の verifier 初期化 | 計測なし | 空文字、`0`、`false`、`1`、`0anything` | 該当なし（変数が設定されていれば値の形式による無効化なし）。計測バッファ確保失敗時は無効化 |
| SYCL の verifier 初期化 | 計測なし | 空文字、`0`、`false`、`1`、`0anything` | 該当なし（変数が設定されていれば値の形式による無効化なし）。計測バッファ確保失敗時は無効化 |
| Metal verifier | 読み取り箇所なし | 該当なし | この変数による計測なし |

CLI 引数や別の設定値でこの判定を上書きする処理はありません。サーバーログへ出す通常の decode profile には別途 `STRATA_DECODE_TIMING` が関係します。`engine/src/core/verify.cpp:1262-1276`、`engine/sycl/src/core/verify.cpp:816-829`、`docs/DETAILS.md:364-365`。

## 有効になる条件

- CUDA/HIP または SYCL の verify window 実装を通り、verifier 初期化が完了すること。Metal 実装は `init` 内で先に戻るため対象外です。`engine/src/core/verify.cpp:978-993,1262`、`engine/sycl/src/core/verify.cpp:624-626,816`。
- 計測バッファの確保が成功すること。失敗時は `prof_on_` を false に戻すため、profile は記録・出力されません。`engine/src/core/verify.cpp:1273-1276`、`engine/sycl/src/core/verify.cpp:817-829`。
- 通常のサーバー decode でリクエストごとの GPU profile を見る場合は `STRATA_DECODE_TIMING=1` も必要です。decode timing 出力ブロックの中で `profile_report()` を呼び、空でない結果を stderr に出します。`engine/src/program/generate.cpp:23352-23358,23385-23390`。プロジェクトの説明もこの二変数の併用を案内しています。`docs/DETAILS.md:364-366`。
- `--batch` 系にも集計後に `profile_report()` を出す経路があります。`STRATA_VERIFY_PROFILE_EVERY` は SYCL の GPU-clock profile を window ごとに途中出力する別変数で、`STRATA_VERIFY_PROFILE` 自体の有効条件ではありません。`engine/src/program/generate.cpp:17495-17509`、`engine/sycl/src/core/verify.cpp:2337-2346,2921-2935`。

## 実行時の詳細

値は verifier の `init` 中に読み、`prof_on_` に保存します。各 verify 呼び出しで環境を読み直す実装ではないため、初期化後の環境変更は既存 verifier には反映されません。後から初期化される別 verifier は、その初期化時点の環境を判定します。CUDA/HIP は GPU 用バッファを確保・ゼロ初期化し、verify window のステージ境界で GPU stamp を追加します。window 終了後にデータをホストへ読み戻し、集計します。`engine/src/core/verify.cpp:1262-1276,1516-1518,3594-3607,4146-4180`。

このフラグは計測だけでなく実行経路にも影響します。CUDA/HIP では `prof_on_` が true のとき、`STRATA_SIDE_MIXER` の分岐ストリーム経路、共有 expert の fork 経路、行コピー融合、hit の combine 融合、融合 wait-and-copy を使わない条件があります。また dispatch の診断行に `prof=1` と記録します。`engine/src/core/verify.cpp:1548,1610,2621,2847-2860,2868-2875,2933-2942`。したがって profile の値は実行時間や並行性を変え得ます。コード上、このフラグ自体がトークンの選択結果を変える設定として使われてはいません。

CUDA/HIP の通常のリクエスト集計は、集めた window 数でステージ時間を平均し、`GDN layers` / `QSA layers` と合計 ms/window を `profile_report()` に整形します。decode timing が有効なサーバー経路では stderr に `strata decode GPU stages (ms/window):` として出力し、複数 GPU stage では stage 番号付きの行も出します。集計後の profile カウンターはリセットされます。`engine/src/core/verify.cpp:3208-3232`、`engine/src/program/generate.cpp:23385-23390`。

SYCL も `init` で設定有無を保存し、確保成功時に buffer を用意します。通常の single-group window (`G == 1`) は集計対象です。`STRATA_VERIFY_EAGER` が設定されていれば window ごとに `verify stages T=... (ms/window):` を出し、未設定なら GPU stamp を集計し、`STRATA_VERIFY_PROFILE_EVERY` が正数ならその数の window ごとに GPU-clock の行を出します。後者の間隔値は関数内 static で初回評価されます。これらの SYCL 出力条件は CUDA/HIP のサーバー出力条件と異なります。`engine/sycl/src/core/verify.cpp:816-829,2919-2935`。

## ログと測定値

CUDA/HIP 側のステージ集計文字列は ` GDN layers:`、` | QSA layers:`、` | total %.2f ms/window over %lld windows` を含み、サーバーでは `strata decode GPU stages (ms/window):` の後ろに出ます。通常の decode timing 自体が無効ならこのサーバー出力経路は呼ばれません。`engine/src/core/verify.cpp:3208-3232`、`engine/src/program/generate.cpp:23352-23358,23385-23390`。

SYCL 側では条件に応じて `verify stages T=%d (ms/window):` または `verify stages T=%d (ms/window over %lld, GPU clock):` を stderr に出します。バッチ window では `STRATA_VERIFY_PROFILE_EVERY` が正数で閾値に達した場合に `verify stages batch window of ... (GPU clock):` を出します。`engine/sycl/src/core/verify.cpp:2337-2346,2919-2935`。

計測バッファ確保失敗時の明示的な profile エラーや fallback 警告は該当箇所にありません。性能値は環境・GPU・backend・モデル等に依存するため、この調査では測定していません。`docs/DETAILS.md:364-366` は profile が decode を遅くすると記載していますが、特定環境での数値は示していません。

## 根拠

- `engine/src/core/verify.cpp:956-993,1262-1276` — CUDA/HIP verifier 初期化、Metal の早期 return、設定有無の判定とバッファ確保。
- `engine/src/core/verify.cpp:1516-1518,1548,1610,2621,2847-2860,2868-2875,2933-2942` — stamp、診断値、profile 時に抑制される実行経路。
- `engine/src/core/verify.cpp:3594-3607,4146-4180,3208-3232` — window 後の集計と report 生成。
- `engine/src/program/generate.cpp:23352-23358,23385-23390,17495-17509` — decode timing/server と batch の出力呼び出し。
- `engine/sycl/src/core/verify.cpp:624-626,816-829,2337-2346,2919-2935` — SYCL 初期化、集計・出力条件。
- `docs/DETAILS.md:364-366` — サーバーでの設定併用例と計測時の速度に関する注意。
