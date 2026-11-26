# `STRATA_COMPONENTS_DIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata Control とデスクトップ App Host が、エンジンや Control などのコンポーネントを置くルートディレクトリを選ぶ。値が空でなければ指定値をルートとして使い、未設定または空文字なら OS ごとのユーザーデータディレクトリから既定値を作る。ルートの選択後、エンジンは `<root>/engine`、更新状態は `<root>/.updates`、形状別エンジンは `<root>/shapes`、更新された Control は `<root>/control` 以下を参照する。App Host は同じルートに設定ファイルも配置する。`engine_component.components_dir()` と Host の `componentsDirectory()` によるパス選択で、GPU backend や build macro による値の解釈差はない。〔`terminal/strata_control/engine_component.py:179-193,205-220,252-259`; `terminal/strata_control/shape_engine.py:143-151`; `terminal/strata_control/discovery.py:47-59`; `app/host/server/control-runtime.mjs:26-31,88-99`〕

`tools/packaging/ENGINE-COMPONENT.md:18` のコンポーネント既定位置と、この値で場所を指定できるという説明は実装と一致する。`docs/release-notes-0.2.1.md:64` は engine bundle の移動として説明しているが、現行コードでは更新 Control、更新状態、形状別 engine、App Host の設定ファイルにも同じルートが使われる。〔`terminal/strata_control/engine_component.py:179-193,205-220,252-259`; `terminal/strata_control/discovery.py:52-59`; `app/host/server/control-runtime.mjs:88-99`〕

## 値と判定

Python Control と JavaScript Host はどちらも環境マップから名前を直接参照し、値が truthy（空でない文字列）ならディレクトリ値として採用する。整数・真偽値への変換、trim、存在確認、絶対パス化、正規化はこの選択関数では行わない。したがって空文字は未設定と同じだが、空白だけの文字列、`0`、`false` は空でないパスとして採用される。〔`terminal/strata_control/engine_component.py:179-189`; `terminal/strata_cli/handover.py:34-42`; `app/host/server/control-runtime.mjs:26-31`〕

| 条件 | 未設定・空文字 | 採用される値 | この変数としての無効値 |
|---|---|---|---|
| 全 OS（Control / App Host） | Windows では `%LOCALAPPDATA%\Strata\components`。`LOCALAPPDATA` が未設定または空なら `<home>/AppData/Local/Strata/components`。Windows 以外では `$XDG_DATA_HOME/strata/components`。`XDG_DATA_HOME` が未設定または空なら `<home>/.local/share/strata/components`。 | 空文字以外はそのままパス文字列として採用。例: `/srv/strata/components`、`C:\Strata`、`0`、`false`、空白のみ。 | parse による無効値判定はない。ディレクトリが存在するか、または書込み可能かは選択時に検証しない。 | 

既定値の決定では、Windows かどうかに加えて `LOCALAPPDATA` または `XDG_DATA_HOME` の値が使われる。これは `STRATA_COMPONENTS_DIR` より優先度が低い。〔`terminal/strata_control/engine_component.py:181-189`; `app/host/server/control-runtime.mjs:27-31`〕

## 有効になる条件

- Control の既定パス参照では、呼び出し側から明示的な root/path が渡されないこと。たとえば `strata components engine` は `--components-dir` がなければ `status()` を通してこの環境変数を使う。〔`terminal/strata_cli/cli.py:153-159,2087-2094`; `terminal/strata_control/engine_component.py:1340-1356`〕
- `strata update` など `--components-dir` を受け付けるコマンドでは、空でない CLI 引数が環境変数より優先される。明示引数がないと `default_components_dir()` が環境変数由来のパスを使う。値が設定されている場合は source checkout 内の `engine-feed` への特例切替も行わない。〔`terminal/strata_cli/update_cmd.py:47-55,269-284,318-324`〕
- Source checkout の `setup.py` にある `engine_from_feed()` は、更新子プロセス用に値を `<checkout>/engine-feed` へ設定し直す。その処理内では、親プロセスから継承した値を使わない。〔`terminal/setup.py:5366-5377`〕
- App Host は `componentsDirectory()` で値（または既定値）を選び、`controlEnvironment()` がその値を `STRATA_COMPONENTS_DIR` として Control 子プロセスの環境へ設定する。App Host の設定では親環境の値より、選択済みの `components` 引数が優先される。〔`app/host/server/control-runtime.mjs:26-31,88-99`〕
- CLI の Control handover と Terminal launcher の修復対象も同じ環境変数で決まる。ただし handover は既に更新処理を抑止する guard/off 変数がある場合や、checkout 自身の Control を使う場合などには実行されない。変数が指す場所に更新 Control の pointer がない場合は handover 先もない。〔`terminal/strata.py:37-51`; `terminal/strata_cli/handover.py:34-42,70-78,126-150`; `terminal/strata_cli/launcher_heal.py:24-27`〕

## 実行時の詳細

Python の `components_dir()` は、`environ` 引数がなければ呼び出し時点の `os.environ` を参照する。関数内 cache はなく、呼び出しのたびに環境を評価するため、プロセス内で環境値が変更され、その後に root を再取得すれば新しい値が使われる。既に `Path` として渡された root や、呼び出し元で選択済みの root は再評価されない。〔`terminal/strata_control/engine_component.py:179-189,1211-1215,1340-1344`; `terminal/strata_cli/handover.py:34-42`〕

値はファイルシステム上のルート選択に使われる。エンジン解決はそのルートをスキャンして実行可能な package を探し、status は同じルートから installed engine、pin/previous 状態、更新通知を組み立てる。形状別 engine と updater の state/cache も同じルート配下に置かれる。App Host は選択したルートを Control 子プロセスへ明示的に渡す。〔`terminal/strata_control/engine_component.py:1211-1217,1340-1364`; `terminal/strata_control/shape_engine.py:143-151,349-363`; `terminal/strata_control/feed_models.py:55-58`; `app/host/server/control-runtime.mjs:88-99`〕

CLI の `strata components engine` では、対象ルートに利用可能な engine がなければ `status()` が notice を返し、human 出力では notice を stderr に出して終了コード `5` を返す。JSON 出力でも `ok: false` と report を出して `5` を返す。ここで環境変数自体の構文エラーは発生せず、値が指す場所の内容に応じて missing/unusable の結果となる。〔`terminal/strata_control/engine_component.py:70-88,1211-1217,1340-1360`; `terminal/strata_cli/cli.py:2087-2109`〕

## ログと測定値

この変数の値を採用したこと自体を知らせるログは、パス選択コードにはない。エンジンが見つからない場合の利用者向け notice と終了コードは「実行時の詳細」を参照。性能測定値は該当しない。〔`terminal/strata_control/engine_component.py:179-189,1211-1217`; `terminal/strata_cli/cli.py:2087-2109`〕

## 根拠

- 値の選択、OS 別既定値、エンジン・更新状態のルート: `terminal/strata_control/engine_component.py:59-64,179-193,205-220,252-259,1209-1217,1340-1364`
- Control の handover、CLI の明示パス、update 先の選択: `terminal/strata_cli/handover.py:34-42,70-78,126-155`; `terminal/strata_cli/cli.py:153-159,2087-2109`; `terminal/strata_cli/update_cmd.py:47-55,269-284,318-324`
- App Host の環境読み取りと子プロセス環境への設定: `app/host/server/control-runtime.mjs:26-31,88-99`
- 形状別 engine と model feed cache: `terminal/strata_control/shape_engine.py:143-151,349-363`; `terminal/strata_control/feed_models.py:55-58`
- setup 子プロセスでの上書き: `terminal/setup.py:5366-5377`
