# `STRATA_VERIFY_COMPLEMENT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`strata generate` が expert profile から GPU expert cache を埋めた後、現在 resident な各 slot の内容を GPU からホストへ読み戻して checksum を計算し、stderr に出す診断用フックです。ソース内コメントは `tests` 用としています。checksum を期待値と比較したり、失敗時に実行を止めたりする検証ではなく、ログに値と read-back エラーの有無を出します。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | checksum 計算を行わない |
| 空文字を含む、何らかの値が設定済み | checksum 計算を行う |

値の内容は読まず、`std::getenv("STRATA_VERIFY_COMPLEMENT") != nullptr` の設定有無だけで判定します。したがって `0`、`false`、空文字も有効化します。数値変換や文字列比較はありません。

## 有効になる条件

判定箇所は `src/program/generate.cpp` の profile fill ブロック内です。そのため、`profile` が空でなく、expert source (`srcp`) が存在する実行でのみ環境変数が評価されます。これは `strata` 実行ファイルにあるフックです。確認した同名参照はこの一箇所のみで、`sycl/src/program/generate.cpp` にはありません。

## 実行時の詳細

profile の先頭 pair に対応する slot の read-back 検証と fill 完了ログの後、環境変数が設定されていれば、全 layer と全 expert を走査し、cache 上の slot がある expert を `(slot, blob bytes)` として集めて slot 順に並べます。各 slot の device memory を `cudaMemcpy(..., cudaMemcpyDeviceToHost)` で読み戻し、blob bytes に FNV-1a 64-bit hash を計算します。最大7本の worker thread と呼び出し元 thread が slot を分担します。最後に slot 番号、blob byte 数、slot ごとの hash を順につないで全体 hash を作ります。

stderr の出力形式は `strata generate: expert cache checksum %016llx (%zu slots%s)` です。read-back の `cudaMemcpy` が一度でも失敗すると末尾に `, A READ-BACK FAILED` が付きますが、戻り値は検査されず、このフック自体は処理を中断しません。環境変数は profile fill の後に判定され、static cache はありません。この箇所での判定後に値を変更しても再評価されません。

## 根拠

- `src/program/generate.cpp:5213-5214` は profile が空でなく source がある場合に fill を行うブロックを示します。
- `src/program/generate.cpp:5256-5270` は先行する slot 0 検証・fill ログと、環境変数の設定有無による分岐を示します。
- `src/program/generate.cpp:5271-5301` は resident slot の列挙、D2H read-back、並列 hash、stderr 出力を示します。
- `src/core/pinned.cu:286-292` は FNV-1a 64-bit hash の実装です。
- `CMakeLists.txt:585-606` は `src/program/generate.cpp` が `strata` 実行ファイルのソースであることを示します。
- `docs/DETAILS.md` の確認範囲では、この環境変数や checksum フックの説明は見つかりませんでした。
