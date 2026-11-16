# `strata components use --backend`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use <engine>` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | バックエンド名を取る文字列。parser に型・候補制限はなく、省略時はハードウェア検出を使う |

## 役割

インストール済みエンジンを選ぶときのバックエンド／ハードウェア条件を指定します。通常は PC の GPU を検出し、明示するとその指定を使って候補の適合性を判定します。検出中の backend と異なるメーカー用エンジンを選んだ場合、かつその GPU が PC に存在すると確認できた場合は、そのメーカーの選択も次回以降の起動用に保存します。`--backend` でそのメーカーを明示して対象 engine と同じ backend にした場合はこの保存経路を通りません。このコマンドはローカルにあるエンジンを切り替えるもので、ダウンロードはしません。

## 使い方

```sh
# AMD 用としてインストール済みの 0.1.54 を選ぶ
strata components use 0.1.54 --backend amd

# CUDA 用の特定フォルダーを選ぶ
strata components use 0.1.54-linux-x86_64-cuda --backend nvidia
```

候補のバージョンやフォルダー名は `strata components engines` で確認できます。同じバージョンが複数候補に一致するときは、曖昧さを避けるためフォルダー名を指定します。

## 値と既定値

`strata_cli/update_cmd.py` の共通 parser は `--backend` を `default=None` の文字列引数として登録し、`choices` や `type` を設定していません（`strata_cli/update_cmd.py:47-56,84-87`）。省略時は `updater.detect_hardware()` が使われ、環境変数 `STRATA_ENGINE_BACKEND`、保存済み選択、OS・GPU 検出の順で判断します（`strata_cli/update_cmd.py:310-317`、`strata_control/engine_component.py:528-548`）。

既知の別名は `nvidia` → `cuda`、`amd` → `hip`、`intel` / `arc` → `sycl` です。`hip-rdna2` のような `hip-<variant>` も受け付け、バックエンド `hip` と variant に分けます（`strata_control/engine_component.py:476-488`）。`metal`、`cuda`、`hip`、`sycl`、`cpu` はコンポーネントで扱うバックエンドです（`strata_control/targets.py:22-31`）。

parser は値を検証しません。未知の文字列は parser では拒否されず、後段の候補適合性判定で扱われます。コマンドで使われる適合性判定は OS、バックエンド、Strata runtime、GPU arch、NVIDIA driver とファイル検証を参照します（`strata_control/engine_library.py:65-88`）。

## 実行時の動作

明示された値は `requested_hardware()` で正規化され、対象バックエンドを環境変数に一時設定したのと同じ形でハードウェア情報を検出します。認識できるバックエンドならその指定が優先され、未知の名前はハードウェア情報の `backend` 欄にそのまま設定されます（`strata_cli/update_cmd.py:279-296,310-317`）。

そのハードウェア情報を使ってインストール済みエンジン一覧を適合性判定し、位置引数のバージョンまたはフォルダー名から対象を特定します（`strata_control/engine_library.py:98-134,184-197`）。`--backend` は一覧の候補を直接選んだり、同一バージョンの曖昧さを解消したりはしません。`--family` が指定されていれば、その値でファミリーを絞って候補を探します（`strata_cli/update_cmd.py:84-87`）。

対象が現在の hardware context と異なる backend でも、その backend が実機にある別メーカーなら、Strata のユーザー設定 `engine_backend` に保存してから切り替えます。実装条件は `target.backend != ctx.hardware.backend` かつ `target.backend` が検出済み `makes` に含まれることです。`--backend amd` のように明示指定して context と対象の backend が同じならこの保存分岐には入りません。保存後の切り替えに失敗した場合は以前の選択に戻します（`strata_control/engine_library.py:277-293`、`strata_control/engine_component.py:488-525`）。エンジン選択自体は component state の pin と履歴を更新し、最新エンジンを選ぶ場合は pin を外して更新追従に戻します（`strata_control/updater.py:1398-1447`）。エンジンの同一性が変わると保存済み tuning preset が再確認対象としてマークされる場合がありますが、削除はされません（`strata_control/updater.py:1442-1447`）。

## 適用条件と副作用

- 対象エンジンが別 OS、未対応バックエンド、非対応 GPU arch、古い runtime / driver、または欠損・改変ファイルに該当すると適合しません（`strata_control/engine_library.py:65-88`）。適合しない場合は切り替えずエラーになります（`strata_cli/update_cmd.py:439-444`）。
- エンジンを使用中のモデルがある場合は切り替えを拒否または待機します。`--wait` がなければ対話端末では待機確認を出し、非対話では busy エラーになります（`strata_control/engine_library.py:202-228`、`strata_cli/update_cmd.py:473-488`）。
- 切り替えでローカル component state の engine pin、previous / skipped 情報、履歴が更新されます（`strata_control/updater.py:1404-1445`）。別メーカーのエンジンを選んだ場合はさらにユーザー設定の `engine_backend` が更新されます（`strata_control/engine_library.py:281-292`）。ダウンロードやエンジンファイル削除はこの `use` 経路では行いません（`strata_control/engine_library.py:211-228`）。
- `hip-<variant>` の variant はハードウェア情報に記録されますが、この `use` の適合性・候補特定では参照されません。候補適合性判定はバックエンド family などを確認し（`strata_control/updater.py:327-336`、`strata_control/engine_library.py:65-88`）、候補名の照合は folder / version / `newest` で行います（`strata_control/engine_library.py:184-197`）。

## 出力とエラー

正常終了時は、人向け出力で切り替え先と状態を表示します。`--output json` または `jsonl` の場合は成功結果を JSON として出力します（`strata_cli/update_cmd.py:439-464`）。対象が見つからない、曖昧、または無効な場合は終了コード 2、対象がこの PC で実行できない場合や検証に失敗した場合は通常終了コード 5、実行中モデルで切り替えが阻止された場合は終了コード 7 です（`strata_control/engine_library.py:184-207,238-254`、`strata_cli/update_cmd.py:439-444,368-372`）。人向けエラーは `strata:` を付けて stderr に出し、機械向け出力では `ok: false` とエラー情報を JSON に出します（`strata_cli/update_cmd.py:303-308`）。

## 根拠

- `strata_cli/cli.py:113-139` — `components` parser と update command parser の登録。
- `strata_cli/update_cmd.py:47-56,84-87` — `--backend` の定義、`use` の位置引数・共通引数への組み込み。
- `strata_cli/update_cmd.py:279-296,310-317,419-464` — 指定値から hardware context を作り、対象を適合判定して切り替える実行経路。
- `strata_control/engine_component.py:476-488,528-548` — backend alias / variant の正規化と、省略時検出の優先順位。
- `strata_control/engine_library.py:65-88,184-228,277-312` — 適合条件、候補特定、使用中チェック、別 GPU backend の保存、engine 切り替え。
- `strata_control/updater.py:1398-1447` — pin、履歴、tuning preset 状態の更新。
- `strata_control/targets.py:22-31` — 対応 OS と backend family の組み合わせ。
