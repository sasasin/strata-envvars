# `--rollback-engine`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`UPDATE.bat` からの入口） |
| オプション | `--rollback-engine` |
| 別名 | なし |
| 値 | 取らない（`store_true`） |

## 役割

直前のエンジン更新で `engine/.previous` に保存されたエンジンを現行位置へ戻す。戻す前に現行エンジンを `.previous` に移すため、同じ操作をもう一度実行すると元のエンジンへ戻せる。

## 使い方

```sh
python terminal/setup.py --rollback-engine
```

CUDA 12 用エンジンを戻す場合は、保存先を選ぶため `--cuda 12` も指定する。

```sh
python terminal/setup.py --rollback-engine --cuda 12
```

## 値と既定値

フラグのみで値は受け取らない。省略時はロールバックしない。複数回指定しても `store_true` のため有効状態は変わらない。値を付けた場合は `argparse` の引数エラーになる。

対象ディレクトリは `--cuda 12` のとき `engine-cuda12/`、それ以外は `engine/`。`--cuda` の受理値は `12`、`13`、`auto` で、既定値は `STRATA_CUDA` 環境変数または未指定である。ただしロールバック先の選択は値が文字列 `12` と一致するかだけで決まり、`13`、`auto`、未指定（および `STRATA_CUDA` が `12` 以外）では `engine/` が対象になる。

## 実行時の動作

parser が引数をすべて解析した後、`--rollback-engine` が立っていれば通常の起動・更新処理より先にロールバック関数を呼び、結果をそのまま終了コードとして返す。したがって `--update` など他の通常モード用フラグも同時に受理されるが、ロールバック分岐で終了するためその処理には進まない。

対象の `<engine>/.previous` が存在し、中に項目があれば、一時ディレクトリ `<engine>/.swap` を作り、`.previous` 内の各項目を現行エンジンへ移す。移動先に同名項目があれば先に `.swap` へ退避し、最後にその項目群を `.previous` に戻して一時ディレクトリを削除する。結果として前世代と現世代が入れ替わる。エンジンの版数は `BUILD.json` の `version` から表示し、読み取れない場合は `?` になる。

## 適用条件と副作用

`.previous` はエンジン置換時に作られ、置換対象の既存ファイルを一世代分保存する場所である。次の置換では既存 `.previous` を削除して作り直すため、保存できるのは直近の一世代だけ。ロールバック関数自体はエンジンファイル群を移動し、モデルも起動しない。

ただし、ロールバック関数へ入る前に `move_over_old_layout()` と `data_folder_for(a)` が呼ばれる。旧レイアウト移行条件に該当するとモデル・pack・エンジンなどを `terminal/` 側へ移動し、通常のデータフォルダー処理では同一ドライブ上の既存モデルファイルを集約し、設定ファイルのパスや `settings.json` を更新する場合がある。従ってこのフラグを付けた実行でも、それらの前処理によるファイル移動や設定変更が起こり得る。`--move-data`、`--data-dir`、`--set-default-data-dir` も前処理には作用する。

Apple Silicon の通常経路では `setup.py` が自身の parser より前に Metal 用 `setup_mac.py` へ引数を委譲する。Metal 側 parser は未知引数を警告して処理を続け、`--rollback-engine` を定義していないため、この macOS 経路ではエンジンのロールバックにはならない。

## 出力とエラー

対象 `.previous` が存在しない、または空の場合、対象パスと「更新時に保存される」旨の警告を出し、終了コード `1` を返す。成功時は入れ替え後のエンジン版数と、退避された置換前の版数・保存先を `[ok]` メッセージで表示して `0` を返す。入れ替え中のファイル操作にはこの関数内で例外回復処理がなく、移動や `.swap` 作成に失敗した場合は正常終了メッセージまで到達しない。`--output jsonl` を併用すると、標準出力は JSON Lines 用に確保され、成功・警告イベントも出力される。

## 根拠

- `terminal/setup.py:11533-11534` — root parser における `store_true` オプション定義。
- `terminal/setup.py:11546-11549` — `--cuda` の値と既定値。
- `terminal/setup.py:11606-11607`、`terminal/setup.py:11692-11693` — 引数解析後にロールバックを通常処理より先に実行し、`--cuda 12` のとき toolkit 12 を選ぶ。
- `terminal/setup.py:11608-11609`、`terminal/setup.py:11676-11693` — ロールバック分岐より前に旧レイアウト移行、設定・インストール確認、データフォルダー処理を行う。
- `terminal/setup.py:8436-8464` — 条件付き旧レイアウト移行でファイルを移動する処理。
- `terminal/setup.py:7419-7516` — データフォルダー処理によるモデルデータの移動、設定ファイルと保存設定の更新、および関連オプション。
- `terminal/setup.py:967-980` — `--output jsonl` のイベント出力経路。
- `terminal/setup.py:2166-2168` — toolkit 12 とそれ以外のエンジンディレクトリ対応。
- `terminal/setup.py:6215-6255` — エンジン置換時に既存ファイルを `.previous` に一世代保存し、前の `.previous` を消す処理。
- `terminal/setup.py:6258-6279` — `.previous` の有無確認、ファイル群の交換、警告・成功メッセージと戻り値。
- `terminal/setup.py:9290-9294`、`engine/metal/setup_mac.py:375-405` — macOS での委譲と、Metal parser が未知引数を警告して続行する処理。

