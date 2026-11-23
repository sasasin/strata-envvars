# `setup.py --update`（Mac / Apple Silicon）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`terminal/setup.py` から委譲） |
| オプション | `--update` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

ソース checkout の Mac 用セットアップで Metal エンジンを現在のソースに合わせて用意し、選択したモデルとその準備済みファイルがローカルにあるか確認して終了します。エンジンが現在の checkout からビルド済みなら再利用し、モデルファイルが欠けている場合も取得せず警告します。この経路はサーバーを起動しません。通常のモデル取得や設定生成にも進みませんが、開始時のデータフォルダー処理は既存ファイルを移動し、run config のパスを付け替えることがあります。

## 使い方

Mac（Apple Silicon）の Strata checkout のルートで、推奨回答を使って実行します。

```sh
./setup.sh --update --yes
```

特定モデルを確認したい場合は `--model` を指定できます。モデル名は現行 parser の選択肢から選びます。

```sh
./setup.sh --update --model IQ3_S --yes
```

## 値と既定値

`engine/metal/setup_mac.py` は `--update` を `action="store_true"` で登録しています（同ファイル:398行）。引数値は不要で、指定がなければ `False`、指定すれば `True` です。短縮別名や値域はありません。同じフラグを重ねても真偽値として扱われます。`--update=value` のように値を付ける書式はこの登録と合わず、argparse の引数エラーになります。

モデルを省略すると、通常は選択メニューが表示されます。`--yes` がある場合、質問への回答は既定値になり、モデル選択では推奨モデルが使われます（`engine/metal/setup_mac.py`:439–448、`terminal/setup.py`:1077–1092）。

## 実行時の動作

POSIX の `setup.sh` は `terminal/setup.py` を起動し（`setup.sh`:6–17）、macOS では `terminal/setup.py` が通常 parser の実行前に `metal/setup_mac.py` へ引数を渡します（`terminal/setup.py`:11218–11219、9205–9210）。したがって、Mac での `--update` は `setup_mac.py` の parser と処理に適用されます。

委譲先は引数を parse した後、モデル選択より前に `S.data_folder_for(a)` を呼びます（`engine/metal/setup_mac.py`:403–418）。これは `terminal/setup.py` のデータフォルダー処理を通し、既定の場所や `--data-dir`、`--move-data`、`--set-default-data-dir` に応じて既存のモデルファイルを移動し、設定を保存したり run config のパスを付け替えたりします（`terminal/setup.py`:7335–7426）。さらに、モデル・family が明示されず対話選択に入る条件では、parser より前に署名 feed のモデル一覧を読み込みます。acquisition が許可されていれば feed を取得し、取得できない場合は最後に検証済みの一覧を使います（`engine/metal/setup_mac.py`:361–374、`terminal/setup.py`:9593–9608）。

Mac スクリプトはその後 Mac 情報と問題点を確認します。`--check` も同時に指定すると、この確認の結果を 0 または 1 で返して終了し、モデル選択やエンジンのビルドには進みません（`engine/metal/setup_mac.py`:420–432）。通常の `--update` はモデルと画像対応の選択を経て Python パッケージを確認・必要ならインストールし、Metal エンジンを準備します（同ファイル:434–478）。エンジンは `engine/build-metal/BUILD.json` に記録されたソース version・digest と実行ファイルを確認し、一致すれば再利用します（同ファイル:46–47、109–115、129–153）。

エンジン準備後は、選択モデルの shard が存在し `.done` 完了マークを持つこと、および pack の `native_experts.txt` と `tokenizer/vocab.json` が存在することを確認します（`engine/metal/setup_mac.py`:482–489、`terminal/setup.py`:1281–1294）。確認できなければ「モデルファイルは update ではダウンロードしない」と警告し、`./setup.sh --setup` を案内します。画像対応が選ばれていて画像 encoder がなければ、こちらもダウンロードしない旨を警告します。どちらの欠落警告の経路でも、コマンドは 0 を返します（`engine/metal/setup_mac.py`:489–495）。

## 相互作用・適用条件・副作用

- `--build` を併用すると `BUILD.json` を削除してからエンジン準備に進むため、現在の engine stamp が一致していても再ビルドします（`engine/metal/setup_mac.py`:479–481）。通常の `--update` でもエンジン準備関数は呼ばれますが、stamp が現在のソースと一致する場合は既存 engine を再利用します（同ファイル:109–115、481）。
- `--model`、`--vision`、`--gguf-dir`、`--models-dir` などは確認対象やファイル位置に影響します。ただし `--update` 分岐はモデル取得・pack 処理へ進む前に終了するため、欠けたモデルを補完しません（同ファイル:379–403、482–495）。一方、データフォルダー処理による既存モデルの移動や config のパス更新はこの分岐より前に実行されます（同ファイル:412–414、`terminal/setup.py`:7335–7426）。
- `--setup` を併用しても、エンジン準備後に `a.update` の分岐で戻るため、通常のモデル download / prepare / server start には進みません（同ファイル:482–497）。
- この処理は macOS の委譲経路に適用されます。`setup_mac.py` 自身は Apple Silicon / Metal 用と記載され、Mac の検査に失敗すれば `S.fail` により停止します（同ファイル:1–15、420–432）。
- `--update` は `terminal/setup.py` の通常経路にある `update_pull()` を通りません。Mac の委譲判定は通常 parser と `update_pull()` の呼び出しより前です（`terminal/setup.py`:11218–11219、11385–11392）。そのため、この Mac 経路自体は Git pull をしません。また、モデル取得や選択内容に基づく run config の再生成には進みません。ただし、先述のデータフォルダー処理は既存データを移動したり config のパスを付け替えたりできます。利用者向け `docs/SOURCE_INSTALL.md`:154–156 は Git checkout の更新でソースを pull できると一般的に説明していますが、ここで確認した Mac 委譲経路の実装とは一致しません。
- ネットワーク・ファイル副作用として、条件により署名 feed のモデル一覧を取得し、必要なら Python 依存パッケージをインストールし、Metal の build 用ヘッダー未配置時には pinned archive をダウンロードします（`engine/metal/setup_mac.py`:361–374、85–99、471–481、`terminal/setup.py`:4307–4329、9593–9608）。これはモデル shard の download とは別です。

## 出力とエラー

通常の `say` / `warn` 出力は stdout に表示されます（`terminal/setup.py`:997–1004、1039–1056）。Mac の事前検査で問題があれば setup は停止し、エンジンの build が失敗した場合は `build.log` の場所を示して終了します（`engine/metal/setup_mac.py`:420–432、143–149）。引数の未知部分は argparse で拒否せず `not used on a Mac:` と警告します（同ファイル:403–405）。選択肢外の既知値は argparse により引数エラーになります（同ファイル:376–403）。

## 根拠

- `engine/metal/setup_mac.py:372–405` — Mac parser、`--update` の型、未知引数の警告。
- `terminal/setup.py:11218–11219, 9205–9210` — Apple Silicon の Mac 経路が `setup_mac.py` へ委譲する箇所。
- `engine/metal/setup_mac.py:420–432, 434–478` — Mac 検査、質問・選択、依存確認、エンジン準備への流れ。
- `engine/metal/setup_mac.py:361–374` と `terminal/setup.py:9593–9608` — 条件付きの feed モデル一覧読み込みと取得・cache fallback。
- `engine/metal/setup_mac.py:412–414` と `terminal/setup.py:7335–7426` — update 判定前のデータフォルダー処理と、既存モデル・run config・設定への影響。
- `engine/metal/setup_mac.py:46–47, 109–153, 479–495` — engine stamp の再利用、`--build` による再ビルド、モデル・画像 encoder の存在確認と update 時の早期終了。
- `terminal/setup.py:1281–1294, 4307–4329` — `.done` 完了マークと依存パッケージ導入の判定。
- `terminal/setup.py:11385–11392` — 通常経路の `update_pull()`。Mac 委譲がその前に行われる根拠は `11218–11219`。
- 利用者向け資料との照合: `docs/SOURCE_INSTALL.md:154–156` は Git checkout の更新時に pull 可能と説明するが、Mac の現行 parser 経路では `update_pull()` を呼びません。現行動作の記述は上記ソースに基づきます。

調査時点では指定 checkout の `git status --short --branch` は `## main...origin/main`（変更表示なし）でした。
