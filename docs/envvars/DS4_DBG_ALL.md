# `DS4_DBG_ALL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリ・GPU driver の環境変数は対象外。

## 役割

DeepSeek-V4.1 (DS4) の Metal 実装にある `DS4_DBG_H` 診断を、先頭2層だけでなく全層に広げます。`DS4_DBG_ALL` 単独ではこの診断を有効にしません。`DS4_DBG_H` も環境に設定されている必要があります。

この分岐は DS4 モデルの layer 処理中、`mi == 0` の group member に限って実行されます。条件を満たすと `d.h` を host view から読み、値のゼロ数・NaN 数・最大絶対値・先頭値などを `stderr` に出力します。これは状態の観測用ログで、変数自体がモデル計算を切り替える処理はありません。

## 値と判定

値の内容は parse されず、設定されているかだけを見ます。Metal では `ds4_dbg("DS4_DBG_ALL")` が `std::getenv(name) != nullptr` を返すため、`DS4_DBG_ALL` が空文字でも設定済みとして有効です。`1` など特定の値との比較、数値変換、範囲検査はありません。

| ビルド・設定 | 判定 | 結果 |
|---|---|---|
| Metal、unset | false | `DS4_DBG_H` が有効でも、通常どおり `il < 2` の層だけを対象にする |
| Metal、任意の値を設定（空文字を含む） | true | `DS4_DBG_H` が有効なら `mi == 0` の全層を対象にする |
| CUDA または HIP、設定の有無を問わない | false | helper がコンパイル時定数 false を返すため、この診断分岐は実行されない |

## 有効になる条件

- backend が `STRATA_METAL` でビルドされていること。`ds4_dbg` はこの macro の場合だけ環境を参照し、それ以外では常に false を返します。
- `DS4_DBG_H` が設定されていること。`DS4_DBG_ALL` はその内側の層範囲条件を `il < 2` から全層へ広げるだけです。
- 対象 layer の呼び出しで `mi == 0` であること。別の group member の呼び出しではログを出しません。
- DS4 の `layer()` 処理が実行されること。無効値時の fallback や CLI 引数による上書きはありません。

## 実行時の詳細

`ds4_dbg` は `static` 変数に結果を cache せず、呼び出しごとに環境を問い合わせます。`DS4_DBG_ALL` の参照は `DS4_DBG_H` が true で `mi == 0` の場合に限られるため、それ以外ではこの名前の問い合わせ自体が短絡評価で省かれます。プロセス実行中に環境が変更された場合、以後の評価には変更後の値が使われます（Strata 内で環境を変更する処理や別途転送する処理は、この変数について見つかりませんでした）。

診断が実行されると `d.h` の `T * H * D` 個の float を `strata::gpu::host_view(d.h)` 経由で参照して走査し、次の形式の1行を `stderr` に出します。

```text
DBG h: il=... dev=... h=... p0=... T=... p0tok=... zeros=... ninf=... max=... first=... ... nan_range=.....
```

実装上、`ninf` と表示される値は `h` 配列内で NaN と判定された要素数です（正負の無限大を数える処理ではありません）。診断分岐内に環境値を理由とする警告、エラー、終了処理はありません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal の `ds4_dbg` は `std::getenv(name) != nullptr`、非 Metal は定数 false。
- `src/dsv41/ds4_model.cu:9961-9967,9986-10005` — layer 処理、`DS4_DBG_H`・`mi == 0`・層範囲の条件、`d.h` の走査と `stderr` 出力。
- `setup.py:9007-9013` — この設定生成経路で engine backend を `metal` として記録。
