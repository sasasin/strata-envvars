# `QSA_STOP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`QSA_STOP` は通常の Strata 実行用設定ではなく、Metal の `qsa_prompt_parity` テストが `qsa_attn_mm` kernel の途中で止める位置を調べるためのテスト専用フックです。テストが環境変数を整数に変換して Metal function constant 8 に渡し、kernel は指定段階で return します。Strata の製品経路ではこの環境変数を読みません。

## 値と判定

| 環境値 | テストが渡す値 | `qsa_attn_mm` の動作 |
|---|---:|---|
| 未設定 | 0 | 通常経路を続行 |
| 空文字 | 0 | 通常経路を続行 |
| `1` | 1 | ID/scale のロード後、行列積の前に return |
| `2` | 2 | `Q × Kᵀ` の後に return |
| `3` | 3 | softmax の後に return |
| `4` | 4 | value 行列積の各 64 次元ブロックを旧形式で直接書き込み、そのブロック処理を続行 |
| その他の整数 | その整数 | 1〜4 の条件に一致しないため、通常の kernel 経路を続行 |

テスト側は `std::getenv("QSA_STOP")` が null のとき 0、設定されていれば `std::atoi` の結果を渡します。したがって未設定と空文字はいずれも 0 です。文字列全体の妥当性検査はなく、`atoi` が認識する先頭の整数部分が使われます（例: `2junk` は 2、整数として始まらない文字列は 0）。kernel 側で特別扱いするのは整数 1、2、3、4 だけです。範囲への clamp や無効値の警告はありません。

## 有効になる条件

- この環境値を読むのは `metal/tests/qsa_prompt_parity.cpp` の `qsa_prompt_parity` プログラムだけです。同テストは `qsa.metal` と `qsa_prompt.metal` をコンパイルし、`qsa_attn_mm` 用 pipeline の作成時に環境値を function constant 8 へ設定します。
- 製品側の Metal prompt 経路も `qsa_prompt.metal` をコンパイルし、`qsa_attn_mm` を使う場合があります。しかし pipeline 作成時に設定しているのは function constant 7 だけで、8 は指定しません。shader 内では constant 8 が未指定なら 0 を使うため、`QSA_STOP` が製品の処理を変える根拠はありません。
- function constant は pipeline 作成時に与えられます。テストでは `main` 内で一度読み取って pipeline を作るため、作成後に環境値を変えてもその pipeline には反映されません。

## 実行時の詳細

`qsa_prompt_parity` は `qsa_attn_mm` の pipeline を作る時点で `QSA_STOP` を読み、`mtl::Constants().i(8, ...)` として渡します。constant 8 は shader の `QSA_STOP` に対応し、未指定なら `qsa_stop` は 0 です。値 1〜3 では指定段階で各 threadgroup が return し、4 では value 積の各 64 次元区間を `tO` に直接 store して次の区間へ進みます。これらは parity 調査用の途中状態を作る分岐で、通常の attention 結果を生成する設定ではありません。

`QSA_STOP` 自体に対応するログ、警告、エラー出力はありません。テストは通常の比較を行い、相対 L2 と `PASS` / `FAIL` を stdout に出し、比較失敗数があれば終了コード 1、なければ 0 を返すコードです。途中停止時に比較がどうなるかは値やテスト条件によるため、特定の出力や終了結果は断定しません。

## 根拠

- `metal/tests/qsa_prompt_parity.cpp:23-29` は parity プログラムの入口と shader のコンパイル、`:41` は `QSA_STOP` の `getenv` / `atoi`、function constant 8 の設定です。
- `metal/src/mtl_rt.h:37-43` では `.i(index, value)` が整数型の function constant 値を登録します。
- `metal/kernels/qsa_prompt.metal:19-22` は constant 8 の宣言と未指定時の 0、`:44-50` は値 1 の停止、`:90-93` は値 2、`:94-107` は softmax と値 3、`:108-147` は value 積および値 4 の分岐を示します。
- 製品側の compile は `metal/src/engine/window.cpp:2497-2501`、prompt-chain での pipeline 作成は `metal/src/engine/prompt_chain.inc:286-299` にあります。ここでは function constant 7 のみ指定されています。別の window prompt 経路では `metal/src/engine/window.cpp:2726-2740` に `qsa_flash` または通常の `qsa_attn` の呼び出しがあり、`qsa_attn_mm` は呼び出していません。
