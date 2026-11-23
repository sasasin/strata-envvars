# `STRATA_VISION_TOWER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は現在、画像エンコーダーの tower を選びません。`terminal/tools/vision/strata_vision.cpp` の `main` が、旧設定値を検出したときに警告を stderr へ出す用途でのみ読みます。Strata の画像 reader はこの値にかかわらず own reader を実行します（`terminal/tools/vision/strata_vision.cpp:56-60, 140`）。

サーバー経由では `child_env()` が親環境をコピーし、run config の `env` を重ねて画像 reader の子プロセスへ渡します。config 側に同名キーがあれば親環境の値を上書きします。サーバーはこの変数の意味を解釈せず、GPU 用の環境調整もこのキーを変更しません（`terminal/serve/server.py:3870-3891, 3997-4012, 8906-8907, 3114-3121`）。

## 値と判定

`std::getenv` で値を取得し、未設定（null）か空文字列かを調べた後、`strcmp` で文字列全体を大文字小文字を区別して比較します。数値変換、trim、部分一致はありません（`terminal/tools/vision/strata_vision.cpp:59-60`）。

| 条件 | unset | 警告しない設定値 | 警告する設定値 |
|---|---|---|---|
| `strata-vision` 起動時（CPU / GPU ビルド共通） | 何もしない | 空文字、`own`、`auto` | それ以外の空でない値すべて。例: `mtmd`、`MTMD`、`0`、`1`、`true`、`false`、`0anything`、先頭・末尾に空白を含む値 |

有効な切替値はありません。`own` と `auto` も tower 選択を行わず、警告を抑制するだけです。空でない未知値や旧値もエラー扱いにはなりません。

## 有効になる条件

- `strata-vision` または同じ実装の backend 別実行ファイルが起動し、`main` を通るときに限り判定されます。読み取り箇所は backend 用の `#if` ブロック外にあります（`terminal/tools/vision/strata_vision.cpp:36-60`; 実行ファイル定義 `terminal/tools/vision/CMakeLists.txt:74-90`）。
- サーバーでは vision 設定があり、reader が実際に起動するときに警告が発生します。lazy 起動や elastic 起動では、reader の起動まで判定されません（`terminal/serve/server.py:8886-8907`; `terminal/serve/server.py:2963-2990`）。
- `--tower` は互換用に受理されますが、tower は選びません。`mtmd` は別の警告を出し、`own` / `auto` は何もせず通過します。これら以外は `--tower takes own or auto` と stderr に出して終了コード 2 で終了します。この CLI 引数と環境変数の優先順位はなく、サーバーは reader 起動引数に `--tower` を加えません（`terminal/tools/vision/strata_vision.cpp:61-74`; `terminal/serve/server.py:3017-3029`）。
- OS、backend、GPU、モデルの種類によってこの変数の判定規則は変わりません。GPU reader が起動できず CPU reader に切り替わる経路も、この変数の意味を変えません（`terminal/serve/server.py:2967-2975, 3042-3057`）。

## 実行時の詳細

reader プロセスの `main` 開始時に一度だけ取得し、そのプロセス内に cache しません。プロセス起動後の環境変更を再読する処理はありません。サーバーは `child_env()` 作成時に親環境を複製してから config の `env` を反映し、その環境辞書を reader の `Popen` に渡します。reader を再起動すると同じ保存済み環境辞書が渡され、各新プロセスが起動時に再び判定します（`terminal/serve/server.py:3873, 3890-3891, 2963-2966, 3114-3121`）。

値は reader の処理選択に使われません。引数処理後、`--mmproj` が指定されていれば同じ own reader の処理へ進みます（`terminal/tools/vision/strata_vision.cpp:61-74, 93-95, 140`）。

## ログと測定値

値が空でない `own` / `auto` 以外なら、stderr に次の行を出します。設定値は `%s` にそのまま入ります。

```text
strata-vision: STRATA_VISION_TOWER=<値> is no longer read; Strata's picture reader runs
```

これは警告であり、この分岐自体では終了しません。サーバー経由では stderr は設定されたログファイルへ接続され、ログ指定がなければ `DEVNULL` です（`terminal/tools/vision/strata_vision.cpp:59-60`; `terminal/serve/server.py:3118-3121`）。この変数による測定値はありません。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:36-60` — 起動時の読み取り、値比較、警告。
- `terminal/tools/vision/strata_vision.cpp:61-74, 93-95, 140` — `--tower` の互換処理、必要引数の検査、reader 実行。
- `terminal/tools/vision/CMakeLists.txt:74-90` — `strata-vision` 実行ファイルと HIP variant の定義。
- `terminal/serve/server.py:3870-3891, 3997-4012, 8886-8907, 2963-2990, 3017-3029, 3042-3057, 3114-3121` — 子環境の作成、server 起動条件、引数、再起動・fallback、stderr の接続。
