# `setup.py --inspect`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` の root 呼び出し |
| オプション | `--inspect` |
| 別名 | なし |
| 値 | 1個以上。SOURCE と任意の VARIANT。SOURCE はローカルファイル、フォルダー、URL、`ms:owner/repo`（ModelScope）または `hf:owner/repo`（Hugging Face）。VARIANT は名前の部分一致または glob。 |

## 役割

GGUF ファイルのヘッダーからテンソル構成・量子化情報を表示し、Strata が配布対象としているモデルの指紋と照合します。ファイル名の量子化ラベルだけで判断せず、Strata が認識する形式との一致、同じ routed-expert 配置だが未検証の形式、非対応といった判定を出します。通常のセットアップには進まず、helper の終了コードをそのまま返します（`terminal/setup.py:11543-11545`, `terminal/setup.py:11626-11627`, `terminal/tools/strata_inspect.py:1-5`, `terminal/tools/strata_inspect.py:100-135`, `terminal/tools/strata_inspect.py:187`）。

## 使い方

```bash
# ローカルの GGUF ファイル、または GGUF を含むフォルダーを調べる
python terminal/setup.py --inspect /models/my-model-00001-of-00002.gguf

# ModelScope リポジトリ内の候補を一覧表示する
python terminal/setup.py --inspect ms:ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF

# variant 名（または glob）で絞る
python terminal/setup.py --inspect ms:ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF IQ3_S

# Hugging Face のリポジトリを指定する
python terminal/setup.py --inspect hf:owner/repo 'Q4*'
```

## 値と既定値

- setup parser は `nargs="+"` で1個以上の値を受け取ります。SOURCE は必須で、2個目は任意の variant 名です。3個目以降も parser では受理されますが、setup は helper に先頭2個しか渡さないため無視されます（`terminal/setup.py:11543-11545`, `terminal/setup.py:11626-11627`）。値なしで `--inspect` を指定すると argparse が usage とエラーを表示して終了します。
- variant を省略すると全 variant が候補になります。variant が複数残れば名前・ファイルサイズ・ファイル数を一覧表示します。1つに絞られた場合はそのファイル群を調べます（`terminal/tools/strata_inspect.py:172-177`）。
- SOURCE が HTTP(S) URL の場合、URL末尾の1ファイルを対象にします。ローカルフォルダーは再帰走査します。Hub 指定はリポジトリのファイル一覧を取得します（`terminal/tools/quantscope.py:78-107`）。
- setup 経由の helper は `.gguf` で終わるファイルだけを対象とし、名前に `mmproj` を含むファイルは除外します。拡張子判定は大文字小文字を区別します（`terminal/tools/strata_inspect.py:166-170`）。

## 実行時の動作

1. setup が引数を解析し、旧レイアウトのデータ移動や `--update` の処理などを行った後、`--inspect` があれば Python interpreter で `terminal/tools/strata_inspect.py` を起動し、SOURCE と任意の VARIANT の最大2値を転送します。`--prepare-pack` が同時指定されると、その処理が先に選ばれて inspect は実行されません（`terminal/setup.py:11606-11627`）。
2. helper は SOURCE を解決します。Hub は API で一覧を取り、HTTP URL は HEAD でサイズを得ます。ヘッダーの読み取りはローカルファイルなら seek/read、リモートなら Range リクエストです。HTTP の読み取りは最大5回試行し、各接続の timeout は60秒です（`terminal/tools/quantscope.py:46-58`, `terminal/tools/quantscope.py:67-75`, `terminal/tools/quantscope.py:78-107`, `terminal/tools/quantscope.py:128-139`）。
3. variant はファイル名から shard 番号と拡張子を外してグループ化します。選択した GGUF の shard を名前順に読み、テンソル・格納サイズ・量子化の構成を集計します（`terminal/tools/quantscope.py:110-112`, `terminal/tools/strata_inspect.py:168-184`, `terminal/tools/quantscope.py:170-197`, `terminal/tools/quantscope.py:308-333`）。
4. 集計値を `terminal/data/gguf_fingerprints.json` と比較します。完全一致は既知の family/model、routed experts の格納が一致するものは未検証の同系配置、Strata が扱わない expert quantization は非対応、それ以外は未検証として説明します（`terminal/tools/strata_inspect.py:35`, `terminal/tools/strata_inspect.py:100-135`, `terminal/tools/strata_inspect.py:185-187`）。

## 適用条件と副作用

- この分岐はインストール・モデルのダウンロード・エンジン起動を行わず、通常セットアップをスキップします。ただし setup 全体の前処理後に分岐します。`move_over_old_layout()` は旧配置からファイルやディレクトリを `terminal/` へ rename する場合があり、`--update` は Git checkout で `git pull` を試みます。inspect のみを目的とする場合、これらと同時指定しないでください（`terminal/setup.py:11606-11613`, `terminal/setup.py:8436-8464`, `terminal/setup.py:8386-8418`, `terminal/setup.py:11626-11627`）。
- Hub・URL 指定はネットワークアクセスを行います。GGUF の本体全体をダウンロードせず、ファイル一覧・サイズ情報とヘッダー範囲を取得します（`terminal/tools/quantscope.py:46-58`, `terminal/tools/quantscope.py:78-103`, `terminal/tools/quantscope.py:128-139`）。
- `--output jsonl` と併用すると setup が stdout を stderr に振り替えてから helper を起動するため、inspect の表示も stderr に流れます。inspect 自体の JSONL イベント出力は実装されていません（`terminal/setup.py:11527-11529`, `terminal/setup.py:967-974`, `terminal/setup.py:11606-11608`, `terminal/tools/strata_inspect.py:155-187`）。
- `STRATA_SOURCE` や setup の `--source` はモデル取得元の設定であり、inspect の SOURCE 解釈を切り替えません。inspect helper は `ms:` / `hf:` / URL / ローカルパスを独自に解決します（`terminal/setup.py:11536-11539`, `terminal/setup.py:11622-11627`, `terminal/tools/quantscope.py:34-43`, `terminal/tools/quantscope.py:95-107`）。

## 出力とエラー

- variant が複数ある場合は `variants (pass one as the second argument)` と候補一覧を stdout に出し、helper は正常終了します（`terminal/tools/strata_inspect.py:173-177`）。選択した場合は量子化・テンソル集計と `Strata: ...` の判定を stdout に出します（`terminal/tools/quantscope.py:308-333`, `terminal/tools/strata_inspect.py:182-187`）。
- 判定 `known` と `layout` は終了コード 0、`no` は 2、`untested` も 0 です。したがってコード0だけでは Strata で動作確認済みとは限りません（`terminal/tools/strata_inspect.py:100-135`, `terminal/tools/strata_inspect.py:185-187`）。
- 対象 GGUF がない場合や variant が一致しない場合は `sys.exit` のエラー文字列で終了します。壊れたヘッダー・ネットワーク障害などの例外は helper 内で捕捉されず、Python の例外出力になります（`terminal/tools/strata_inspect.py:166-179`, `terminal/tools/quantscope.py:46-58`, `terminal/tools/quantscope.py:170-197`）。setup は helper の終了コードをそのまま終了コードにします（`terminal/setup.py:11626-11627`）。

## 根拠

- `terminal/setup.py:11543-11545` — root parser の宣言、値数と SOURCE / VARIANT の説明。
- `terminal/setup.py:11606-11627` — parse 後の前処理、優先される `--prepare-pack`、helper 呼び出しと終了コード転送。
- `terminal/setup.py:8436-8464`、`terminal/setup.py:8386-8418` — inspect 分岐より前に起こり得る旧配置の rename と `--update` の pull。
- `terminal/tools/strata_inspect.py:155-187` — helper の引数、GGUF 選択、結果表示と判定別終了コード。
- `terminal/tools/quantscope.py:46-107`、`terminal/tools/quantscope.py:128-197` — ローカル / リモートのソース解決と GGUF ヘッダー読み取り。
- `terminal/tools/strata_inspect.py:100-135` — 指紋比較の判定条件。

調査制約: 同一 revision の CLI help は実行せず、parser と helper のソースを確認しました。ネットワーク実行時の Hub API 応答や個々の URL サーバーの Range 対応は実測していません。
