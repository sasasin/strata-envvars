# `--backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | 必須の文字列。parser に `choices` や型変換の指定はない。エンジンファミリー名を渡す |

## 役割

エンジン更新先のファミリーを明示します。省略時は、この PC の GPU などから検出したファミリーを使います。指定値は更新コンテキストの backend として扱われ、feed から適合するエンジンパッケージを選ぶ際に使われます（`strata_cli/update_cmd.py:30-39,163-184`、`strata_control/updater.py:566-580`）。

## 使い方

```sh
strata update --backend cuda --check
```

`--check` は feed を読み、選択内容を表示します。更新を実行する場合は `--check` を外します。`strata components update` にも同じ parser 定義が使われます（`strata_cli/update_cmd.py:42-56`）。

## 値と既定値

- 値は1つの文字列です。省略時の parser 値は `None` です（`strata_cli/update_cmd.py:30-34`）。
- parser 自体には許可値の列挙や validation がありません。非空文字列を指定すると、その値が `hardware["backend"]` にそのまま設定され、`backend_source` は `requested` になります（`strata_cli/update_cmd.py:174-180`）。
- 実際に feed のエンジンパッケージと照合される名前は `metal`、`cuda`、`hip`、`sycl`、`cpu` です。これは backend/platform 対応表のキーです（`strata_control/targets.py:20-29`）。未知の名前も CLI parser では拒否されませんが、同じ backend 名のパッケージがなければ選択結果は「この PC 向けのパッケージなし」になります（`strata_control/feed.py:372-395,398-416`、`strata_control/updater.py:573-590`）。
- 省略時は `updater.detect_hardware()` が backend を検出します。`STRATA_ENGINE_BACKEND` があれば環境変数側の処理で値を正規化して検証し、不正ならエラーになります。GPU 検出ではなく環境変数を使った場合の検出元は `environment` です（`strata_control/updater.py:249-270`、`strata_control/engine_component.py:439-482`）。明示した非空の `--backend` はその結果を上書きします。
- CLI の `--backend` 値は小文字化や空白除去をされません。空文字列を渡した場合は `if a.backend` が偽になるため上書きに使われず、検出値が残ります（`strata_cli/update_cmd.py:176-180`）。

## 実行時の動作

`strata update` は選択した backend を使い、署名済み feed 内から platform、backend、GPU アーキテクチャ、必要 runtime/driver などが合うエンジンを選びます。backend が一致しないパッケージは候補から外れます（`strata_control/feed.py:372-395`）。更新実行時は、取得・検証した engine を試験起動してから切り替えます（`strata_cli/update_cmd.py:43-45`、`strata_control/updater.py:926-960,992-1027`）。

この指定はエンジン選択に作用します。`--no-engine` を併用すると engine 更新工程自体が省略されますが、Control 更新など他工程は独立して動作します（`strata_cli/update_cmd.py:48-56,203-224`、`strata_control/updater.py:1274-1297`）。`--check` でも backend は選択結果に反映されますが、ダウンロードは feed の読み込みに限られ、確認結果を状態ファイルへ記録します（`strata_control/updater.py:624-640`）。

明示値は `backend_source="requested"` と記録されるため、異なる GPU メーカーの engine を更新しないための `make_guard` を通過します（`strata_cli/update_cmd.py:177-180`、`strata_control/updater.py:539-563`）。ただし、これは PC の GPU 情報、CUDA/HIP のアーキテクチャ情報や driver 情報を書き換えません。指定 backend と検出済みハードウェアの組み合わせに合う feed パッケージがなければ選択されません。更新 package が既存 engine と別メーカーの場合の後段拒否も、`backend_source` が `requested` のときは適用されません（`strata_control/updater.py:938-942`）。明示値は実際の GPU に適合する場合に限って使用してください。

## 適用条件と副作用

- `--backend` は `strata update` と `strata components update` に共通です。`strata components rollback` も共通 option parser を使いますが、rollback の経路では backend は更新 feed の選択には使われず、指定値は rollback 後の engine 解決に渡されます（`strata_cli/update_cmd.py:42-59,174-196`、`strata_control/engine_component.py:859-891`）。
- `strata update --check` の際も hardware 検出と backend 選択が行われます。通常の更新では feed を取得し、選択された engine/Control 等の更新処理に進みます（`strata_cli/update_cmd.py:174-213`、`strata_control/updater.py:624-632,1274-1285`）。
- parser に enum validation がないため、タイプミスは使用法エラーにならず、該当 engine がない結果につながります。`--check` では `none-for-this-pc` と理由が表示されます。通常更新でも engine の選択が `none-for-this-pc` ならその工程は更新なしとして扱われ、他の有効な更新工程は続き、例外がなければ終了コードは `0` です（`strata_cli/update_cmd.py:132-152`、`strata_control/updater.py:581-590,926-937,1274-1297`）。
- `strata update --backend hip-rx9070` のような HIP variant 指定は CLI 側では backend 値そのものとして扱われ、環境変数 `STRATA_ENGINE_BACKEND` にある `hip-<variant>` の解釈処理は通りません。feed の `backend` が `hip-rx9070` であるパッケージを探す形になるため、通常の `hip` backend 指定とは同じではありません（`strata_cli/update_cmd.py:176-180`、`strata_control/updater.py:254-260`、`strata_control/feed.py:380-383`）。

## 出力とエラー

無効な backend 名に対する専用 parser エラーはありません。適合パッケージが見つからない場合は、通常出力に engine の選択不可状態と理由を含めます（`strata_control/updater.py:566-590`、`strata_cli/update_cmd.py:132-152,217-224`）。署名済み feed、network、package 検証、試験起動などで更新工程が失敗すると、その工程のエラーを報告し、失敗の終了コードを返します。具体的なコードは失敗原因により異なります（`strata_cli/update_cmd.py:225-234`、`strata_control/updater.py:1274-1297`）。

## 根拠

- parser と共有スコープ: `strata_cli/update_cmd.py:30-59`
- `strata update` 実行時の値反映、`--check` / update 分岐、エラー出力: `strata_cli/update_cmd.py:163-234`
- backend 検出と `STRATA_ENGINE_BACKEND` の検証: `strata_control/updater.py:249-270`、`strata_control/engine_component.py:439-482`
- package 適合性・backend による選択: `strata_control/feed.py:372-416`
- メーカー変更ガードと更新 package の処理: `strata_control/updater.py:539-590,926-942`
- 選択不可時の更新結果と終了コード: `strata_control/updater.py:624-640,1274-1297`
- backend/platform 対応表: `strata_control/targets.py:20-29`

調査は指定 revision のソースを対象とし、CLI help の実行、build、テスト、GPU 実行は行っていません。
