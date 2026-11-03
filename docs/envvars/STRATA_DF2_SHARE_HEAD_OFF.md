# `STRATA_DF2_SHARE_HEAD_OFF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DFlash2 drafter が MTP drafter の draft-head 行列を借りて使う共有を止めます。通常は、MTP と DFlash2 が同じ語彙 ID 順・同じ型の行列を使えるとき、MTP が確保した行列を再利用し、DFlash2 用の複製を作りません。この変数を設定すると DFlash2 はその共有を使わず、語彙部分行列を自身の領域に用意します。DFlash2 や MTP の有効・無効を切り替える変数ではありません。

DFlash2 の実装は CUDA / HIP ビルドに含まれ、Metal / SYCL ビルドでは含まれません（`CMakeLists.txt:435-436,705`）。

## 値と判定

値の parse はありません。`std::getenv()` が `nullptr` かどうかだけで判定するため、未設定なら共有を許し、値が設定されていれば内容にかかわらず共有を禁止します。空文字、`0`、`false` も「設定あり」です。数値変換、範囲検査、警告はありません。

| 状態 | MTP の draft-head 共有 |
|---|---|
| 未設定 | 他の共有条件も満たせば許可 |
| 設定あり（空文字を含む） | 禁止。DFlash2 が別に行列を用意 |

CLI 引数や他の環境変数からこの判定値を上書きする経路はありません。`STRATA_DF2_HEAD` は別の head 実行方式を選びます。また、`STRATA_MTP_FULL_HEAD`、`STRATA_Q6_PACKED`、`STRATA_MTP_Q8_SM60` や `--mtp-q4 all|head` は共有条件および VRAM 見積もりの条件に関係しますが、`STRATA_DF2_SHARE_HEAD_OFF` の値を上書きしません（`src/program/generate.cpp:6900-6902,6913-6924`）。

## 有効になる条件

この変数が作用するのは、MTP と DFlash2 の両方を使う CUDA / HIP 経路で、DFlash2 が native head 全体を使う設定ではなく、MTP が DFlash2 に渡せる plain draft-head view を持ち、DFlash2 が読む語彙ファイルも読める場合です。MTP の view は、head・型・語彙ファイルが一致し、同じ device にあり、MTP が所有する通常形式の draft head と語彙配列が存在するときだけ提供されます（`src/core/mtp.cpp:646-657`）。

DFlash2 側でも、語彙が空でないこと、共有 head と device 上の語彙があること、head 型・語彙数・語彙 ID の全配列が一致することを確認してから共有します（`src/core/dflash2.cpp:342-351`）。条件が揃わない経路では、この変数の有無にかかわらず共有されません。head が別 GPU にある場合は通常の gather と peer copy、同じ GPU にある場合は通常の gather で DFlash2 用の行列を作ります（`src/core/dflash2.cpp:352-394`）。

## 実行時の詳細

読み取り箇所は 2 つです。`src/program/generate.cpp:6900-6902` では起動時の expert-cache 用 VRAM 見積もりに使い、共有を予測する条件式を満たす場合だけ DFlash2 の head 行列分を 0 bytes と見積もります。設定されていると `df2_expect_share` は false になり、head 行列分を見積もりに含めます（`src/program/generate.cpp:6913-6924,7254-7258,7538-7548`）。このローカル `const bool` は一度計算されます。実際の共有はこの予測式とは別に MTP view と語彙・型の一致を bind 時に確認します（`src/core/mtp.cpp:646-657`, `src/core/dflash2.cpp:345-351`）。

もう一方は DFlash2 の `bind()` 中の判定です。環境値の内容は読まず、関数が呼ばれるたびに `getenv()` の有無を確認します。共有対象が渡されていても変数が設定済みなら共有分岐を飛ばし、語彙行を DFlash2 用に確保して gather します（`src/core/dflash2.cpp:310-312,342-394`）。したがって、起動後に環境を変更する運用では、cache 見積もり時の判定と bind 時の判定が異なる可能性があります。通常の起動では、プロセス開始前に値を設定してください。

bind 成功時の stderr ログは `strata dflash2: ... MiB` として drafter の大きさを出し、共有時だけ `, the MTP drafter's copy, no second one` を付けます（`src/core/dflash2.cpp:395-397`）。この変数だけを理由にした警告や終了はありません。共有を止めた結果、割り当てに失敗した場合は DFlash2 bind のエラーを stderr に出して MTP に fallback し、`--draft-fallback none` で MTP がロードされていない実行では起動を終了します（`src/program/generate.cpp:19703-19708,19720-19723`; serve 経路は `src/program/generate.cpp:11155-11168`）。

## 根拠

- `CMakeLists.txt:435-436,705`: DFlash2 のビルド対象。
- `include/strata/core/dflash2.hpp:56-60`: `STRATA_DF2_HEAD` と共有 head API。
- `src/core/mtp.cpp:646-657`: MTP draft-head view を渡す条件。
- `src/core/dflash2.cpp:310-312,342-397`: DFlash2 bind、共有条件、別行列の作成、ログ。
- `src/program/generate.cpp:6896-6924,7254-7258,7538-7548`: 共有の期待判定と VRAM 見積もり。
- `src/program/generate.cpp:19693-19723,11145-11175`: bind、失敗時 fallback、CLI 実行経路。
