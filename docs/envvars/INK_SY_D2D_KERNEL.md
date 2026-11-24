# `INK_SY_D2D_KERNEL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling 2 の SYCL 実装にある device-to-device copy helper `ink_sycl::d2d()` のコピー方法を切り替える実験用スイッチです。先頭文字が `1` の場合、サイズとポインタが条件を満たす copy を `sycl::queue::parallel_for` の小さな kernel で行い、それ以外は `Q().memcpy()` に進みます。対象はこの helper を通るコピーだけで、host-to-device や device-to-host の helper は切り替えません（`engine/src/inkling2/sycl/ink_sy_common.h:347-370`）。

呼び出し元にはスロット状態の snapshot / rollback やモデル処理中の device buffer copy があります。たとえば `snapshot_slot()` / `rollback_slot()` は履歴・snapshot・リング間のコピーに `d2d()` を使い、runner の他の経路も activation や residual buffer をコピーします（`engine/src/inkling2/sycl/ink_sy_runner.h:359-390`, `546-572`, `679-685`, `829-845`, `959-974`）。このスイッチが変えるのはコピーの実装方法です。helper の kernel は `uint32_t` 単位で元の要素を destination に代入します。コメントは queue copy と「same bytes」と記していますが、性能差やモデル出力への影響をこの調査で測定したものではありません（`engine/src/inkling2/sycl/ink_sy_common.h:351-369`）。

## 値と判定

値は `std::getenv()` で読み、文字列全体の parse や数値変換はせず `e[0] == '1'` だけを調べます。設定値の先頭 1 byte が ASCII `1` なら有効です（`engine/src/inkling2/sycl/ink_sy_common.h:352-354`）。

| ビルド / 呼び出し条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Inkling 2 SYCL の `d2d()`。ただし後述のサイズ・整列条件も必要 | `false`（queue copy） | `1`, `10`, `1anything`（先頭 byte が `1`） | 空文字、`0`, `01`, `true`, ` 1` など先頭 byte が `1` でない値 |

空文字は設定済みポインタですが、`e[0]` が `\0` なので無効です。大文字小文字、空白、後続文字の妥当性は検査されません。たとえば `1true` も先頭が `1` のため有効です。値の境界は文字列の先頭 byte のみで決まり、整数の範囲や負値の数値解釈はありません（`engine/src/inkling2/sycl/ink_sy_common.h:353`）。

## 有効になる条件

- Inkling 2 SYCL 実装の `ink_sycl::d2d()` が呼ばれること。共通ヘッダーは SYCL backend の runner から取り込まれます（`engine/src/inkling2/sycl/ink_sy_runner.h:24`; `engine/src/inkling2/sycl/ink_sycl_backend.cpp:1-17`）。
- `d2d()` の byte 数 `b` が 0 より大きいこと。0 byte なら環境変数を調べず return します（`engine/src/inkling2/sycl/ink_sy_common.h:356-358`）。
- 設定値の先頭 byte が `1` であること（`engine/src/inkling2/sycl/ink_sy_common.h:353`, `358`）。
- byte 数が 4 の倍数で、source と destination のアドレスがともに 4 byte 整列していること。条件を満たさなければ設定が有効でも `Q().memcpy()` に fallback します（`engine/src/inkling2/sycl/ink_sy_common.h:358-369`）。

このヘルパーの分岐には OS、GPU 世代、別環境変数、CLI 引数、モデル状態による追加判定はありません。バックエンドの適用範囲は SYCL 実装内です。CLI 引数・設定ファイル・別環境変数がこの値を優先または上書きする読み取り箇所は、対象名の全参照検索では確認できません。

## 実行時の詳細

`d2d_kernel_mode()` の関数内 `static const bool` が初めて評価されるときに一度だけ `getenv()` を実行します。通常の非 0 byte `d2d()` 呼び出しが最初の評価点です。その時点で環境変数が未設定、空、または先頭文字が `1` 以外なら `false` が保存され、以後そのプロセス内で環境変数を変更しても再評価されません。0 byte の `d2d()` は早期 return するので、まだ判定を起こしません（`engine/src/inkling2/sycl/ink_sy_common.h:352-358`）。

有効でサイズ・整列条件を満たす場合、`n = b / 4` 個の 32-bit 値を処理する 1D kernel を enqueue します。global range は `n` を 256 work-item 単位に切り上げ、各 work-item は `i < n` のときだけ 1 要素をコピーします。kernel はこの関数内で wait せず return します。条件を満たさない場合も helper は `Q().memcpy(dst, src, b)` を enqueue して wait しません（`engine/src/inkling2/sycl/ink_sy_common.h:356-370`）。

## ログと測定値

この変数の値や選択された copy 経路を出力するログ、独自のエラー・終了分岐は helper 内にありません（`engine/src/inkling2/sycl/ink_sy_common.h:351-370`）。`docs/DETAILS.md` と関連資料に、この変数を使った条件付き性能測定値は見つかりませんでした。コメントにある Level Zero copy-engine sync cost は実験の意図であり、性能結果ではありません（`engine/src/inkling2/sycl/ink_sy_common.h:351`）。

## 根拠

- 読み取りと値判定、初回 cache、copy 分岐: `engine/src/inkling2/sycl/ink_sy_common.h:351-370`
- SYCL runner から共通ヘッダーへの接続: `engine/src/inkling2/sycl/ink_sy_runner.h:24`; `engine/src/inkling2/sycl/ink_sycl_backend.cpp:15-17`
- `d2d()` の呼び出し例（snapshot / rollback、activation / residual、D-Spark buffer）: `engine/src/inkling2/sycl/ink_sy_runner.h:359-390`, `546-572`, `679-685`, `829-845`, `959-974`
