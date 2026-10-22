# `STRATA_PYTHON`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata Terminal の起動スクリプトと App Host が Python を起動するときに、使用する Python 実行ファイルを明示します。設定値は実行ファイル名またはパスとして扱われ、Python の起動コマンドに引数を追加する形式ではありません。CUDA/HIP 等の engine の環境変数ではありません。

## 値と判定

| 読み取り箇所 | 未設定または空文字 | 非空文字列 | 検証 |
|---|---|---|---|
| POSIX Terminal launcher (`bin/strata`) | override を使わず、同梱 Python、続いて候補パス上の Python を探す | 値を実行ファイルパスとして最優先で使用 | `-x` による実行可能性のみ。Python の版は検査しない |
| Windows cmd launcher (`bin/strata.cmd`) | override を使わず、同梱 Python、checkout の `.venv`、`py -3`、`python` の順で探す | 値を実行ファイルパスとして最優先で使用 | `if exist` のみ。Python の版は検査しない |
| Windows PowerShell launcher (`bin/strata.ps1`) | override を使わず、同梱 Python、checkout の `.venv`、`py -3`、`python` の順で探す | 値を実行ファイルパスとして最優先で使用 | `Test-Path` のみ。Python の版は検査しない |
| App Host の `resolvePython()` | `STRATA_NATIVE_PYTHON`、同梱 Control Python、checkout の venv、PATH 上などの候補へ進む | 値を `command` として最優先で返す | ファイル存在・起動・Python の版を検査しない |

Terminal launcher では空文字は未指定と同じです（POSIX は `[ -n ... ]`、Windows は値の truthiness / `if defined` で分岐）。App Host でも空文字は JavaScript の `||` により `STRATA_NATIVE_PYTHON` へ進みます。値に空白が含まれても別引数には分割されず、指定された一つの実行ファイルとして扱われます。

override が設定されていない場合、Terminal launcher が PATH などから探す Python には 3.10 以上という条件を確認します。これは fallback 候補の検査であり、`STRATA_PYTHON` で指定した Python には適用されません。

## 有効になる条件

- Terminal では `bin/strata`、`bin/strata.cmd`、または `bin/strata.ps1` を通して起動した場合に参照されます。各 launcher は環境変数を最初に確認し、非空なら他の Python 候補より優先します。
- App Host では `apps/host/server/python-resolver.mjs` が Python 子プロセスの実行先を選ぶ際に参照します。値があれば `STRATA_NATIVE_PYTHON`、Control 同梱 Python、checkout の venv より優先します。
- `control-runtime.mjs` は packaged Control の環境を作る際に `STRATA_PYTHON` と `STRATA_NATIVE_PYTHON` を削除します。その Control 子プロセスにはこの指定は継承されません。
- POSIX で指定先が実行可能でない場合は launcher がエラーを出して終了コード 5 になります。Windows cmd は指定先が存在しない場合、PowerShell は `Test-Path` が偽の場合に診断を出して終了コード 5 になります。存在するが Python ではないファイルや、非対応版の Python を指定した場合、launcher はそのまま起動を試みます。
- override を指定しない fallback では、同梱 Python が選ばれた場合に限り、Windows cmd / PowerShell は `PYTHONNOUSERSITE=1` を設定し、`PYTHONHOME` と `PYTHONPATH` を消去します。POSIX launcher も同梱 Python のパスを選んだ場合に同様の環境調整をします。`STRATA_PYTHON` override にはこの調整を行いません。

## 実行時の詳細

Terminal launcher は起動のたびに環境を読み、選んだ Python で `strata.py` を実行します。POSIX 版では `serve` と `bench` のとき、その Python で必要パッケージを import できるか調べ、不足時は stderr に interpreter と `requirements.txt` を示して終了コード 5 で終わります。他のサブコマンドではこの事前確認をせず、そのまま CLI を起動します。Windows launcher は選んだ Python に `strata.py` と引数を渡し、終了コードを返します。

App Host の `index.mjs` は起動時に `resolvePython()` の結果を定数として保持し、tuning や revise 等の Python job に使います。native control は接続開始時に resolver を呼び、選択した Python で `tools/strata_mcp.py` を起動します。resolver の cache key には `STRATA_PYTHON` と `STRATA_NATIVE_PYTHON` の値が含まれますが、`index.mjs` が起動時に保持した値は環境変更だけでは再選択されません。

指定先の失敗は各実行経路で異なる形で観測されます。Terminal の存在・実行可能性チェックを通った後の起動失敗は Python 起動結果として返り、App Host の resolver は明示指定の起動可能性を事前確認しないため、子プロセスの spawn / 起動処理側で失敗します。

## 根拠

- POSIX launcher の優先順位、空文字判定、実行可能性検査、エラーと終了コード: `bin/strata:31-35,76-88`。fallback の版検査: `bin/strata:45-70`。serve / bench の依存確認と最終起動: `bin/strata:109-133`。
- Windows cmd の優先順位、指定値の存在検査、fallback の版検査、引数転送: `bin/strata.cmd:16-48`。
- Windows PowerShell の優先順位、指定値の存在検査、fallback の版検査と起動: `bin/strata.ps1:17-57`。
- App Host の選択規則、検証のない明示値、cache key: `apps/host/server/python-resolver.mjs:23-57`。起動時に解決し jobs に渡す箇所: `apps/host/server/index.mjs:732-746,872-879`。native control での resolver と MCP 子プロセス起動: `apps/host/server/native-control.mjs:82-92`。
- packaged Control の子環境から変数を除く処理: `apps/host/server/control-runtime.mjs:77-90`。
- `integrations/harness/tool_flow_e2e.py:66` にも同名の読み取りがありますが、これは統合テスト harness 専用です。未設定なら `sys.executable`、設定されていればその文字列を使う実装で、通常利用時の Terminal / App Host 動作の根拠にはしていません。
