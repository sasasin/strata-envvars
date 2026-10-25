# `STRATA_METAL_GYRO_TILES`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Metal engine の `Window::gemv()` が、Gyro の dense weight 向けに使う専用 GEMV タイルを有効にするかを制御します。タイルを無効にすると、通常の形状・型ごとのタイル選択が使われます。これは macOS / Apple Silicon 向け Metal engine 内の設定で、CUDA・HIP・SYCL の経路にはこの変数の読み取りがありません。

## 値と判定

値を数値や真偽値として parse せず、環境変数の文字列全体を `"0"` と比較します。未設定または `"0"` 以外ならタイル設定は有効です。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| `0` | 無効 |
| 空文字、`00`、`false`、`1` など | 有効 |

判定結果は `Window::gemv()` 内の関数ローカル `static const bool` に保存されます。したがってプロセスで最初に `gemv()` が呼ばれた時点の値が使われ、以降に環境を書き換えても再評価されません。

## 有効になる条件

環境変数の判定が有効でも、専用タイルが使われるのは次の条件を満たす GEMV に限られます。

- `Window` のモデルファイルに `blk.0.ffn_gate_exps.weight` があり、その tensor type が `144` 以上である。この条件で `gyro_dense_` が true になります。
- GEMV の `ntok` が 2 以上である。
- tensor type と入力・出力幅が次のいずれかに一致する。

| tensor 条件 | 専用タイル `(L, Rr, S, K)` |
|---|---|
| Q5_K、`n_in == 2560`、`n_out >= 6144` | `(2, 1, 4, 1)` |
| Q5_K、`n_in == 6144` | `(2, 1, 4, 1)` |
| Q8_0、`n_in == 640` | `(4, 2, 4, 1)` |

いずれの条件にも該当しない場合は、この変数が有効でも専用タイルへの変更はありません。モデル名ではなく、先頭層 tensor の有無/type と各 GEMV tensor の型・形状で分岐します。

## 実行時の詳細

`gemv()` はまず一般の形状・型ルールから `(L, Rr, S, K)` を選びます。その後、Gyro dense 判定、`STRATA_METAL_GYRO_TILES`、`ntok`、対象 tensor の条件が揃う場合に上表の値へ変更し、その値から `gemv_<type>_<L>_<Rr>_<S>_<K>` という Metal pipeline 名を組み立てて dispatch します。専用タイルは lane sum の順序を変える旨が実装コメントにあります。

後続で `STRATA_METAL_GEMV_NR` も評価されます。`ntok > 1`、その値の parse 結果が `2`、かつ `n_out >= 2048` のとき、`S`、`K`、`Rr` をさらに変更する分岐があります。よって、最終的な dispatch 設定はこの変数だけでは決まりません。

実装にはこの変数専用のログ出力はありません。`docs/MAC.md` は M4 Mac mini 32 GB で Gyro-S の decode を測定し、dense-weight tiles を無効にした場合を 8.70 tok/s、既定設定を 9.14 tok/s と記録しています。同資料によると条件は SSD からの expert streaming、1 token/step、draft layer なしで、5 組の interleaved pair の中央値です。また全10回で同じ token が出たと記載されています。この測定値は同資料の条件に限られます。

## 根拠

- `metal/src/engine/window.cpp:648-688` — 通常タイルの選択、環境値の比較と static cache、Gyro 専用条件・タイル変更、後続 `STRATA_METAL_GEMV_NR` 分岐、pipeline dispatch。
- `metal/src/engine/window.cpp:341,477-490` — `gyro_dense_` の役割と、`blk.0.ffn_gate_exps.weight` の type による設定。
- `metal/CMakeLists.txt:1-3,49-53,90-123` — Metal engine が macOS 専用の独立 CMake project で、engine executable `strata` を構成すること。
- `docs/MAC.md:174-190` — Gyro の説明、測定条件、タイル無効時と既定時の測定結果。
