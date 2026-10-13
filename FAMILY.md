# `FAMILY`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Strata の Docker 起動スクリプトが、どのモデル系列を setup に渡すか、および起動時にどの系列名の設定ファイルを選ぶかを決めます。C++ エンジンや `setup.py` が環境変数 `FAMILY` を直接読むのではなく、`docker-entrypoint.sh` が読み、必要なら `setup.py --family <値>` の引数にします。Docker 起動以外で `FAMILY` を設定しても、この環境変数自体を読む処理はありません（`docker-entrypoint.sh:19-20,37-43,76-78`; `Dockerfile:25-28`）。

## 値と判定

シェルの `${FAMILY:-qwen}` を使うため、未設定または空文字なら `qwen` になります。空白除去、大小文字変換、値の事前検証はありません。`qwen` だけは系列接頭辞を空にし、それ以外は値に `-` を付けて接頭辞にします。設定ファイル名に使うモデル名は別途小文字化されますが、系列名はそのままです（`docker-entrypoint.sh:19-21,41-43`）。

| 環境変数の値 | entrypoint の系列接頭辞 | setup 時の扱い |
|---|---|---|
| 未設定または空文字 | 空（既定値 `qwen`） | `--family qwen` |
| `qwen` | 空 | `--family qwen` |
| `swift`, `coder`, `unsloth` | それぞれ `swift-`, `coder-`, `unsloth-` | setup が受理 |
| その他（例: `QWEN`, `unknown`） | 値をそのまま使った `<値>-` | setup の `--family` 選択肢にない値なら、setup 実行時に argparse が拒否 |

`setup.py` の現行選択肢は `FAMILIES` のキー `qwen`, `swift`, `coder`, `unsloth` です。モデルごとに利用可能な系列も制限されます。たとえば `Q2_0` は `qwen`、`IQ1_M` は `coder`、Unsloth のモデルは `unsloth` に属します。系列とモデルが合わなければ `setup.py` はその組み合わせをエラーにします（`setup.py:201-229,266-300,4827-4830,5230-5243`）。

## 有効になる条件

- この環境変数の読み取りは Docker イメージの `docker-entrypoint.sh` に限られます。entrypoint は毎回 `FAMILY` と `MODEL` から `/data/config/strata-<系列付きモデル名>.json` のパスを組み立てます。`qwen` では系列接頭辞を付けず、ほかでは系列名を付けます（`docker-entrypoint.sh:37-44`）。
- `CONFIG` が空で、対象設定がまだない場合、または `REINSTALL=1` の場合には setup を実行し、`FAMILY` を `--family` に渡します。setup でモデル選択に進む際、系列に属さない `MODEL` はエラーになります（`docker-entrypoint.sh:65-88`; `setup.py:4829-4830,5230-5243`）。
- すでに対象設定がある場合は setup を省略し、その設定を選択して起動します。この経路では `FAMILY` の値が setup の選択肢かどうかを検証しませんが、値と一致する設定ファイル名が必要です（`docker-entrypoint.sh:55-63,70-93`）。
- `CONFIG` が空でない場合は、そのファイルが存在することを確認して系列・モデルの既定設定へのリンク先を `CONFIG` にします。したがって設定内容の選択は `CONFIG` が優先します。`FAMILY` はリンク名を組み立てる値としては引き続き使われます（`docker-entrypoint.sh:35,55-68`）。

## 実行時の詳細

entrypoint 起動時に一度だけシェル変数へ展開されます。該当モデルの設定がなく setup が必要なら、`--family "$FAMILY"` として setup に渡され、選択された系列のモデルファイルや pack、設定が作られます。設定作成後は系列接頭辞付き（`qwen` は接頭辞なし）の設定名を `/data/config` に保存し、その設定を指すリンクを `/opt/strata` に作って `setup.py` を起動します（`docker-entrypoint.sh:37-44,65-93,96-106`; `setup.py:5230-5243,5301-5303`）。

通常の再起動では既存の `/data/config` 内の設定を使い、setup を省略します。別系列へ切り替えると、系列接頭辞が異なる設定ファイルが選ばれます。Docker 以外の起動経路、プロセス稼働中の環境変更、Strata エンジンへの環境変数継承について、この変数を使う実装は確認できません。

## 文書との照合

`docs/INSTALL.md` は Docker の setup 環境変数として `FAMILY` を挙げ、`qwen` を既定の例、`swift` / `coder` を選択例として説明しています。また後段で Unsloth の例に `FAMILY=unsloth` を使っています。記述は entrypoint と整合しますが、列挙は分かれており、現在の全選択肢は `setup.py` の `FAMILIES` 定義が根拠です（`docs/INSTALL.md:103-104,129-134`; `setup.py:266-300`）。

## 根拠

- 環境変数の既定値、系列名から接頭辞への変換、モデル名の小文字化、設定パス: `docker-entrypoint.sh:19-21,37-44`
- `CONFIG`・既存設定・`REINSTALL` による setup の選択と `--family` の引き渡し: `docker-entrypoint.sh:35,55-88`
- setup が受理する系列と系列・モデルの適合確認: `setup.py:201-229,266-300,4827-4830,5230-5243`
- Docker 利用者向け説明: `docs/INSTALL.md:103-117,129-134`
