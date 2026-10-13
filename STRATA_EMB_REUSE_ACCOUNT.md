# `STRATA_EMB_REUSE_ACCOUNT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト処理用バッファの必要量を見積もる planner に、実際には別バッファと領域を共有する `bo` の分を数えないよう指示します。対象は `Prefill::bytes_needed_impl()` の見積もりです。値を有効にしても GPU バッファの割り当て方式自体は変わらず、主に自動 chunk 選択や expert cache から借りる枠数の判断が変わります。

## 値と判定

環境変数の文字列全体や数値としての妥当性は調べず、最初の1文字だけを判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（値は設定済みだが先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` など |
| それ以外 | 無効。`0`, `true`, ` 1` など |

`emb_reuse_account()` の結果は関数内の `static const bool` にキャッシュされます。初回評価後にプロセス環境を変更しても再評価されません。実装にログ出力はありません。

## 有効になる条件

`src/prefill/prefill.cpp` を含む prompt prefill 実装（CUDA/HIP および SYCL port）で、`Prefill::bytes_needed()` または `Prefill::bytes_needed_owned()` を使う見積もり経路に入ったときに判定が使われます。通常の生成経路では、この見積もり値は prompt chunk の cache 枠の計算や利用可能メモリとの比較に使われます（例: `src/program/generate.cpp` の `lend_slots`、`part_slots`、および CUDA 空き容量との比較）。自動 chunk や借用枠がこの差分で変わらなければ、見える実行結果に差はありません。

実際の `Prefill::carve()` は `bo` に `emb` と同じポインターを割り当てます。環境変数が無効でも実割り当てで二重に領域を取るわけではなく、planner が従来互換のため `bo` 相当の `T * N` floats を余分に見積もります。有効時はその見積もりだけを省きます。よって、planner がより大きな chunk や追加の borrowed cache slots を選ぶことがあり、prompt の計算分割や丸めが変わり得ます。

## 実行時の詳細

`Prefill::bytes_needed_impl()` は `bo` の共有を除くバッファ群を順に `Alloc::take()` で数え、環境変数が無効なら追加で `f(T * N)` を数えます。ここで `T` は chunk token 数、`N` はモデル側の幅です。実割り当て側では embedding rows が hyper-connection broadcast 後に不要になるため、`Prefill::carve()` が `m.bo = m.emb` としています。

この変更は planner の必要量に限られ、プロンプト演算そのものを直接切り替える分岐ではありません。ただし見積もりが減ることで選択 chunk や借用 cache 枠が変わると、資料によれば prompt residual の丸めが変わり、既定値と bitwise 同一ではなくなることがあります。

## 文書との照合

`docs/DETAILS.md` は RTX 3060 の IQ3_XXS で、記載条件のもと chunk が 6400 から 6656 tokens、借用枠が 1652 から 1670 へ変わり、prompt が約 3.9%向上した例を記載しています。同資料は prompt residual が既定値と byte-identical ではなく、同資料内の実行では greedy output が一致したとしています。これは資料に記載された測定例であり、他の構成での性能や出力一致を保証するものではありません。

## 根拠

- `src/prefill/prefill.cpp:258-265`: `bo` と `emb` の共有に関する注記、環境変数の先頭文字判定と static cache。
- `src/prefill/prefill.cpp:1205-1223`: 実バッファの carving と `m.bo = m.emb`。
- `src/prefill/prefill.cpp:1819-1859`: 見積もり関数、および無効時だけ `T * N` を加算する箇所。
- `src/program/generate.cpp:6252-6253,6948-6950,7123-7128`: 見積もり値を cache 枠や空き容量の判断に使う例。
- `CMakeLists.txt:586`、`sycl/CMakeLists.txt:233-236`: CUDA/HIP と SYCL port の prefill target が `src/prefill/prefill.cpp` を含むこと。
- `docs/DETAILS.md:1941-1943`: 設計説明と、上記の測定例・出力差に関する説明。
