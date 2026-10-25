# `setup.py --data-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。

対象スコープは `source-setup` の `setup.py` と、それに引数を渡す setup/update wrapper です（[索引](../../README.md#source-setup)）。

## 概要

`--data-dir DIR` は、モデルファイル、準備済み pack などを置くデータフォルダーを指定します。引数は文字列として受け取り、既定値は parser 上 `None` です。指定がなければ、設定ファイルに記録済みの場所、または Strata の配置場所の隣にある `Strata-data` が使われます。`setup.py` の help は新規環境で約 70–120 GB と説明していますが、必要量はモデルや処理によって異なります。

```sh
./setup.sh --setup --data-dir "$HOME/Strata-data"
```

`--data-dir` の指定だけでは既存モデルを移動しません。移動する場合は `--move-data`、移動せず新しい場所を既定フォルダーとして記憶する場合は `--set-default-data-dir` を併用します。これらは別 option であり、この文書では `--data-dir` との相互作用に限って説明します。

## 値と検証

- Parser は `ap.add_argument("--data-dir", help=...)` として定義し、`type`、`choices`、`required`、明示的な `default` を付けません。したがって値は文字列で、指定なしの値は `None` です（`setup.py:8481–8482`）。値を省略すると argparse が引数エラーにします。
- 実処理では指定値に `expanduser()` と `resolve()` を適用して保存先を決めます（`setup.py:6051–6055`）。`~` を含む入力はホームディレクトリーへ展開されます。
- `strata_control.folders.problem()` が保存先を検査します。空でない指定は絶対パスである必要があり、Windows の不正文字、システムフォルダー（実行ユーザー自身のホームを除く）、ファイルをフォルダーとして使う指定、書き込み不能な既存フォルダー、存在しない親や書き込み不能な親を拒否します（`strata_control/folders.py:63–100`）。
- 検査時、存在するフォルダーまたは最も近い既存の親へ小さな一時ファイルを作成して削除し、書き込み可能かを確認します（`strata_control/folders.py:49–60, 82–99`）。通常は一時ファイルを残しませんが、削除に失敗した場合は残る可能性があります。
- 指定した保存先が検証に失敗すると `fail()` が理由と案内を表示し、「ダウンロードも変更も行わず、保存先として記録しない」と伝えて終了します（`setup.py:6054–6057, 825–830`）。検証後の作成時に `mkdir` が失敗した場合は警告を表示して `home()` を代わりに使います（`setup.py:6062–6066`）。

## 動作と適用条件

通常の setup/update 処理は `data_folder_for(a)` を通じて指定値を `data_folder()` に渡します（`setup.py:6136–6139`）。同関数は指定値があればそれを保存先に選び、なければ保存済み `data_dir`、さらに未設定なら `home().parent / "Strata-data"` を選びます（`setup.py:6051–6053`）。選択フォルダーは必要に応じて作成されます（`setup.py:6062–6066`）。

選んだフォルダーはモデルデータのルートとなり、既定の GGUF 配置場所はその下の `models` です（`setup.py:8609–8612`）。モデル準備時の pack 保存にも使われます（例: `setup.py:7660–7665, 8081–8084`）。`--models-dir` が別途指定されている場合、GGUF 配置はそちらになりますが、データルート自体は tokenizer や pack 等に引き続き使われます。

`--data-dir` の有無は起動経路も変えます。既存モデルを引数なしで起動する場合は `data_folder_in_place()` が設定を読むだけで、作成・移動・コピー・設定保存をしません。一方、`--data-dir` を指定するとこの単純起動判定から外れ、通常の setup 処理を通ります（`setup.py:8602–8612, 6142–6151`）。`--update` の経路は `update_install()` へ進み、その処理中も指定フォルダーがデータルートになります（`setup.py:8617–8619`）。

## 既存ファイル、保存、相互作用

- 指定先が現在記憶されているフォルダーと異なる場合、Strata は既存モデルを持つ候補フォルダーを調べます。別ドライブにあるモデルは移動せず、既存場所を使い続けます（`setup.py:6067–6081, 6105–6109`）。
- 同一ドライブに移動可能なモデルがあり、`--move-data` がなく `--yes` もない場合は、対話で keep/move を尋ねます。`--yes` のときは既定の keep が選ばれます。keep では既存モデルを残し、新しいダウンロードだけを指定先に置きます（`setup.py:6081–6096`; `ask()` の yes 時は既定値を返す: `setup.py:851–865`）。
- `--move-data` を併用すると既存モデルを新しい場所へ移す選択になります。モデルファイルはファイル単位で移動し、packs や MTP は移動先に同名物がない場合に移し、設定ファイル内のモデルパスも更新します。移動後にデータが残る場合は「使用中または移動先に同じデータがある」と警告します（`setup.py:6081–6096, 6110–6129`）。移動先と異なるドライブのデータは移動対象ではありません。
- `--set-default-data-dir` は keep の場合でも選択先を `settings.json` の `data_dir` として記録します。通常の移動経路でも処理完了時に `data_dir` と Strata install の一覧を保存します（`setup.py:6091–6096, 6130–6133`）。新しい場所にモデルが一つも見つからない場合は移動扱いとして記録されます（`setup.py:6097–6098`）。
- 記録済みの場所を指定なしで使う場合、その場所が後日利用不能なら既定の `Strata-data` に戻し、無効な `data_dir` 設定を除いて警告します（`setup.py:6058–6061, 6146–6151`）。

## 出力・失敗経路と wrapper

選んだ場所や既存モデルの場所を標準出力に説明し、保存先を設定へ記録します。指定値の検証失敗はセットアップを停止します。保存先の作成時に発生する `OSError` は警告して Strata 配置場所 (`home()`) にフォールバックします（`setup.py:6054–6066`）。ファイル移動時の個別失敗表示や、全 OS での権限・ドライブ挙動の詳細まではこのソース範囲から一般化できません。

`setup.sh` は `setup.py "$@"`、`START-HERE.bat` は `setup.py %*` を起動します。更新 wrapper も `setup.py` に委譲します（`setup.sh:9–13, 76`; `START-HERE.bat:44–55`; `update.sh:62`; `UPDATE.bat:79`）。したがって wrapper 独自の `--data-dir` 解釈はありません。

macOS の通常 setup は `setup.py` から `metal/setup_mac.py` へ委譲します（`setup.py:8418–8419`）。Metal 側にも同名引数と `--move-data` / `--set-default-data-dir` があり、共通の `data_folder_for()` を呼びます（`metal/setup_mac.py:339–342, 365–367`）。macOS Control mode は `setup.py` の別分岐です（`setup.py:8561–8562, 8251–8254`）。

## 根拠

- `setup.py:8481–8487` — parser 定義と関連 option の説明。
- `setup.py:6042–6151` — 保存先選択、検査、既存データの扱い、記録、読み取り専用の単純起動。
- `setup.py:8602–8612, 8617–8619` — `--data-dir` が起動/setup/update 分岐に与える影響。
- `strata_control/folders.py:49–104` — 保存先の書き込み検査とエラー文言。
- `setup.sh:9–13, 76`; `START-HERE.bat:44–55`; `update.sh:62`; `UPDATE.bat:79` — wrapper からの引数委譲。
- `metal/setup_mac.py:339–342, 365–367`; `setup.py:8418–8419, 8561–8562` — macOS の parser / 委譲経路。

調査は指定 revision の `setup.py`、関連 helper、wrapper のソースを対象としました。CLI help は実行していません。setup/update はネットワーク取得やモデル配置などの副作用を持ち得るため、ソース parser と使用箇所を根拠にしています。
