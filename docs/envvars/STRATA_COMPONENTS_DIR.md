# `STRATA_COMPONENTS_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有の Control、CLI、デスクトップホスト、セットアップコードを対象とし、テストコードと外部ライブラリの動作は実装根拠から除外した。

## 役割

Strata の engine / Control などのコンポーネントを置くルートディレクトリを指定する。指定先の下に `engine/`、`control/`、`cloudflared/` などのサブディレクトリが使われる。主な利用経路は、Control が engine component を検索・起動・更新する処理、Terminal が更新済み Control へ hand-over する処理、デスクトップホストがコンポーネントの場所を決めて Control 子プロセスへ渡す処理である。

## 値と判定

Python の `engine_component.components_dir()` と `handover.components_dir()`、Node の `componentsDirectory()` は、値を文字列として parse せず、truthy / 非空かどうかで判定する。空白除去、パス検証、絶対パス化はこの判定箇所では行わない。

| 状態 | 使用されるルート |
|---|---|
| 未設定 | OS ごとの既定ルート |
| 空文字 | OS ごとの既定ルート（Python の `dict.get()` と JavaScript の truthy 判定で指定値扱いにならない） |
| 空でない文字列 | その文字列をパスとして使用。相対パスや空白を含む値もこの箇所では拒否しない |

既定ルートは次のとおり。

| OS | 環境変数 | 既定ルート |
|---|---|---|
| Windows | `LOCALAPPDATA` が非空ならその値、そうでなければユーザー home | `<LOCALAPPDATA または home>/Strata/components` |
| Windows 以外 | `XDG_DATA_HOME` が非空ならその値、そうでなければユーザー home | `<XDG_DATA_HOME または home>/.local/share/strata/components` |

Python では `Path(explicit)` を返し、Node では指定文字列を返すため、`STRATA_COMPONENTS_DIR` 自体に `engine` などのサブフォルダー名は付け足されない。下位コードが必要に応じて `engine/` 等を加える。

## 有効になる条件

- Control の `engine_component.components_dir()` を既定値として呼ぶ処理では、指定値が engine component の格納ルートになる。engine 検索はその下の `engine/` を走査し、run config の `component:strata-engine` 解決も同じルートを使う。CLI の `strata components engine` は `--components-dir` があればそれを環境変数より優先して渡す。
- `strata update` / `strata components update|rollback` は `--components-dir` が空でなければそれを使い、そうでなければ上記の環境変数解決を使う。
- デスクトップホストは `componentsDirectory()` でルートを決め、Control 子プロセスの環境にその値を `STRATA_COMPONENTS_DIR` として設定する。子プロセス起動時は、ホストが渡す値が継承元の値を上書きする。ホストは同じルートから更新済み Control、同梱 engine の配置先、cloudflared component の場所も構成する。
- Terminal の hand-over 判定も同じ環境変数から `control/active.json` を探す。ただし通常のソース checkout から起動した場合、hand-over は既定で行われない。通常のインストール経路で更新済み Control を探す場合にこのルートが使われる。
- CLI から明示的な `--components-dir` を指定する処理では、その CLI 引数が環境変数で選んだルートに優先する。すべての Strata データがこの環境変数で移動するわけではなく、モデル等の install 先は別設定（例: `STRATA_INSTALL_DIR`）である。

## 実行時の詳細

Python 側は `components_dir()` が呼ばれた時点の `os.environ`（引数 `environ` が渡された場合はその辞書）を参照する。読み取った値は `Path` に変換されて返るが、この関数内でディレクトリの作成や存在確認はしない。engine の `scan()` は `<root>/engine` を列挙し、存在しない場合は空の一覧を返す。`resolve()` は適合する engine を選び、見つからないときは `EngineMissing` とする。更新処理は同じ component root の下で engine / Control の更新状態を扱う。

Node 側は `process.env` を既定入力として関数呼び出し時に参照する。ホストの `controlEnvironment()` は元の環境を複製した後に `STRATA_COMPONENTS_DIR` を決定済みルートで上書きし、Control 起動時に渡す。ホストが呼び出し側から `components` 引数を受け取った場合は、その値が環境変数から計算した既定値より優先する。

Terminal の hand-over は選択ルートの `control/active.json` を読み、更新先 Control を探す。環境変数が空なら Windows は `%LOCALAPPDATA%\Strata\components` 相当、その他は `$XDG_DATA_HOME/strata/components` 相当を探す。hand-over の子プロセス環境は元の環境をコピーして構成されるため、`STRATA_COMPONENTS_DIR` は引き継がれる。

## 根拠

- `strata_control/engine_component.py:59,176-190`: 環境変数名、空でない値の採用、OS ごとの既定ルート、engine サブディレクトリ。
- `strata_control/engine_component.py:727-740,806-814,904-913,916-930`: engine 格納先の走査、起動用 component 解決、component status のルート使用。
- `strata_control/discovery.py:44-56`: Control の component directory helper を委譲し、app install/settings の既定場所もその親ディレクトリから構成。
- `strata_cli/cli.py:2001-2027`: `strata components engine` の `--components-dir` 引数を status 呼び出しへ渡し、結果に component folder を表示。
- `strata_cli/update_cmd.py:30-38,167-175`: 更新・rollback CLI の `--components-dir` と、引数がない場合の環境変数ベースの既定値。
- `strata_cli/handover.py:34-42,70-78,126-140,148-150`: hand-over 用の component root 選択、checkout 時の抑止、`control/active.json` 読み取り先、子プロセス環境。
- `apps/host/server/control-runtime.mjs:26-31,37-43`: Node ホスト側の値判定、既定ルート、更新済み Control の探索先。
- `apps/host/server/control-runtime.mjs:78-100,108-119`: Control / installer の子プロセス環境での設定と `STRATA_COMPONENTS_DIR` の上書き。
- `apps/host/server/index.mjs:125-128,179-180,918-919`: 同梱 engine の配置、host 管理オブジェクト、cloudflared component のルート利用。
- `strata_cli/launch/runner.py:416-426`: runner に component directory が設定されている場合、起動する子プロセスへ環境変数として渡す。
- `setup.py:4103-4112`: セットアップが独自の `engine-feed` staging root を設定して update 子プロセスを実行する例。これは環境変数より専用 staging root を明示する内部処理。
- `docs/INSTALL.md:56,324` および `packaging/ENGINE-COMPONENT.md:15-19`: component folder として既定場所または `STRATA_COMPONENTS_DIR` を案内。現行の分岐詳細は上記ソースに基づく。
