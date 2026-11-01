# `DS4_MM_ABL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DeepSeek 4.1 の prompt 中に使う expert down-projection GEMM に、ablation 用の値を渡します。値 `1`〜`3` は MSL kernel の down 計算を変えます。`STRATA_METAL` 定義下で `ds4_iq.cu` が Metal 実装の `iq_set_dn()` を呼び、`mm_set(false, ...)` が処理する経路が対象です。Metal 版 DeepSeek 4.1 の実行経路以外では、この名前を読むコードは確認できませんでした。

## 値と判定

`mm_set()` の呼び出しごとに `std::getenv("DS4_MM_ABL")` を確認し、未設定なら `0`、設定されていれば `std::atoi()` の結果を `unsigned` に変換して kernel 引数 `pad0` に渡します。文字列全体の検証や値域チェックはありません。

| 環境変数の値 | `pad0` と down kernel の動作 |
|---|---|
| 未設定、空文字、数値として読めない文字列、先頭の数値が `0` | `0`。通常の down-projection 計算 |
| `1`（例: `1tail`） | `1`。重みタイルをゼロに置き換えて積を計算する |
| `2`（例: `2tail`） | `2`。down kernel が `w0` の K=0 ブロックを復号し、得た `w2` 側だけを使う（`w0` は当該タイルの先頭出力列を指す） |
| `3`（例: `3tail`） | `3`。down kernel はタイル処理の冒頭で戻り、出力を書かない。その後ホスト側のコピー処理自体は続く |
| その他の整数 | `1`〜`3` と一致しなければ通常の計算。たとえば `4` は通常計算 |

`atoi` のため、先頭空白と符号は整数変換で扱われ、数値の後ろに続く文字列は無視されます。負値は `unsigned` へ変換されます（`-1` は通常 `UINT_MAX` となり、`1`〜`3` の特別分岐には一致しません）。整数型の範囲外の文字列について、実装は独自の検査や fallback を設けていません。明示設定値の優先順位を変える CLI 引数や設定ファイルは見つかりませんでした。

## 有効になる条件

- Metal の `strata_ds4` ターゲットは `STRATA_METAL=1` で DeepSeek 4.1 のソースをコンパイルし、Metal 側 `ds4_finish.cpp` をリンクします。
- `ds4_iq.cu` の `set_down()` が `STRATA_METAL` 分岐に入り、`a.hbounds != nullptr` のとき `metal_host::iq_set_dn()` を試します。その呼び出しが成功すると、`DS4_MM_ABL` を引数に使う `mm_set(false, ...)` の経路が実行されます。
- `mm_set()` は、空の expert/row 数、未対応の量子化型や寸法、Metal 準備・バッファ確保などにより処理できないと `false` を返す経路があります。その場合、呼び出し元は通常の `set_down()` 側の処理へ進みます。この fallback では本環境変数が kernel 引数として使われません。
- `iq_set_gu()` も同じ `mm_set()` を呼びますが、MSL の gate/up kernel は `pad0` を参照しません。この変数が計算を変えるのは down kernel です。

## 実行時の詳細

設定値は `mm_set()` の引数構築まで進んだ呼び出しごとに読み直され、static cache には保存されません。プロセス中に環境が変更された場合、以降の該当呼び出しで新しい値が見える実装です。Strata はこの環境変数について CLI 優先順位、子プロセスへの転送、専用の警告やエラーを実装していません。

down kernel の `pad0 == 1` は重みベクトルをゼロにし、`pad0 == 2` は当該タイルの `w0`（先頭出力列）の K=0 ブロックを復号し、`w2` 側だけを通常とは異なる形で使います。`pad0 == 3` は kernel の出力書き込みを省略しますが、ホストコードはその後 `g_mm_ys` から結果先へコピーします。このため 3 は通常の down-projection 結果を生成する設定ではなく、後続処理には当該 kernel が書かなかった scratch の内容が渡ります。これらの値による結果変更、失敗、停止について Strata が個別にログを出す処理は確認できませんでした。`DS4_MM_DBG` のログは GEMM の引数寸法などを出しますが、`pad0` 自体は表示しません。

## 根拠

- 候補一覧に名前がある箇所: `docs/envvars/000_envvers.md:225`。
- 読み取り、`atoi`、既定値 0、引数構築、通常ログ: `metal/src/engine/ds4_finish.cpp:2460-2465,2476-2484,2505-2512`。
- down の scratch 結果のコピー、`iq_set_gu()` / `iq_set_dn()` からの呼び出し: `metal/src/engine/ds4_finish.cpp:2575-2596,2616-2634,2637-2643`。
- down kernel の `pad0` 分岐と出力書き込み: `metal/src/engine/msl/ds4_mm.metal:88-93,109-129`。
- `STRATA_METAL` 時の DeepSeek gate/up・down の Metal 呼び出しと false 時の後続経路: `src/dsv41/ds4_iq.cu:1585-1620`。
- Metal DeepSeek ターゲットが `ds4_finish.cpp` を組み込み、`STRATA_METAL=1` でビルドする設定: `metal/CMakeLists.txt:135-147,165-171`。
