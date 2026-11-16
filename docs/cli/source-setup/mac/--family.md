# `--family`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS 用 `metal/setup_mac.py`（`setup.py` から委譲） |
| オプション | `--family` |
| 別名 | なし |
| 値 | `qwen`、`unsloth`、`gyro`、または読み込まれた署名 feed に登録された family ID |

## 役割

`--family` はモデル family 名を受け取ります。ただし、macOS セットアップで実際に使う family は選択した `--model` の `MAC_MODELS` エントリーから決まります。指定値とモデル側の family が違う場合は警告を出し、モデル側の family を使います。そのため、family を指定してもモデルの絞り込みや強制にはなりません。

## 使い方

```sh
# Unsloth family のモデルを選び、設定後にサーバーは起動しない
./setup.sh --family unsloth --model UD-IQ4_XS --no-start
```

`--family` は `--model` と組み合わせて指定できます。family だけを指定した場合のモデル選択は「実行時の動作」を参照してください。

## 値と既定値

- 省略時は `None` です。短縮別名はありません。
- parser の choices は組み込みの `qwen`、`unsloth`、`gyro` と、セットアップ前に読み込まれた feed の family ID です。feed の family は `strata_control.mac_fit.FEED_FAMILIES` に加えられ、`MAC_MODELS` にモデルが登録されます。
- feed の family を指定した場合、feed が取得できなければ前回検証済みのキャッシュが利用されることがあります。どちらも利用できず family ID が choices にない場合、parser は値を受理しません。

## 実行時の動作

1. `setup.py` は macOS で通常の PC 用 parser を通さず、引数を `metal/setup_mac.py` にそのまま渡します。
2. `setup_mac.py` は parser を作る前に `--family` を確認します。組み込み 3 family 以外の値なら、署名 feed のモデル一覧を読み込んで feed family を登録しようとします。
3. parser は `--family` を choices で検証します。モデルは別引数 `--model` で指定し、`--model` がなければ `--family` による絞り込みをせず、利用可能なモデル一覧から対話選択します。
4. 既存の設定があり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれもない場合は、既存モデルをそのまま起動する早期経路に入ります。この条件には `--family` が含まれないため、`--family` 単独では既存モデルの起動先を切り替えません。
5. セットアップ経路では、選ばれたモデルの `MAC_MODELS[model].family`（未設定なら `qwen`）を実際の family として採用します。`--family` と違えば `--family <指定値>: <model> is a <family> file; using <family>` と警告して続行します。この family がダウンロード元、モデルタグ、準備処理、設定ファイル名に使われます。

feed family の読み込みは、未登録 family を指定しただけでも parser 検証より先に試みられます。feed の取得が有効で署名付き一覧を取得できた場合、その一覧はオフライン利用用キャッシュに記録されます。取得失敗時は既存の検証済みキャッシュにフォールバックし、一覧がない場合は feed 由来の選択肢は追加されません。

## 適用条件と副作用

- この文書の parser は Apple Silicon / macOS の Metal セットアップ用です。`setup.py` は `sys.platform == "darwin"` かつ Control モードでない場合に `metal/setup_mac.py` を呼び出します。
- family のみを指定して既存設定がない場合、モデル一覧から選択します。指定 family に応じた絞り込みや、その family のモデルを自動選択する処理は確認できません。
- feed family の照会は、対象値が組み込み family 以外の場合に parser 構築前に起きます。feed を取得できる条件ではネットワークアクセスがあり、取得した署名付きモデル一覧は更新 feed 用ディレクトリの `feed-models.json` に保存されます。保存できない場合は警告ログにとどまり、処理を続けます。
- モデルのダウンロード、ビルド、モデル準備などの副作用は、`--family` 自体ではなく、後続のセットアップ経路と選択モデルによって発生します。

## 出力とエラー

- 指定値と選択モデルの family が異なる場合、`S.warn` による警告を表示し、モデル側の family で続行します。
- family が parser choices に含まれない場合は choices 検証で拒否されます。未登録の値では、その検証より前に feed 読み込みが試行される場合があります。
- このオプション専用の Strata エラー出力や終了コードは確認できません。feed の取得・キャッシュ読込エラーは `feed_models.load` 内で処理され、最終的に利用できるキャッシュがなければ feed family を追加せずに戻ります。

## 根拠

- `setup.py:8309-8313` — macOS で使用するセットアップ実装への引数委譲。
- `setup.py:9330-9331` — macOS かつ Control モードでない場合に Metal セットアップへ入る条件。
- `metal/setup_mac.py:360-368` — 組み込み外の `--family` を parser 作成前に検出して feed モデル一覧を読む条件。
- `metal/setup_mac.py:371-378` — `--family` の parser 定義、既定値、choices、および別引数 `--model`。
- `metal/setup_mac.py:402-404` — parser が既知引数を解析し、残りの引数を警告する処理。
- `metal/setup_mac.py:415-417` — 既存設定をそのまま起動する早期経路。条件に `a.family` が含まれない。
- `metal/setup_mac.py:433-447` — `--model` 未指定時は全モデル一覧から選び、family 値で絞らない処理。
- `metal/setup_mac.py:461-465` — モデル定義から実 family を決め、指定値との不一致を警告してモデル側を採用する処理。
- `metal/setup_mac.py:496-512` — 実 family とモデルを使うダウンロード・shard 検証・family pin 検証。
- `strata_control/mac_fit.py:176-185` — 組み込み Mac family と feed family リスト。
- `strata_control/feed_models.py:110-137` — feed 取得、検証済みキャッシュへのフォールバック、取得一覧の記録。
- `strata_control/feed_models.py:337-347` — feed モデルを `MAC_MODELS` と `FEED_FAMILIES` に登録する処理。
- `setup.py:8568-8583` — Mac セットアップから呼ばれる feed モデル読み込みと登録。
