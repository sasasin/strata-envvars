# `STRATA_DSV41_EXE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

DeepSeek-V4.1 用の別エンジン `strata-dsv41` の実行ファイルを、独自ビルドなど指定したパスから選びます。旧 `setup.py` の DeepSeek モデルセットアップと Terminal の `strata launch` の両方が参照します。通常の Strata エンジンや他のモデルの実行ファイル選択には使われません。

## 値と判定

両方の実装で `os.environ.get(..., "")` の結果を `.strip()` し、空でなければ `Path(value).is_file()` で確認します。値を `1` などの真偽値として parse するのではなく、パスとして扱います。

| 値 | 動作 |
|---|---|
| 未設定、空文字、空白だけ | override なし。通常のエンジン探索へ進む |
| 空白を除くパスが既存ファイル | そのファイルを独自エンジン候補として返す |
| 空白を除くパスがファイルでない | override の候補は見つからない。通常探索への fallback はしない |

パスの前後空白は除去されますが、`~` や環境変数の展開、絶対パス化、実行権限の検査はありません。相対パスは各 Python プロセスの作業ディレクトリから解決されます。`is_file()` はファイルの存在だけを判定するため、実行可能か、対応 OS 用か、エンジンとして正常起動するかまでは検証しません。

## 有効になる条件

- **旧 setup (`setup.py`)**: DeepSeek-V4.1 モデルのセットアップで `dsv41_exe(eng)` が呼ばれます。独自パスが有効ならそれを使い、`engine-dsv41/` 内のパッケージや `eng` の隣にある従来配置より優先します。インストール済みパッケージの自動 upgrade は、変数が空でない場合に抑止されます。
- **Terminal (`strata launch`)**: run config の `arch` が `deepseek41` の場合にだけ独自パスを探索します。有効なファイルが見つかると run config の `exe` をそのパスに差し替え、親ディレクトリをライブラリ探索先に追加します。`--dsv41-package` を使った場合と同様に、選んだエンジンの自動 upgrade は行いません。
- 変数が空でないのに指すファイルが存在しない場合、setup はその呼び出しではパッケージ配置を override として選べず、最終的に DeepSeek エンジンが見つからないエラーになります。Terminal 側の探索 helper も他のインストール場所を探索せず `None` を返します。ただし launch 前の config にある `exe` が既存ファイルなら、そのファイルは `dsv41_engine_missing()` の判定を通り、独自パスが適用されず元の `exe` のまま残る経路があります。

## 実行時の詳細

値は Python helper の呼び出しごとに読み取られ、static cache はありません。setup は独自パスが見つからなければ、条件に応じて engine package の取得を試みますが、環境変数が引き続き非空なら再度の `dsv41_exe()` も同じ override を優先するため、取得したパッケージへ切り替わらず後続の「engine is not available」エラーに至ります。Terminal は独自パスが有効な場合 `build_config()` で run config を書き換え、その `exe` が launch 対象になります。Terminal では config の元の `exe` が既存ファイルの場合、独自パスが無効でもその元のパスを保持しうるため、変数だけから最終的な起動先は決まりません。

環境変数を読んで失敗時に出す専用警告はありません。setup の verbose 時には、エンジンが見つからない場合に `STRATA_DSV41_EXE` を指定した独自ビルド手順を表示します。setup では選択したパスを `engine: <path>` と表示します。Terminal は選択したファイルが通常の起動処理で使えない場合の挙動をこの変数の helper 内では扱わず、実際の起動エラーに委ねます。

## 根拠

- `setup.py:7815-7829` — 空白除去、ファイル判定、独自パス優先、通常配置探索と従来配置への fallback。
- `setup.py:8040-8059` — DeepSeek セットアップでの選択、package 取得後の再判定、自動 upgrade 抑止、未検出時のエラーと verbose 案内。
- `strata_cli/launch/runner.py:1875-1894,1896-1915` — DeepSeek 用 run config の `exe` とライブラリ探索先の差し替え、および独自パス時の upgrade 抑止。
- `strata_cli/launch/runner.py:1864-1873` — config に記録済みの engine file が有効なら、それを missing と判定しない条件。
- `strata_cli/launch/runner.py:1917-1924` — Terminal 側の独自パス判定と、ファイルでなければ他のインストール場所に fallback しない分岐。
- `strata_cli/launch/runner.py:1235-1244` — run config 作成時に DeepSeek エンジン選択を反映する呼び出し。
