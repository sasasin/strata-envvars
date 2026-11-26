# `HIP_PATH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata 本体の engine 設定値として解釈されるのではなく、Strata の Python サーバーが engine 用環境を組み立てる際に、存在しないパスを指す値を AMD (`backend: hip`) の子 engine に渡さないよう除去する。また Windows 向け engine package 作成では、未同梱 DLL を探す ROCm の候補ディレクトリをこの値から作る。どちらも値の真偽や場所を Strata が確認する処理であり、HIP runtime が値をどう使うかは本書の対象外である。`terminal/serve/server.py:4007-4062,4065-4095`、`tools/packaging/package_engine.py:239-249,252-271`。

## 値と判定

| 経路 | 未設定 | 設定時に有効になる値 | 無効・特別扱い |
|---|---|---|---|
| `strata serve` の子 engine、HIP backend | 親プロセス環境に無ければ `child_env` のコピーにも無い。 | 空でない文字列で、そのパスが `Path.exists()` を満たす場合は値をそのまま子 engine 環境に残す。 | 空文字は `if v` を通らず削除されないので、空文字のまま子へ渡る。空でないが存在しないパスは環境から削除される。文字列の trim、大小文字変換、パス正規化はしない。 |
| `strata serve` の子 engine、HIP 以外 | 親環境の値をそのままコピーする。 | 値の形式・存在をこの guard は検査しない。 | `hip_env_guard` 自体が呼ばれない。 |
| `tools/packaging/package_engine.py` の Windows package | `HIP_PATH` が無ければ ROCm の候補は追加されない。 | 空でない値 `root` から `root/bin/x64` と `root/bin` を候補化し、そのうちディレクトリであるものだけ検索対象に残す。 | 空文字は `if root` で無視。パス文字列の形式検証はなく、存在しない・ディレクトリでない候補は `is_dir()` で落ちる。 |

この変数について数値変換、真偽文字列 (`true` / `false`) の解析、数値境界はない。たとえば `0`、`false`、空白だけの値も一般のパス文字列として扱われ、サーバーではパスが存在するか、packager ではその配下がディレクトリかで決まる。サーバーでは `HIP_PATH=0` が存在しないパスなら除去され、実在する `HIP_PATH` なら残る。`server.py:4073-4077`、`package_engine.py:244-249`。

## 有効になる条件

- サーバー側の検査・除去は `cfg.get("backend") == "hip"` の場合だけ行われる。CUDA、SYCL、その他 backend では不正な値でも Strata はこの箇所で変更しない。`terminal/serve/server.py:4054-4062`。
- server 環境は親の `os.environ` のコピーから作られ、続いて `cfg["env"]` の項目が同名値を上書きする。その後 HIP guard が評価されるため、設定内の `HIP_PATH` も guard の対象となる。`terminal/serve/server.py:4010,4027-4028,4054-4055`。
- package 側の既定検索は `target.startswith("windows")` の場合だけ利用可能。明示的な `--search` 候補が1つ以上渡ると、その候補群が既定検索を置き換える。`--search` が空なら既定検索が使われる。`tools/packaging/package_engine.py:210,239-249,252-258,317-318,367-371`。
- packager は missing library があるときに検索する。`HIP_PATH` 由来の候補も `PATH` 由来の既存ディレクトリと合わせて探索されるため、`HIP_PATH` が未設定でも `PATH` 等に DLL があれば解決しうる。見つからない DLL が残れば package 作成を拒否する。`tools/packaging/package_engine.py:252-281`。

## 実行時の詳細

`child_env` は子 engine の起動環境を作るたびに `dict(os.environ)` を含む新しい辞書を作り、設定由来の `env` を反映してから HIP backend の guard を呼ぶ。存在しない `HIP_PATH` はその辞書から削除され、stderr に `strata serve: AMD: HIP_PATH=<値> does not exist: not passed to the engine` と出る。存在する値や空文字は変更されず、`StrataEngine` が `--serve` engine を `env=env` で起動するときに渡される。`terminal/serve/server.py:4007-4010,4027-4028,4054-4055,4073-4077,4093-4094, terminal/serve/server.py:833-835`。

この処理は `child_env` の呼び出しごとに評価され、`HIP_PATH` を保存する static cache はない。したがってサーバープロセスの環境または設定値が次の engine 起動前に変われば、その次の環境構築で再評価される。既に起動した子の環境は起動時に渡された値のままである。通常起動のほか、分割 fallback、replica、prefill/decode engine も `child_env` を経由している。`terminal/serve/server.py:8820-8824,8845-8852,8911-8919,9391-9394`。

package 作成時は `build` から `_bundle_missing_libraries` に渡った検索候補が空の場合、Windows target に限り `HIP_PATH` を読み、存在する `bin/x64`・`bin` ディレクトリを検索候補に加える。対象 DLL がそこに見つかれば staging にコピーし、依存 DLL が最後まで見つからない場合は `SystemExit` で `refusing to package: ...` と説明を出して終了する。ここでの読み取りは packager の呼び出し中に行われ、engine 実行時の設定ではない。`tools/packaging/package_engine.py:210,239-281`。

## ログと測定値

サーバーは HIP backend で空でない `HIP_PATH` が存在しないときだけ、stderr に `strata serve: AMD: HIP_PATH=<値> does not exist: not passed to the engine` を出す。存在する値・空文字・HIP 以外の backend では、この変数についての警告は出ない。packager は見つけた DLL を `bundled <DLL名> (imported by the engine; from <ディレクトリ>)` と出力し、依存関係を満たせないときは package 拒否のエラーを出す。`tools/packaging/package_engine.py:271-281`。測定値は該当しない。

## 根拠

- server 環境の継承・設定上書き・HIP backend 条件: `terminal/serve/server.py:4007-4062`
- `HIP_PATH` の存在判定、削除、警告文: `terminal/serve/server.py:4065-4095`
- 子 engine への環境引き渡し: `terminal/serve/server.py:833-835`
- Windows package の環境読み取りと検索先構成: `tools/packaging/package_engine.py:210,239-249,252-281,317-318,367-371`
