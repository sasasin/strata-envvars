# `CHAIN_GU`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の通常実行ファイルが読む環境変数ではありません。リポジトリ内で確認できる読み取り箇所は `metal/tests/token_chain.cpp` のみで、Metal の token-chain 計測プログラムにおける MoE gate/up (`GU`) dispatch の tile 設定を上書きします。このプログラムの冒頭コメントは、実モデルの GGUF を使った decode step の GPU 時間計測であり、activation は合成値なので数値検証ではないと説明しています。

## 値と判定

読み取り時に整数の既定値 `gl=32`, `gr=1`, `gs=4` を設定し、変数が設定されていれば `sscanf(e, "%d,%d,%d", &gl, &gr, &gs)` を呼びます。したがって `LANES,ROWS,SIMDGROUPS` の順で整数を読みます。文字列全体の消費や変換成功数を検査せず、無効値の警告・fallback 処理もありません。

| 入力例 | 結果 |
|---|---|
| 未設定、空文字、先頭が整数として読めない値 | 既定値のまま（または変換できた先行項目だけ変更） |
| `16,2,4` | `gl=16`, `gr=2`, `gs=4` |
| `16,2` | 先頭2項目だけ変更し、`gs=4` は既定値のまま |
| `16,2,4tail` | 3整数を読み、後続の `tail` は検査しない |

`%d` による符号付き整数変換で、値域・正数性・GPU tile としての妥当性は検査されません。部分的な `sscanf` 成功では書き換わった項目だけが残り、残りは初期値です。変換数が0でもエラー表示はありません。

## 有効になる条件

この設定は `metal/tests/token_chain.cpp` の計測経路で MoE dispatch を組み立てるときだけ使われます。Strata の製品実行経路でこの名前を読む箇所は、調査対象 HEAD のソース全体検索では見つかりませんでした。よって通常の `strata` 実行に `CHAIN_GU` を設定しても、この変数による変更は確認できません。

## 実行時の詳細

値は helper や static cache を介さず、その MoE dispatch 構築時に `getenv()` で読み取られます。読み取った `gl`, `gr`, `gs` から `a.gx_gu = NFF / (gs * (32 / gl) * gr)` を計算し、`MoeArgs` に入れて dispatch に渡します。コード上、ゼロ値による除算や負値、tile が GPU 実装の想定に合うかを事前に拒否する検査はありません。値が不正な場合の安全な実行結果は保証されていません。

この変数自体についてのログ出力はありません。

## 根拠

- `metal/tests/token_chain.cpp:1-8` — `token_chain` の用途と計測上の位置づけ。
- `metal/tests/token_chain.cpp:495-545` — MoE dispatch の既定 tile、`CHAIN_GU` の `getenv` / `sscanf`、`gx_gu` の計算。
- HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35` の Strata 所有ソースを `CHAIN_GU` で検索し、他の読み取り箇所がないことを確認。
