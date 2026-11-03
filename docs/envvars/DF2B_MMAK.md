# `DF2B_MMAK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `## main...origin/main`。

## 役割

Metal 同梱ベンチマーク `metal/tests/df2_bench.cpp` が、fragment-order Q4_0 行列積に使うカーネル名の接頭辞を選びます。既定は `df2_mma4`、`df2_mma4s` を指定すると split-K 版のカーネルを選びます。この変数の参照は同ベンチマーク内だけで、Strata の通常のモデル実行経路から読む箇所は確認できません。

## 値と判定

値は数値変換せず、環境変数から `std::string` にそのまま取り込みます。未設定だけが既定値に置き換わり、空文字を含む設定値は保持されます。大文字小文字を区別する文字列比較 `mmak == "df2_mma4s"` だけが split-K 判定です。

| `DF2B_MMAK` | カーネル名 | grid の計算 |
|---|---|---|
| 未設定 | `df2_mma4_<DF2B_MMAV>` | 通常版: 行タイル数を `R*S` で割って切り上げ |
| `df2_mma4s` と完全一致 | `df2_mma4s_<DF2B_MMAV>` | split-K 版: 行タイル数を `R` で割って切り上げ |
| 上記以外（空文字を含む） | `<値>_<DF2B_MMAV>` | 通常版の計算 |

`DF2B_MMAV` は同じファイルで別途読み込まれ、未設定時の既定値は `2_4` です。値の形式検証や `DF2B_MMAK` の fallback はありません。上記以外の値で生成される関数名がライブラリに存在しない場合、Metal ランタイムは `mtl: no function <関数名> ...` を stderr に出して終了コード 3 で終了します。関数が存在するかは値だけからは保証されません。

## 有効になる条件

- `metal/tests/df2_bench.cpp` のベンチマークを実行すること。Strata 本体の一般的な CLI / サーバー設定ではありません。
- この値によるカーネル選択と split-K の grid 分岐は `DF2B_KIND=frag` の経路で作られる fragment-order 行列に適用されます。`FRAG` は `DF2B_KIND` が文字列全体で `frag` と一致するときだけ真です。別の kind では `DF2B_MMAK` の値を読み込みますが、`m.frag` の分岐を通らず、この設定による行列積カーネル選択は行われません。
- Metal 実行環境と、選ばれた関数を含むコンパイル済みライブラリが必要です。GPU、OS、build macro、モデル状態による Strata 本体側の有効条件はありません。

## 実行時の詳細

ベンチマークの `main()` は Metal コンテキスト作成・`dflash2.metal` のコンパイル後に値を読み、ローカルの `mmak` と `splitk` に保持します。環境を再読するループや子プロセスへの転送はありません。fragment-order 行列積では `mmak + "_" + mmav` をパイプライン名として要求し、`splitk` に応じて dispatch grid の算出式を切り替えます。同じ選択を小さな CPU 照合用処理とベンチマークの行列積ディスパッチの両方で使います。

有効値や `df2_mma4s` の既定動作を示す専用ログはありません。CPU 照合経路では関数名を含む `... check: max |gpu - cpu| ... OK/FAIL` を stdout に出し、誤差条件に失敗すると終了コード 1 を返します。選択した関数名が見つからない場合、ランタイムは stderr に `mtl: no function ...` を出して終了コード 3 で終了します。カーネルの計算自体は Metal ソースの `df2_mma4` / `df2_mma4s` にありますが、ここでは外部 Metal 実装の内部動作を環境変数の効果として説明しません。

## 根拠

- `metal/tests/df2_bench.cpp:62-72`: 対象が Metal ベンチマークであること、Metal ライブラリをコンパイルすること、fragment kind の判定。
- `metal/tests/df2_bench.cpp:195-197`: `DF2B_MMAV` と `DF2B_MMAK` の読み取り、既定値、split-K 判定。
- `metal/tests/df2_bench.cpp:213-240`: fragment kind の CPU 照合で選択した関数名と pipeline を使い、失敗時に 1 を返す。
- `metal/tests/df2_bench.cpp:285-303`: fragment 行列積での pipeline 選択と `splitk` による grid 分岐。
- `metal/src/mtl_rt.mm:484-510`: pipeline 名で関数を検索し、見つからない場合の stderr 文言と終了コード 3。
- `metal/tests/df2_bench.cpp:1-9`: ベンチマークの目的と測定対象。ここに書かれた設計・測定説明を、この環境変数の実行結果として独自に検証したものではありません。
