# `STRATA_VISION_TOWER`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`strata-vision` が画像をエンコードする reader を選びます。`own` は Strata の vision tower、`mtmd` は llama.cpp の mtmd reader、`auto` は Strata reader を使える条件なら `own`、そうでなければ `mtmd` です。変数自体が変えるのは reader の選択で、通常の画像処理では選ばれた reader が画像 embedding を生成します。サーバーでは vision 設定を持つモデルの reader 子プロセスに適用されます（`tools/vision/strata_vision.cpp:89-100,137-143`; `serve/server.py:10191-10209,3341-3348`）。

## 値と判定

`main()` は引数解析の前に `std::getenv` で一度読み、`vision_tower_default` が文字列全体を大文字小文字を区別して比較します。前後の空白除去や別形式からの変換はありません。未設定と空文字はどちらも `auto` で、警告は出ません。`mtmd`、`own`、`auto` 以外の非空文字列は警告して `auto` になります（`tools/vision/strata_vision.cpp:94-100`; `tools/vision/own/own_reader.cpp:37-42`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata-vision` の全 build | `auto` | `mtmd` は mtmd reader を指定、`own` は Strata reader を指定、`auto` は利用可能性に応じて選択 | 空文字は unset と同じ。`MTMD`、` own`、`auto `、任意の別文字列などは `auto` に戻る。非空なら警告 |

環境値を決めた後に `--tower` が処理され、指定があれば環境値を上書きします。CLI が受理するのは完全一致の `mtmd`、`own`、`auto` で、それ以外は `--tower takes mtmd, own or auto` を stderr に出して終了コード 2 です（`tools/vision/strata_vision.cpp:101-113`）。

## 有効になる条件

- `strata-vision` が起動する経路で読み取られます。サーバーではモデル設定に `vision` があると `Vision` を作り、その設定から reader を起動します。`child_env` は親環境を基礎に設定の `env` を上書きし、vision reader にもその環境を渡します。設定にこの名前がなければ親プロセスから継承した値が残ります（`serve/server.py:4428-4441,10191-10209,3341-3348`）。
- `mtmd` は reader 選択を直接指定し、`own_reader_supported` の可否判定を通しません。`own` も明示指定を保持し、可否判定で `mtmd` に差し替えません（`tools/vision/strata_vision.cpp:139-143`; `tools/vision/own/own_reader.cpp:84-87`）。
- `auto` で Strata reader を選ぶには mmproj が指定され、ファイルを開いて vision geometry を読み取れ、対応 geometry である必要があります。GPU 指定時は加えて build に `STRATA_VIT_GPU` があり、GPU が利用可能で、`prefer_mtmd` に該当せず、GPU geometry が対応し head dimension が 96 以下であることが必要です。条件を満たさなければ `mtmd` になります（`tools/vision/strata_vision.cpp:139-143`; `tools/vision/own/own_reader.cpp:49-72`）。
- `auto` が `own` を選んだ後、reader の起動前に失敗した場合、text model が指定されていると mtmd に切り替わります。`own` を環境値または `--tower own` で明示した場合はこの auto 起因の切替条件にならず、失敗は `ERR` として返ります（`tools/vision/strata_vision.cpp:141-143,161-175`; `tools/vision/own/own_reader.cpp:89-110`）。
- サーバー設定が環境値を渡す場合、同名の設定 `env` はサーバーの継承環境より優先します。reader を直接起動する場合は起動元の環境が使われます。別の環境変数は tower の値選択には使われません。`STRATA_VIT_GPU` は build 条件、GPU/モデル情報は `auto` の可否に関わります（`serve/server.py:4431,4440-4441`; `tools/vision/own/own_reader.cpp:49-72`）。

## 実行時の詳細

環境変数は `strata-vision` プロセス起動後の `main()` で一度読みます。実行中に環境を変えても、そのプロセスの tower 選択は変わりません。サーバーは subprocess 起動時に環境辞書を渡し、reader の再起動でも保存した spawn 設定を使います（`tools/vision/strata_vision.cpp:72,94-100`; `serve/server.py:3195-3205,3341-3348`）。

`auto` が選ばれると、mmproj と `--gpu`、`--max-tokens` の状態を使って `own_reader_supported` を呼び、可能なら `own`、そうでなければ `mtmd` に解決します。解決時に理由がある場合、`strata-vision: llama.cpp's reader (<理由>)` を stderr に出します。auto が `own` を選んだ場合に限り、text model が指定されていれば起動前失敗の理由を stderr に出して mtmd で起動し直します。明示的な `own` は同じ fallback を行いません（`tools/vision/strata_vision.cpp:137-175`; `tools/vision/own/own_reader.cpp:84-110`）。

## ログと測定値

- 未設定・空文字では tower 選択に関する警告はありません。無効な非空値では stderr に `strata-vision: STRATA_VISION_TOWER=<値> is not mtmd, own or auto; using auto` が出ます（`tools/vision/strata_vision.cpp:98-100`; `tools/vision/own/own_reader.cpp:37-42`）。
- `auto` が `mtmd` に解決され、理由文字列があると stderr に `strata-vision: llama.cpp's reader (<理由>)` が出ます。`auto` で選んだ Strata reader が起動前に失敗し、mtmd に切り替わると `strata-vision: Strata's picture reader did not start (<理由>); reading pictures with llama.cpp's reader` が stderr に出ます（`tools/vision/strata_vision.cpp:141-143,168-175`）。
- reader は起動時に stdout へ `READY <幅> own` または `READY <幅> mtmd` を返します。auto fallback の mtmd は `READY <幅> mtmd fallback` です。サーバーは `READY` 行を読み、fallback 表示があれば `[strata] Strata's picture reader did not start; pictures are read with llama.cpp's reader. Details are in the log.` を出します（`tools/vision/own/own_reader.cpp:168-169`; `tools/vision/strata_vision.cpp:319-321`; `serve/server.py:3372-3377`）。
- 選択した reader を起動できない場合、Strata reader は `ERR <理由>` を stdout に返す経路があります。サーバーは `READY` 以外の応答を reader 起動エラーとして扱います（`tools/vision/own/own_reader.cpp:92-110`; `serve/server.py:3357-3370`）。

## 根拠

- `tools/vision/strata_vision.cpp:94-113` — 環境値の初期選択、CLI `--tower` の上書きと無効引数。
- `tools/vision/strata_vision.cpp:137-175` — `auto` 解決、明示選択、起動前 fallback とログ。
- `tools/vision/own/own_reader.cpp:37-42,49-87,89-110,168-169` — 値判定、Strata reader の可否、失敗と起動応答。
- `serve/server.py:4428-4441,10191-10209,3195-3205,3341-3348,3372-3377` — server 設定から子プロセスへの環境引き渡しと起動応答の処理。
