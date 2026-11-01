# `CHAIN_DN4`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`CHAIN_DN4` は Strata の通常の製品実行経路ではなく、Metal の `token_chain` テスト用プログラムにある調整値です。非 `Q2_0` 型の MoE down projection について、カーネルのタイル形状（1行あたりの lane 数、lane あたりの行数、simdgroup 数）を指定します。Q2_0 型の場合は代わりに `CHAIN_DN` が参照されます。

このテストプログラムの先頭コメントは、実モデルの GGUF 重みを使う一方、activation は合成値であり数値検証ではなく処理時間を測るものと説明しています。したがって、この変数を Strata の通常の推論設定として扱う根拠は確認できません（`metal/tests/token_chain.cpp:1-8`）。

## 値と判定

変数は `std::getenv()` で調べ、値が設定されている場合に `std::sscanf(e, "%d,%d,%d", &dl, &dr, &ds_)` で最大3個の整数を読みます。未設定なら初期値が残ります。`sscanf` の戻り値は確認せず、数値範囲や正負の検証、clamp、エラー出力もありません（`metal/tests/token_chain.cpp:540-545`）。

| 対象 tensor | 未設定時の値 `(dl, dr, ds_)` | 設定時 |
|---|---:|---|
| down tensor が `Q2_0` 以外 | `(4, 2, 4)` | `CHAIN_DN4` から読み取れた整数で、対応する先頭フィールドから上書き |
| down tensor が `Q2_0` | `(8, 1, 4)` | `CHAIN_DN` を同じ書式で読み取り。`CHAIN_DN4` は読まれない |

書式はカンマ区切りです。`%d` は符号付き10進整数を読み、各カンマは書式中のリテラルなので、カンマのない空文字や不正な先頭では変換数0となり初期値が保たれます。先頭の整数だけ、または先頭2整数だけ変換できた場合は、そのフィールドだけが更新され、残りは初期値です。3整数の後ろにある文字列は書式に含まれないため判定されません。値の全体一致や妥当性の検査はありません。

## 有効になる条件

- `metal/tests/token_chain.cpp` にあるテスト用プログラムを実行し、MoE dispatch の構築まで進む必要があります。
- `CHAIN_DN4` が選ばれるのは down tensor の型が `Q2_0` ではない場合です。Q2_0 では動的な名前選択により `CHAIN_DN` が使われます（`metal/tests/token_chain.cpp:540-545`）。
- このソースに `CHAIN_DN4` を上書きする CLI 引数はありません。タイル値を使って kernel 名、dispatch の threadgroup 幅とグリッド幅を計算します（`metal/tests/token_chain.cpp:579-603`）。
- この値はテストコード内で検査・検証されません。0 や負数も整数変換自体は受け付けられますが、後続の除算や dispatch 設定に渡されます。そうした値での実行結果や失敗の具体的な形は、このソースからは保証できません。

## 実行時の詳細

値の取得箇所は `token_chain` の各層の dispatch を組み立てるループ内です。実行時に各層ごとに `getenv` し、環境変数値をプロセス内の static 変数などへ cache してはいません。dispatch 構築後に `cx.run()` / `cx.run_graph()` が呼ばれるため、実行中の環境変更を dispatch に反映する処理はありません（`metal/tests/token_chain.cpp:396-400,540-545,644-652`）。

読み取った値は次の計算に使われます。

- `gx_dn = N / (ds_ * (32 / dl) * dr)` として grid 幅を算出します（`metal/tests/token_chain.cpp:545`）。
- down kernel の名前に `dl`, `dr`, `ds_` を含め、threadgroup 幅を `32 * ds_` とします（`metal/tests/token_chain.cpp:581-582,597-603`）。
- ソース内に、この環境変数自体を示すログ、警告、エラー文はありません。テストは後続で dispatch 数や測定時間などを stdout に出力しますが、その出力は `CHAIN_DN4` の値を報告しません（`metal/tests/token_chain.cpp:646-659`）。

## 根拠

候補索引 `docs/envvars/000_envvers.md` には `CHAIN_DN4` が載っています（同ファイルの候補一覧）。Strata ソース全体の完全一致検索で見つかった環境変数名の読み取りは `metal/tests/token_chain.cpp:544` のみです。同箇所は動的な名前 `dq2 ? "CHAIN_DN" : "CHAIN_DN4"` を `getenv` に渡しており、その選択元 `dq2` は down tensor が `Q2_0` かどうかです（`metal/tests/token_chain.cpp:541-544`）。他の参照は同テスト内の説明コメントです。製品コードでの読み取りや `docs/DETAILS.md` における説明は確認できませんでした。
