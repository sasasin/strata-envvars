# `--vision`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象 checkout は `main`、working tree clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | Apple Silicon Mac のソース setup（`./setup.sh` → `setup.py` → `metal/setup_mac.py`） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `yes`、`no`、`gpu`、`cpu` のいずれか。値は必須 |

## 役割

選択したモデルに画像読み取り機能を設定し、画像 encoder と vision encoder weights（mmproj）を使うか、その encoder を Metal GPU または CPU のどちらで実行するかを選びます。この文書は `metal/setup_mac.py` 独自 parser の scope です。Apple Silicon で `STRATA_CONTROL_INSTALL=1` を設定せず `setup.py` を実行したとき、この parser に委譲されます（`setup.py:7703-7707, 9068-9069`）。

## 使い方

リポジトリのルートで、たとえば次のように指定します。

```sh
./setup.sh --vision cpu --no-start
```

`--no-start` を付けても setup はモデルや encoder の準備と設定ファイル作成を行い、最後に server を起動しません（`metal/setup_mac.py:466-475, 542-570`）。

## 値と既定値

- `--vision yes`: 画像対応を有効にし、encoder を GPU で実行します。
- `--vision gpu`: `yes` と同じく画像対応を有効にして GPU を選びます。
- `--vision cpu`: 画像対応を有効にして CPU encoder を選び、CPU 利用について注意を表示します。
- `--vision no`: 画像対応を無効にします。
- 省略時は「画像も読み取るか」を質問し、既定回答は yes です。`--yes` も指定されている場合、質問は表示せず既定の yes を採用します（`metal/setup_mac.py:353-355, 404-410`; 質問処理は `setup.py:930-944`）。

値は `argparse` の `choices` によって上記4つに制限されます。引数なしや範囲外の値は parser が拒否し、usage とエラーを表示して終了します。`--vision` の後に値を付ける必要があります（`metal/setup_mac.py:328-356`）。

## 実行時の動作

値を受け取った後、`cpu` 以外は `vision_gpu=True` とされ、`no` だけが無効値に正規化されます。したがって `yes` と `gpu` は同じ GPU 経路、`cpu` は CPU 経路になります（`metal/setup_mac.py:404-410`）。

画像対応が有効なら、選択した family の mmproj をモデル保存先へダウンロードし、必要な場合はサイズと SHA-256 を照合します。その後、`strata-vision` が存在し同一ソース digest の build stamp があれば再利用し、そうでなければ `tools/vision` を Metal 有効でビルドします（`metal/setup_mac.py:159-189, 466-475`）。生成設定には engine 引数 `--vision` と encoder 実行ファイル、mmproj、モデルファイル、GPU/CPU の選択、`max_tokens: 1024` が記録されます（`metal/setup_mac.py:547-550`）。`no` の場合は mmproj の取得・encoder build・設定内の vision 項目を省きます。

例の `--no-start` がなければ、作成した設定を使って server 起動を試みます。起動時には設定で参照する engine/model ファイルの存在確認と、モデル準備中でないことの確認が行われます（`metal/setup_mac.py:302-323`）。

## 適用条件と副作用

- Apple Silicon の Metal setup 専用です。通常の `setup.py` parser（Control install 経路を含む）は別 parser で、そこでは `--vision` に `none` もありますが、この Mac 専用 parser では受理されません（`metal/setup_mac.py:353-355`; 通常 parser は `setup.py:9068-9091`）。
- 既存設定がある状態で `--vision` だけを付けて起動すると、parser は値を読み取りますが、既存設定を直ちに起動する早期経路に入り、新しい値は反映されません。再設定するには `--setup`（または `--model` / `--no-start` など setup に進む指定）が必要です（`metal/setup_mac.py:369-371`）。
- `--update` 経路では画像対応の設定確認に値が使われますが、update はモデルファイルを取得しません。画像対応を選んだのに mmproj が無い場合は警告して setup で追加する方法を案内し、そのまま終了します（`metal/setup_mac.py:435-448`）。
- `cpu` は CPU encoder の注意を表示します。画像対応を有効にした通常 setup はネットワークから mmproj を取得し、画像 encoder のビルドが必要なら build directory と `build-vision.log`、stamp を作成・更新します。また run config と起動 script も書き込みます（`metal/setup_mac.py:165-189, 466-475, 547-561`）。

## 出力とエラー

- `cpu` 指定時は `strata_control.vision_reader` の `MAC_CPU_NOTE` を警告表示します（`metal/setup_mac.py:406-408`）。
- encoder の build command が失敗すると、`S.fail` が `build-vision.log` を案内して setup を失敗させます（`metal/setup_mac.py:179-187`）。
- `--check` を指定すると Mac の問題有無を確認した時点で終了し、vision の選択処理には進みません（`metal/setup_mac.py:373-386`）。

## 根拠

- Parser、choices、parse の扱い: `metal/setup_mac.py:326-363`。
- 既定 prompt、値の正規化、CPU 注意表示: `metal/setup_mac.py:404-410`; `setup.py:930-944`。
- 既存設定起動と update 分岐: `metal/setup_mac.py:369-371, 435-448`。
- mmproj 取得、encoder build/reuse: `metal/setup_mac.py:159-189, 466-475`。
- config 生成と起動: `metal/setup_mac.py:542-570`; run config の原子的書き込み helper は `setup.py:6490-6496`。
- `setup.py` からの Mac 委譲: `setup.py:7703-7707, 9068-9069`。

調査範囲はこの checkout のソースです。実機でのビルド・ダウンロード・起動、各 Mac での CPU/GPU 性能は確認していません。
