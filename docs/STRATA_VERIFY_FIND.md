# `STRATA_VERIFY_FIND`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査対象の Strata リポジトリは `main` で、作業ツリーに変更はありません。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `strata generate` の expert cache 検証で、GGUF と異なるデータが見つかったときに、そのデータがどの expert blob に含まれるかを追加検索します。検証そのものを有効にする変数ではありません。比較は別の `STRATA_VERIFY_ALL_SLOTS` が設定されている場合にだけ組み立てられ、この変数は不一致後の診断を追加します。

## 値と判定

`std::getenv("STRATA_VERIFY_FIND") != nullptr` という設定有無だけを判定します。文字列の内容は読みません。

| 値 | 判定 |
|---|---|
| 未設定 | 追加検索をしない |
| 空文字 | 設定済みとして追加検索する |
| `0`、`false`、その他の文字列 | 設定済みとして追加検索する |

数値変換、文字列全体の比較、大小文字の判定はありません。変数は不一致の処理中に都度読み取られ、値を static cache しません。

## 有効になる条件

この処理が到達可能なのは SYCL の `generate.cpp` にある、expert profile を使った GGUF からの pipelined fill の経路です。比較関数は `STRATA_VERIFY_ALL_SLOTS` が未設定でなく、profile が空でなく、source が存在し、per-layer admission でない場合に作られます。`STRATA_VERIFY_ALL_SLOTS` 自身も値ではなく設定有無で有効になります。

追加検索は slot と GGUF blob の比較で不一致が生じた場合にのみ走ります。さらに、その検証呼び出し内で数えた不一致が1件目または2件目までで、最初の差分位置 `fd` から4096 byte後に64 byteの probe を置ける（`fd + 4160 < nb`）場合に限られます。したがって設定しても、一致した場合や条件に合わない不一致では何も出力しません。

## 実行時の詳細

比較では各 filled slot の blob を GGUF から読み、cache の device slot を host buffer に読み戻して `memcmp` します。不一致時は、cache 側 blob の最初の差分位置から4096 byte後の64 byteを probe とし、fill 対象の expert blob を順に GGUF から読み直して `memmem` で検索します。読み出しに失敗した blob は飛ばします。probe が見つかった場合、stderr に expert の layer/expert 番号、slot、fill 順、blob 内 byte 位置を表示します。同じ probe を複数 blob が含めば、それぞれ出力されます。

`STRATA_VERIFY_ALL_SLOTS` により作られた検証処理は fill 直後（`after the fill`）と session 起動後（`session up`）に呼び出されます。この変数の値は各不一致時に参照されるため、検証中に環境を変更した場合でも後続の不一致では再評価されます。なお、環境変数の変更が他スレッドから安全に反映されるかは、このコードからは保証できません。

## 文書との照合

`docs/INTEL.md` は `STRATA_VERIFY_ALL_SLOTS` と並べて `STRATA_VERIFY_FIND=1` を、slot の誤データの出所を探すための診断として紹介しています（763行付近）。ソースでは `=1` に特別な意味はなく、空文字を含む設定済みの値すべてが同じ条件になります。また `STRATA_VERIFY_FIND` 単独では全slot比較を開始しません。

## 根拠

- `sycl/src/program/generate.cpp:4716-4727` — profile fill の範囲と検証関数の宣言。
- `sycl/src/program/generate.cpp:4791-4835` — `STRATA_VERIFY_ALL_SLOTS` の設定判定、slot の読み戻し比較、`STRATA_VERIFY_FIND` の条件と probe 検索、検証の初回呼び出し。
- `sycl/src/program/generate.cpp:5423-5425` — session 起動後の検証呼び出し。
- `docs/INTEL.md:762-767` — この診断を使った事例の説明。
