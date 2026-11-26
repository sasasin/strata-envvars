# `STRATA_VERIFY_FIND`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 `strata generate` の expert cache 検証中に、GGUF の blob と GPU cache slot の内容に不一致が見つかった場合、slot 側のデータがどの expert blob に含まれるかを追加で探し、stderr に出します。検証結果や cache の内容を修正する設定ではなく、診断用です。読み取りと処理は `engine/sycl/src/program/generate.cpp` の `verify_all_slots` lambda 内にあります（同ファイル: 5326-5369）。

## 値と判定

値の文字列は parse せず、`std::getenv("STRATA_VERIFY_FIND") != nullptr` だけで判定します（`engine/sycl/src/program/generate.cpp:5344`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL のパイプライン式 fill による全 slot 検証中、不一致を処理するとき | 追加検索をしない | 空文字、`0`、`1`、`false`、その他設定された文字列 | 該当なし。値の内容による無効値判定はない |

設定された値は空文字でも有効です。数値変換、真偽文字列比較、空白除去、大文字小文字の判定、範囲制限はありません。`STRATA_VERIFY_ALL_SLOTS` が未設定なら、この変数が設定されていても検証 lambda 自体が作られず、効果はありません（同ファイル: 5326-5328）。CLI 引数による上書きや別変数からの値の代入はありません。

## 有効になる条件

- SYCL backend の `strata generate` を使う必要があります。この処理は `engine/sycl/CMakeLists.txt:34-47` に含まれる SYCL 側 `src/program/generate.cpp` にあります。
- profile が空でなく、その profile の source が存在する必要があります。処理は `profile` が空でない場合に始まります（`engine/sycl/src/program/generate.cpp:5255-5263`）。
- 全 slot 検証の lambda は、GGUF source を使い、per-layer admission ではなく、かつ `STRATA_FILL_SERIAL` が未設定のパイプライン式 fill の中でのみ作られます。さらに `STRATA_VERIFY_ALL_SLOTS` が設定されている必要があります（同ファイル: 5265-5271, 5326-5328）。`STRATA_FILL_SERIAL` が設定されるとこのパイプライン経路には入らず、全 slot 検証もこのコードでは設定されません。
- 追加検索は検証中に blob の不一致が検出された場合に限ります。検出した不一致数 `bad` が 1 または 2 で、最初の差分位置 `fd` から 4,160 byte 先が blob 内に残る（`fd + 4160 < nb`）場合だけ検索します（同ファイル: 5338-5344）。

## 実行時の詳細

`STRATA_VERIFY_ALL_SLOTS` が設定されると、fill 対象一覧を保持する lambda が作られ、fill 直後に `verify_all_slots("after the fill")` が呼ばれます。session 起動後にも `verify_all_slots("session up")` が呼ばれます（`engine/sycl/src/program/generate.cpp:5326-5369, 6002-6005`）。各回の検証で slot を GGUF から読み直した blob と比較し、不一致ごとに `STRATA_VERIFY_FIND` を読みます。関数内 static cache や起動時の値の保存はなく、環境変数の内容は比較処理ごとに `getenv` で確認されます（同ファイル: 5331-5344）。

追加検索では、slot 側 blob の最初の差分位置から 4,096 byte 後を開始点とする 64 byte を probe とし、fill 対象の各 expert blob を GGUF source から読み直して、その 64 byte 列を含む blob を探します。読み込みに失敗した候補は飛ばし、見つかった各候補について layer、expert、slot、fill 順、blob 内 byte 位置を stderr に出します（同ファイル: 5344-5355）。この検索分岐は診断出力のみを追加し、slot の内容、検証結果の集計、生成処理を変更しません。不一致自体によるエラー終了もこの lambda では行いません（同ファイル: 5362-5369）。

## ログと測定値

probe が候補 blob に見つかった場合、次の形式の行を stderr に出します（数値部分は実行時の値です）。

```text
    the wrong data at byte %zu is expert (layer %d, expert %d), slot %d (fill %zu), byte %zu of its blob
```

候補に見つからなければこの追加行は出ません。slot の不一致ログと集計ログは `STRATA_VERIFY_ALL_SLOTS` の検証処理が出すもので、`STRATA_VERIFY_FIND` 自体のログではありません（`engine/sycl/src/program/generate.cpp:5362-5367`）。Strata の資料にこの追加検索の測定値はありません。`docs/INTEL.md:162-165` は `STRATA_VERIFY_ALL_SLOTS` による全 slot の比較を記載していますが、`STRATA_VERIFY_FIND` の動作は説明していません。

## 根拠

- `engine/sycl/src/program/generate.cpp:5255-5271` — profile fill とパイプライン式経路の条件。
- `engine/sycl/src/program/generate.cpp:5326-5369` — 全 slot 検証の設定、`STRATA_VERIFY_FIND` の存在判定、blob 検索とログ。
- `engine/sycl/src/program/generate.cpp:6002-6005` — session 起動後の検証呼び出し。
- `engine/sycl/CMakeLists.txt:34-47` — SYCL 実行ファイルに使われる generate ソース。
- `docs/INTEL.md:162-165` — 関連する全 slot 比較についての Strata 資料。
