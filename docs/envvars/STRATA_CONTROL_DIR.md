# `STRATA_CONTROL_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

App Host が Strata Control コンポーネントの候補ディレクトリを受け取るための環境変数。通常のアプリ起動では Tauri shell が resources 内の Control を見つけた場合にこの値を host 子プロセスへ設定する。host はこのディレクトリを候補の一つとして検証し、採用した Control の Python と `strata.py` を後続の Control コマンド実行に使う（`app/desktop/src-tauri/src/main.rs:257-275, 501-542`; `app/host/server/control-runtime.mjs:59-74, 141-146`）。

これは Control の場所を候補として伝える値であり、設定したパスを無条件に採用する指定ではない。host は隣接 Control とユーザーコンポーネント内の更新済み Control も調べ、完全なコンポーネントのうちバージョンが最も新しいものを選ぶ。同じバージョンなら候補順（この変数、host 隣接、更新済み）の先が残る（`app/host/server/control-runtime.mjs:52-74`）。

同梱 Python の `strata_control.doctor` も、古い Control コンポーネントを指す保存済みパスの再配置候補としてこの環境変数を参照する。そこではインストール済み active / newest 候補より後、checkout 内の `strata_control` より前に調べる（`terminal/strata_control/doctor.py:68-118`）。

## 値と判定

| 利用箇所 | unset / 空文字 | 設定時の扱い | 無効・不採用になる例 |
|---|---|---|---|
| App Host `findControl` | 候補を追加しない | JavaScript の truthy 判定後に `resolve()` で絶対パス化。そこに platform 別 Python、`strata.py`、`strata_control` がすべて存在する場合だけ候補にする | 空文字は候補外。存在しないパス、必須ファイルまたはディレクトリの欠落は候補外。相対パスも受け取り、host の作業ディレクトリ基準で解決する |
| `doctor._rebase_component_path` | 候補を追加しない | Python の `os.environ.get()` で取得し、truthy なら `Path` 化。`is_dir()` が真のとき候補に追加 | 空文字は候補外。ディレクトリでないパスは候補外。空白だけの文字列は truthy なのでパスとして検査される |

host 側は値の文字列比較、数値 parse、trim、大小文字変換をしない。`resolve()` がパスを解決するだけであり、候補として使えるかは各ファイルの存在確認で判定する。`BUNDLE.json` は任意で、読み取りや JSON parse に失敗しても候補自体は捨てず、バージョン比較キーは `0` 相当になる。キーはバージョン文字列を `.` で分け、各要素を `Number.parseInt(part, 10) || 0` として比較する（`app/host/server/control-runtime.mjs:46-49, 59-74`）。

host に候補が複数ある場合、環境変数のパスが存在しても必ず優先されるわけではない。設定値の候補が完全であっても、より新しい隣接または更新済み Control があればそちらを選ぶ。比較上同点なら候補順が優先される（`app/host/server/control-runtime.mjs:61-74`）。

## 有効になる条件

- **Desktop アプリ**: Tauri の `control_dir(res)` が resources/control 内の platform 別 Python と `strata.py` を見つけると、host 起動コマンドにそのディレクトリを `STRATA_CONTROL_DIR` として設定する。host 側はさらに `strata_control` の存在も要求する（`app/desktop/src-tauri/src/main.rs:257-275, 522-542`; `app/host/server/control-runtime.mjs:61-66`）。
- **Host 単体起動**: host の `process.env` に値があれば同じ検証・バージョン比較を行う。値が未設定、または候補が不完全で最終的に Control が見つからない場合、`CONTROL` は `null` となり、Host は `packaged` 経路でなく既存のソース checkout 用パスを使う（`app/host/server/index.mjs:142-144, 800-805`; `app/host/server/native-control.mjs:137-145`）。
- **Doctor のパス再配置**: 保存済みパスが `components/control/<version>/...` の形に一致し、元の対象が見つからない場合に限って `_rebase_component_path` が呼ばれる。active/newest の Control に対象がなければ、この環境変数のディレクトリを候補にする。候補中で最初に対象が存在する場所を返す（`terminal/strata_control/doctor.py:32-36, 68-118, 121-149`）。
- GPU backend、モデル状態、CLI 引数による `STRATA_CONTROL_DIR` 自体の切り替えは、確認した読み取り箇所にはない。

## 実行時の詳細

App Host は起動時に `findControl()` を呼び、その結果を `CONTROL` と `createControl` に保持する（`app/host/server/index.mjs:142-144`）。`findControl` は呼び出し時の `env.STRATA_CONTROL_DIR` を読み、候補配列を組み立てる。通常の Control 呼び出しでは保存された `control` オブジェクトの interpreter、CLI、作業ディレクトリを使い、子プロセス環境にも採用した Control の絶対パスを `STRATA_CONTROL_DIR` として設定する（`app/host/server/control-runtime.mjs:59-74, 88-107, 140-146`）。

起動後に環境を変更しても、すでに保持された `CONTROL` が自動で再探索されるわけではない。first-run Control 更新後の `switchControl()` は、実行中モデルや処理がなく、Control 呼び出し中でもない場合に `control.reload()` を行い、これは再度 `findControl({ env })` を呼ぶ。新しい候補が見つかり、現在のディレクトリと異なる場合だけ切り替わる（`app/host/server/control-runtime.mjs:241-263`; `app/host/server/native-control.mjs:770-786`）。

Doctor は `_rebase_component_path` が呼ばれるたびに `os.environ.get()` を評価するため、その処理時点の環境を参照する。候補は重複を除き、`base / rest`（rest が空なら base 自体）が存在する最初のパスを返す。`doctor.inspect` の結果は `components.inspect` の report に含まれる（`terminal/strata_control/doctor.py:68-118, 194-203`; `terminal/strata_control/management.py:487-490`）。

## ログと測定値

`findControl` が値を無視した、または候補が不完全だったことを直接示す警告・エラー出力は確認できない。Control が見つからない場合、host の `/api/control/status` は `control: null` を返す。Control が選ばれている場合は同 API の `control` に採用ディレクトリ、Python、version、bundle を載せる（`app/host/server/index.mjs:1418-1436`）。Control 切り替えが実際に行われたときは `now using Strata Control <version> (<dir>, was <before>)` を update log に記録するが、これは環境変数の値そのものを表示するログではない（`app/host/server/native-control.mjs:778-786`）。

Doctor の report は検査項目ごとに `status` と `path` を含むが、環境変数が採用された理由を個別に記録するものではない（`terminal/strata_control/doctor.py:194-203`）。測定値は該当しない。

## 根拠

- `app/host/server/control-runtime.mjs:46-74` — 候補値の有無、絶対パス化、完全性検査、バージョン比較と選択。
- `app/host/server/control-runtime.mjs:88-107, 140-146, 241-263` — 子プロセス環境への設定、CLI 起動、再探索。
- `app/host/server/index.mjs:142-144, 1418-1436` — 起動時の保持、状態 API。
- `app/host/server/native-control.mjs:137-145, 770-786` — Control の有無による実行経路、更新後の切り替え。
- `app/desktop/src-tauri/src/main.rs:257-275, 501-542` — bundled Control の判定と host 子プロセスへの設定。
- `terminal/strata_control/doctor.py:32-36, 68-118, 121-149, 194-203` — 旧 component path の再配置候補と report の path/status。
- `terminal/strata_control/management.py:487-490` — doctor inspection の呼び出し。
