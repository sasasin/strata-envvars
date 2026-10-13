# `STRATA_DBG_DRAFT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

SYCL 版 `strata` の生成処理で、各 speculative verify window に drafter が用意した token ID 列と target model の出力列、および先頭からの受理数を stderr に表示する診断用フックです。生成結果を変える分岐ではなく、観測用の出力を追加します。通常利用者向けのサーバー設定として使われる実装は確認できませんでした。

## 値と判定

| 状態 | 挙動 |
|---|---|
| 未設定 | 診断行を出さない |
| 設定済み（空文字、`0`、その他の値を含む） | 診断行を出す |

判定は `std::getenv("STRATA_DBG_DRAFT") != nullptr` のみです。値を数値・文字列として parse せず、`1` との比較もありません。

## 有効になる条件

この参照は `sycl/src/program/generate.cpp` にある生成プログラム内だけで見つかりました。したがって、このソースを含む SYCL ビルドの生成処理が対象です。別 backend やサーバー経路で同じ変数を読む実装は確認できませんでした。

出力は生成ループの verify が正常終了した後に行われます。verify 自体が失敗してエラー経路へ戻る場合、この診断行には到達しません。ドラフトの供給元（MTP、suffix draft、lookup chain 等）をこの環境変数が選択することはありません。

## 実行時の詳細

各生成 window の検証結果を受け取った後、コードは `a` を `0` から始め、`window[a + 1]` と target 出力 `outv[a]` が一致する間だけ増加させてから、次の形式で stderr に出します。

```text
draftdbg: window <window 内 token ID...> | target <target token ID...> | accepted <a>
```

`window` は検証対象の入力列で、先頭は直前までに確定していた token、続く要素が提案 token です。`target` は同じ window に対する target 側の token ID 列です。`accepted` は提案列の先頭から target と一致した数で、必ずしも window 全体の長さではありません。コードはログ出力の前に `a` を算出し、出力後も同じ `a` を commit と生成結果の確定に使います。

環境変数は static cache されず、window ごとに `getenv` で読み直されます。Strata 内にこの変数を書き換える処理は見つかりませんでした。ログは `stderr` へ出し、token ID は十進整数です。

## 根拠

- `sycl/src/program/generate.cpp:12398-12404` — 受理数の算出、環境変数の存在判定、stderr の出力形式。
- `sycl/src/program/generate.cpp:12350-12357` — window に直前 token と提案列を格納する処理。
- `sycl/src/program/generate.cpp:12425-12429,12437-12442` — 診断後の commit と確定 token の処理。
- `sycl/CMakeLists.txt:241-243` — `sycl/src/program/generate.cpp` を SYCL の `strata` 実行ファイルに含める設定。
- `docs/DETAILS.md:97-105` — verify window と speculative draft が出力に関わる一般説明。`STRATA_DBG_DRAFT` 自体の説明や測定値はありません。
