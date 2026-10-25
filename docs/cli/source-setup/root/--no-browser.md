# `--no-browser`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` および委譲する更新 wrapper） |
| オプション | `--no-browser` |
| 別名 | なし。同じ設定先を変更する反対指定は `--browser` |
| 値 | 値を取らないフラグ。既定は未指定（`None`） |

## 役割

モデルの起動準備完了時にチャット画面を自動でブラウザーに開かないようにします。API クライアントや harness から使う場合などに利用できます。設定はモデルごとの run config に保存され、生成される `run-<model>.sh` / `.bat` にも反映されます（`setup.py:8476-8480`、`setup.py:7260-7269`）。

## 使い方

Linux で既定の setup / 起動経路を使う例:

```sh
./setup.sh --no-browser
```

Windows では `START-HERE.bat --no-browser` と指定できます。これらの wrapper は引数を `setup.py` に渡します（`setup.sh:6-13,75-76`、`START-HERE.bat:8-10,44-54`）。更新用 wrapper も同じ引数を委譲します（`update.sh:62`、`UPDATE.bat:79`）。

## 値と既定値

値は不要で、型変換や値域検証はありません。parser は `dest="browser"`、`action="store_false"`、`default=None` として登録しています。したがって通常は未指定の `None` で、明示すると `False` になります（`setup.py:8476-8480`）。同じ parser の `--browser` は同じ `browser` 値を `True` にするため、両方を指定した場合はコマンドライン上で後に現れた方が有効です。

無関係な引数を付ける形式（例: `--no-browser yes`）はこのフラグの値としては受理されず、余分な位置引数として argparse のエラーになります。`--no-browser` と `--browser` の指定順を含む使用例以外に、別の値・境界値はありません。

## 実行時の動作

- 既存モデルを通常起動するとき、`main()` は `a.browser` を `start(..., keep={"open_browser": a.browser})` に渡します。明示指定が未指定 (`None`) 以外なら `start()` が既存 config の値と比較して `open_browser` を更新・保存します。`--no-browser` は `False` を保存し、設定が変わった場合は「no browser」と表示します（`setup.py:6766-6771,8677-8691`）。
- 新しい設定を生成する経路（通常の setup、native / DeepSeek / Mac の設定生成）では、`a.browser is not None` のときだけ `cfg["open_browser"]` に値を設定します。生成する run script は `open_browser` が `False` の場合に server の `--open` 引数を付けません（`setup.py:7685-7690,7717-7718,8140-8148,8388-8405,7260-7269`）。
- `setup.py --no-start` で設定だけ作る場合も、run config と run script に値を保存しますが、その場でモデルを起動しません（通常設定の保存と `--no-start` 分岐: `setup.py:9729-9730,9759-9760`）。
- オプションを省略した場合、既存モデルの通常起動では保存済み設定をそのまま使います。新規設定ではキーがなければブラウザーを開く側が既定です。setup の再実行では `open_browser` は setup が再生成するキー集合 `SETUP_KEYS` に含まれず、ユーザー設定として carry over の対象です（`setup.py:6162-6167,6312-6342`）。`--browser` を明示すれば `True` に戻せます。

実際の起動では setup が server 起動引数に `--open` を加えるかを決め、server は `--open` があり、かつ config の `open_browser` が `False` でない場合にのみ `webbrowser.open()` を別スレッドで呼びます。`--no-browser` はブラウザー起動を抑止しますが、server の準備完了表示やローカル URL 表示は残ります（`setup.py:6844-6846,6864-6866`、`serve/server.py:8177,8620-8623,8639-8644`）。

## 適用条件と副作用

このオプションは setup の Python parser にあるため、同 parser に委譲する各 wrapper で利用できます。既存 config の起動時は `open_browser` の値をモデル設定ファイルに書き込みます。新規設定時にはモデル別の `strata-<model>.json` と `run-<model>.sh` / `.bat` の生成内容に反映します（`setup.py:6766-6768,7260-7269,7694-7718`）。このフラグ自体はブラウザーを開く処理を起動せず、setup のモデル準備・server 起動を止めるものではありません。

`--update` との併用では update が設定を更新してもモデルを起動しないため、ブラウザー抑止は保存され、後の起動で使われます（`setup.py:8496-8498` および update wrapper の `update.sh:62` / `UPDATE.bat:79`）。なお、対象は setup の `setup.py` parser です。server の直接起動用 CLI には別の `--open` があり、`--no-browser` は server のオプションではありません（`serve/server.py:8177`）。

## 出力とエラー

明示指定した `--no-browser` によって既存モデルの保存値が変わる場合、setup は設定保存後に `saved for this model: no browser` を表示します（`setup.py:6766-6771`）。通常起動ではブラウザーの自動起動を省き、server は準備完了時に URL を表示します（`setup.py:6864-6866`、`serve/server.py:8620-8623`）。オプション固有の警告や失敗経路は確認できませんでした。無効な option や余分な値のエラーは argparse の一般的な引数エラーで、オプション固有の validation ではありません（parser: `setup.py:8420,8476-8480,8553`）。

## 根拠

- parser 定義と対になる `--browser`: `setup.py:8476-8480`
- 既存 config の永続化と表示: `setup.py:6745-6771`
- ブラウザー起動の条件・案内: `setup.py:6844-6846,6864-6866`、`serve/server.py:8177,8639-8644`
- 設定生成・run script への反映: `setup.py:7260-7269,7685-7718,8140-8148,8388-8405,9729-9730`
- setup の設定 carry over と update 時の非起動: `setup.py:6162-6167,6312-6342,8496-8498,9759-9766`
- wrapper の引数委譲: `setup.sh:6-13,75-76`、`START-HERE.bat:8-10,44-54`、`update.sh:62`、`UPDATE.bat:79`
- 索引上の所属と scope: `docs/cli/README.md:13,1465-1502`

調査は上記 commit の checkout 内の parser・使用箇所・wrapper・server 起動処理に限定しました。CLI help、Release artifact、他 OS での実行結果は補助確認していません。
