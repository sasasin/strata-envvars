# `PYTHONSTARTUP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストは、Control 用の子プロセスに渡す環境から `PYTHONSTARTUP` を取り除く。これは値に応じた動作設定ではなく、ユーザーの Python 環境変数を Control が実行する Python に持ち込まないための環境整形である。Strata は値を読み取って解釈したり、起動ファイルのパスを開いたりしない。`controlEnvironment` がこの環境を作り、`runCli` などがその結果を子プロセスに渡す（`app/host/server/control-runtime.mjs:88-107,140-146`）。

## 値と判定

| Strata が作る環境 | 未設定 | 設定あり（例） | 判定 |
|---|---|---|---|
| `controlEnvironment` を通す Control 子プロセス | `PYTHONSTARTUP` は存在しない | 空文字、`1`、任意の文字列 | 値を検査せず、キーを削除する。空文字も含め、値は子プロセスに渡らない（`app/host/server/control-runtime.mjs:89-95`）。 |
| source checkout のモデルサーバー、および Control フィルターを通さない native 子プロセス | 元の環境を引き継ぐ | 元の値をそのまま引き継ぐ | この経路の Strata コードは `PYTHONSTARTUP` を個別に処理しない（`app/host/server/control-runtime.mjs:82-85`; `app/host/server/native-control.mjs:201-202,689-690,735-742`）。 |

Strata 側に文字列比較、数値変換、大小文字・空白の検査、値域、無効値時の fallback はない。Control 子プロセスでは未設定・空文字・その他の値が同じく削除対象になる。CLI 引数や別の設定値による上書きもない。`controlEnvironment` が他の Control 用変数を追加することはあるが、`PYTHONSTARTUP` を戻す処理はない（`app/host/server/control-runtime.mjs:89-107`）。

## 有効になる条件

- `controlEnvironment` を使って起動される子プロセスでだけ、削除が適用される。Control コンポーネントが見つかった場合、ホストは `packaged` として扱い、たとえば自動調整の Control 起動やインストーラー起動にこの環境整形を使う（`app/host/server/index.mjs:142-144`; `app/host/server/native-control.mjs:140-145,196-202`）。
- `runCli` は起動のたびに `controlEnvironment` の戻り値を `spawn` の `env` に渡す。更新・モデル一覧など同じ runner を通る Control CLI 起動もこの対象（`app/host/server/control-runtime.mjs:140-146,220`）。
- source checkout でモデルサーバーを直接起動する経路は `sourceServerEnvironment` を使うが、そこでは `STRATA_API_KEY` だけを削除する。native の installer や更新など Control を使わない経路も `process.env` をコピーしているため、この変数は Strata によって除去されない（`app/host/server/control-runtime.mjs:82-85`; `app/host/server/native-control.mjs:201-202,689-690,735-742`）。
- OS、GPU backend、build macro、モデル状態による `PYTHONSTARTUP` 自体の判定分岐はない。削除の有無は起動経路による。

## 実行時の詳細

`controlEnvironment` は呼び出しごとに入力環境をオブジェクトへコピーし、そのコピーから固定名の配列を順に `delete` する。したがって `PYTHONSTARTUP` の値をキャッシュせず、Control 子プロセスの起動時にその時点の入力環境から新しい環境を作る。明示的に別の `env` を渡さない場合は呼び出し時の `process.env` が入力になる（`app/host/server/control-runtime.mjs:89-107,141-146`）。

この処理自体はログを出さず、値による終了・警告・失敗経路もない。`runCli` には一般的な子プロセス起動失敗や timeout の処理があるが、コード上 `PYTHONSTARTUP` の有無・値とは結び付いていない（`app/host/server/control-runtime.mjs:140-157,170-179`）。Control フィルターを通らない経路で、子 Python が引き継がれた環境変数をどう扱うかは Strata の処理ではないため、ここでは説明しない。

## 根拠

- `app/host/server/control-runtime.mjs:88-107` — Control 子プロセス環境の作成と、キー配列による無条件削除。
- `app/host/server/control-runtime.mjs:140-146,152-179,220` — runner が作成済み環境を子プロセスへ渡し、起動・終了結果を扱う箇所。
- `app/host/server/index.mjs:142-144` — Control コンポーネントを使う packaged 経路の判定。
- `app/host/server/native-control.mjs:140-145,196-203` — Control の autotuner と installer 起動。
- `app/host/server/control-runtime.mjs:82-85`; `app/host/server/native-control.mjs:689-690,735-742` — source checkout のサーバー起動と、Control フィルターを通らない native 子プロセス起動。
