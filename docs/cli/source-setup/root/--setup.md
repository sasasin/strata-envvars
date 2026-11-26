# `--setup`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（Linux は `./setup.sh`、Windows は `START-HERE.bat` から起動） |
| オプション | `--setup` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常起動時に保存済みモデルをそのまま起動する経路から抜け、モデルの追加や設定変更を行うセットアップ経路を選びます。`setup.py` の説明でも「別のモデルをインストールする／設定を変える」用途として定義されています（`terminal/setup.py:23-28,11525`）。

## 使い方

Linux:

```sh
./setup.sh --setup
```

Windows:

```bat
START-HERE.bat --setup
```

モデルや設定を明示して再設定する例:

```sh
./setup.sh --setup --family qwen --model IQ3_S --context 32768
```

Linux と Windows のラッパーは引数を `setup.py` に渡します（`setup.sh:6-17`、`START-HERE.bat:49-65`）。

## 値と既定値

値は不要です。parser は `action="store_true"` で宣言しており、省略時は偽、指定時は真です。別名、値の範囲、値に対する個別 validation はありません（`terminal/setup.py:11525`）。値を後置する構文は定義されておらず、未知の引数など argparse が受理しない構文は parser のエラーになります（`terminal/setup.py:11444-11445,11606`）。

## 実行時の動作

`--setup` が真だと `plain_start` が偽になり、既存モデルをそのまま起動する分岐の条件も満たさなくなるため、PC の確認とセットアップの選択処理へ進みます。既存モデルがある場合に `--setup` を省略すると通常起動へ進み、複数モデルがある場合も標準の選択肢に「別モデルのインストール／設定変更」があります（`terminal/setup.py:11681-11688,11761-11779,11781-11783`）。

セットアップ経路では選んだモデルや設定に応じて、Python パッケージやエンジンの準備、モデルファイルの取得・準備、起動用スクリプトと run config の作成を行います（`terminal/setup.py:11-21,12353-12360,12380-12390,12505-12527`）。run config は保存され、同じモデルの既存 config が変更される場合は `.bak` にコピーされます（`terminal/setup.py:7715-7747`）。

正常終了時は `--no-start` がなければ最後にモデルを起動します。したがって `--setup` 単独は「セットアップして終了」ではありません。セットアップだけで終える場合は `--no-start` を併用します（`terminal/setup.py:11525-11526,12534-12562`）。

## 適用条件と副作用

- `--setup` と `--model` / `--family` を組み合わせると、選択対象を指定したセットアップになります。これらは `explicit` に含まれ、初回の既存設定引き継ぎ判定にも影響します（`terminal/setup.py:11698-11723`）。
- `--yes` は推奨選択を採用して質問を抑えます。`--setup` 自体は確認を省略しません（`terminal/setup.py:11524-11525`）。
- `--update` を同時に指定すると update 分岐が先に実行され、`--setup` の通常セットアップ経路には進みません（`terminal/setup.py:11692-11698`）。
- `--check` も同時に指定した場合は PC の適合確認を行ってそこで終了し、モデルのセットアップには進みません（`terminal/setup.py:11960-11979`）。`--calibrate` は `--setup` と併用しても校正を行わず、その旨の警告を出します（`terminal/setup.py:11730-11733`）。
- セットアップでファイルのダウンロード、パッケージやエンジンの準備、run config と起動スクリプトの書き込みが起こり得ます。個々の処理は既存状態や他の引数によって異なります（`terminal/setup.py:12353-12360,12380-12400,12505-12527`）。
- Apple Silicon の macOS で Control モードではなく、Hy4-Flash / Inkling-2-Mini の専用経路でもない場合は、parser の実行前に `engine/metal/setup_mac.py` へ引数ごと委譲されます。macOS 側にも別 parser の `--setup` がありますが、これは索引上の `source-setup/mac/--setup.md` のスコープです（`terminal/setup.py:11434-11437,9290-9294,11628-11634`）。

## 出力とエラー

`--setup` 固有の成功メッセージや終了コードはありません。セットアップ中の進行・警告・失敗は各段階から出力されます。通常のセットアップ失敗ではエラーと再実行案内を表示して終了コード 1 で停止し、割り込みは「stopped.」を表示して終了コード 1 になります（`terminal/setup.py:1049-1056,12565-12579`）。

## 根拠

- parser と既定値: `terminal/setup.py:11444-11445,11524-11530,11606`
- 通常起動とセットアップ経路の分岐: `terminal/setup.py:11681-11698,11761-11783`
- config 保存とバックアップ: `terminal/setup.py:7715-7747,12521-12527`
- セットアップ後の起動・`--no-start`: `terminal/setup.py:12534-12562`
- Linux / Windows の引数転送: `setup.sh:6-17`、`START-HERE.bat:49-65`
- macOS の委譲先: `terminal/setup.py:11436-11437,9290-9294`、別 parser `engine/metal/setup_mac.py:395-398`
