# `DS4_LAST_WINDOW`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

同梱 DeepSeek-V4.1 engine (`strata-dsv41`) の `--serve` モードで、各 prompt の最終 token を、その直前に checkpoint を作ってから別 feed として処理します。用途はソースコメントに A/B 比較と記されています。通常の `strata` engine 全般を制御する変数ではありません。

## 値と判定

値の内容は parse せず、`std::getenv("DS4_LAST_WINDOW") != nullptr` で設定の有無だけを判定します。

| 環境変数の状態 | `last_window` |
|---|---|
| 未設定 | `false` |
| 空文字を含む、何らかの値が設定済み | `true` |

従って `DS4_LAST_WINDOW=0` や `DS4_LAST_WINDOW=false` も有効です。値の数値変換、空文字の特別扱い、範囲判定はありません。

## 有効になる条件

- `strata-dsv41` が `--serve` モードで起動され、prompt の処理ループに入ること。
- その prompt の feed が末尾に達し、`fin` が true であること。

CMake では `strata-dsv41` のビルドは `STRATA_BUILD_DSV41` が ON の場合に限られ、既定は OFF です。したがって、この環境変数のコードは通常の `strata` executable ではなく、任意ビルドの DSV41 engine に属します。スコア計算、profile、speculative evaluation の処理にはこの serve ループを通らないため適用されません。

## 実行時の詳細

判定は serve 内の prompt 処理ループで行われ、関数内 `static const bool` に保存されます。最初の評価後にプロセス内で環境変数を変更しても再評価されません。

設定が有効で最終 feed の token 数 `n` が2以上なら、まず末尾以外の `n - 1` token を `Model::feed(..., logits_rows=0)` に渡し、成功後に checkpoint slot 1 を作り、最後の1 tokenを `Model::feed(..., logits_rows=1)` に渡します。`n` が1なら先行 feed は省略され、checkpoint の後にその token を処理します。未設定の場合は `Model::feed_mark(..., logits_rows=1, slot=1)` を呼びます。この関数は通常 feed 経路では同様に最後の token の直前に checkpoint を作りますが、条件を満たす chunked prompt 経路では `forward_chunks` に slot を渡す経路を使います。`DS4_LAST_WINDOW` を設定すると、この `feed_mark` の分岐を通らず、明示的に二つの feed に分けます。

この変数専用のログや診断出力は確認できません。prompt の成功・失敗は通常の feed 処理に従います。

## 根拠

- `src/dsv41/ds4_main.cpp:318-320, 763-799`: serve の prompt loop、判定、末尾 feed と checkpoint の分岐。
- `src/dsv41/ds4_model.cu:9356-9384`: `feed` と `feed_mark` の動作、および chunked path の条件。
- `CMakeLists.txt:797-811`: DSV41 engine が独立 executable `strata-dsv41` であり、`STRATA_BUILD_DSV41` の既定値が OFF であること。
- `docs/DETAILS.md`: `DS4_LAST_WINDOW` の説明や測定値は見つからなかった。
