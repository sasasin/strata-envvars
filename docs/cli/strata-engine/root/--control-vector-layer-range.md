# `--control-vector-layer-range`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（CUDA/HIP 系および SYCL 版） |
| オプション | `--control-vector-layer-range` |
| 別名 | なし |
| 値 | 整数 `A B`。control vector を適用する層範囲の始点と終点（両端を含む） |

## 役割

control vector の適用層を指定する。範囲指定だけでは vector は読み込まれず、`--control-vector` または `--control-vector-scaled` で vector ファイルを指定したときに、ロード時の適用範囲として使われる。既定ではモデルの層番号 `1` から `n_layers - 1` までを対象にする。

## 使い方

```sh
strata generate --pack MODEL_DIR --tokens '1,2,3' \
  --control-vector-scaled vector.gguf:1.0 \
  --control-vector-layer-range 4 44
```

`MODEL_DIR` と `vector.gguf` は利用環境にある推論モデルと control vector のパスに置き換える。例は範囲指定を control vector の読み込みと組み合わせている。

## 値と既定値

- parser は `A` と `B` をそれぞれ `std::atoi` で整数へ変換する。明示的な整数形式・範囲検証はない。たとえば数値として解釈できない文字列は `atoi` により `0` となり、部分的に数字を含む文字列は先頭の数値部分だけが変換される。
- オプションを省略すると内部値は `-1, -1`。ロード時に始点 `A <= 0` は `1` に、終点 `B <= 0` または `B >= n_layers` は `n_layers - 1` に正規化される。
- したがって `0` や負数は個別にエラーにならず、その側の既定境界として扱われる。終点が層数以上でも最終層番号へ丸められる。一方、正の始点が層数以上の場合は上限へ丸められない。
- 同じオプションを複数回指定した場合、parser は同じ2フィールドを順に上書きするため最後の指定が残る。
- 2値の一方が省略されると、引数取得関数が `<option> needs a value` を標準エラーへ出して終了コード `2` で終了する。

## 実行時の動作

範囲は `load_control_vectors` が GGUF 内の方向ベクトルを読み込んだ後に適用される。ロード処理は各対象層について方向データを作り、`cvec_upload` に始点・終点を渡す。層ごとの適用判定は `Cvec::covers` が行い、読み込まれた方向があり、層番号が指定範囲内である場合に限って適用対象となる。

範囲の両端は inclusive。範囲外の層の方向がファイル内にあっても、その層には適用されない。始点が終点を超える、始点がモデルの層範囲外になる、または指定範囲に実際の方向ベクトルがない場合は対象層の走査結果が0件となり、vector 読み込みが失敗する。

このオプションだけを指定しても `load_control_vectors` は呼び出されず、適用は起きない。呼び出し側は `cvec_files` が空でない場合に限って vector をロードする。読み込みは推論セッション初期化前に行われ、デバイス側の vector table の更新・アップロードを伴う。`--serve` ではロード済み vector の有効・無効をリクエスト単位で切り替える経路があるが、この範囲オプションはロード時に決まり、リクエストごとの範囲変更ではない。

## 適用条件と副作用

- 層範囲の効果があるのは control vector ファイルも指定され、読み込みが成功した場合だけ。
- `--control-vector` / `--control-vector-scaled` と `--cvec-mode`、`--cvec-dir` は同じ vector 読み込み処理に関与する。範囲オプション自体は mode や direction の形式を変えない。
- 読み込みはデバイス table を更新し、既存 table を置き換える。vector がロードされると、範囲内かつ方向を持つ層の推論グラフ経路で control vector が適用される。
- CUDA/HIP 系 parser と SYCL parser で、値の変換・境界正規化・空範囲エラーの処理は同じ実装になっている。その他の backend 固有差はこの調査では確認していない。

## 出力とエラー

- vector の読み込み時には標準エラーに mode、direction の方式、正規化後の層範囲、適用層数を表示する。
- 範囲内に適用可能な方向がない場合、`the control vector has no direction in layers A..B` が読み込みエラーとなり、呼び出し側は `strata generate: control vector: ...` を標準エラーに表示して終了コード `2` を返す。
- 上限超過などの値自体を範囲エラーとして拒否する validation はない。前述の正規化後に層が1つも対象にならない場合に読み込みエラーとなる。

## 根拠

- `engine/src/program/generate.cpp:1202-1205` — option 値を保存する control vector 設定。既定値は `-1`。
- `engine/src/program/generate.cpp:1370-1374` — CLI usage に示される `A B` 形式と inclusive / default 表記。
- `engine/src/program/generate.cpp:3842-3847` — 引数取得時の値不足エラーと終了コード。
- `engine/src/program/generate.cpp:4180-4183` — parser が2値を `atoi` で受け取る箇所。
- `engine/src/program/generate.cpp:2786-2813` — 範囲の正規化、対象層走査、空範囲相当の失敗、およびデバイスへの table 引き渡し。
- `engine/src/program/generate.cpp:2825-2829` — 読み込み成功後の範囲・適用数の標準エラー出力。
- `engine/src/program/generate.cpp:6142-6150` — vector が指定された場合だけロードし、失敗時に標準エラーと終了コード `2` を返す呼び出し側。
- `engine/include/strata/kernels/cvec.hpp:25-36` — 範囲の inclusive 判定と、方向のある層だけを適用対象とする条件。
- `engine/src/core/layer.cpp:1638-1649` — 層の FFN 書き込み後に、対象層で control vector を適用する推論経路。
- `engine/src/kernels/cuda/cvec.cu:101-132` — CUDA/HIP 系 device table を更新し、範囲を登録する処理。
- `engine/sycl/src/program/generate.cpp:2144-2147, 1577-1604, 3266-3274` — SYCL 版 parser、同等の範囲処理、ロード呼び出しと失敗処理。
- `engine/sycl/src/kernels/cuda/cvec.dp.cpp:189-229` — SYCL device table を更新し、範囲を登録する処理。

## 調査範囲と制約

Strata checkout の commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6` のソースを確認した。調査開始時の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されなかった。既存バイナリの `--help` は実行せず、ソース内 usage と parser を照合した。
