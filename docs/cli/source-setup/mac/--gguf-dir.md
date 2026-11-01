# `--gguf-dir`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査対象 checkout は `main...origin/main` で clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `setup.py` 委譲先 `metal/setup_mac.py` |
| オプション | `--gguf-dir` |
| 別名 | なし |
| 値 | GGUF shard を置くディレクトリのパス（文字列） |

## 役割

macOS 用 setup で選んだモデルの GGUF shard を置くディレクトリを指定します。省略時は `--models-dir` があればその下のモデル用ディレクトリ、なければデータディレクトリ内の `models/<モデルタグ>` が使われます。macOS の委譲先に固有の説明です。索引上の `source-setup/root/--gguf-dir.md` は別 parser scope です。

## 使い方

Strata checkout のルートで、既存 shard があるディレクトリを指定し、setup 経路を明示します。モデル選択は対話式です。

```sh
./setup.sh --setup --gguf-dir /Volumes/models/qwen
```

`setup.sh` から渡された引数は `setup.py` が macOS で `metal/setup_mac.py` に委譲します。既に setup 済みの構成がある場合、`--gguf-dir` だけでは通常の再設定経路に入らず既存モデルを起動するため、モデルのセットアップ時は `--setup` などの setup 経路を選ぶ必要があります。

## 値と既定値

- parser は値を1つ受け取りますが、型変換・存在確認・ディレクトリ検証はしません。引数を省略した場合は `None` です。空文字列は後続処理で偽として扱われ、指定なしと同じ保存先になります。
- 実際に使うファイル名は選択したモデルから決まり、指定ディレクトリ直下に配置される想定です。モデル別の shard 名・個数を組み立てます。任意の名前を走査して自動採用する実装ではありません。
- `--update` の場合も指定ディレクトリ配下の固定 shard 名を確認します。shard と `.done` marker、準備済み pack が揃わなければモデルファイルをダウンロードせず、「nothing was installed」と案内して終了します。

## 実行時の動作

通常の setup 経路では、指定ディレクトリを `Path` に変換し、存在しなければ作成します。モデルから固定 shard 名の一覧を作り、各 shard についてファイルと隣接 `.done` marker の両方がある場合だけ取得済みとしてスキップします。それ以外は選択モデルの配布 URL から同名ファイルをダウンロードします。その後 GGUF shard の構造・tensor 範囲を検査し、対応する Unsloth shard には pinned size/SHA-256 の検査も実行します。

この macOS 経路の Unsloth 検証呼び出しは `own=True` を指定しません。したがって、hash が一致しない場合にローカルファイルをユーザー所有物として保護する root setup の分岐は適用されず、検証 helper は対象ファイルと marker を削除して setup を停止する場合があります。指定先が共有・読み取り専用であれば、`.done` marker を書けず次回に同じ処理を繰り返すこともあります。

## 適用条件と副作用

- この parser は `setup.py` が `sys.platform == "darwin"` かつ Control mode でないときに使われます。`setup_mac.py` は `parse_known_args` を使い、認識しない余分な引数は `not used on a Mac: ...` と警告して継続します。
- 既存の設定が見つかり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていないと、早期に既存構成を起動します。この判定には `--gguf-dir` 自体は含まれません。
- `--gguf-dir` があっても、選択したモデルの期待 shard 名・個数と異なる命名のファイルを自動検出しません。期待ファイルが marker なしで存在する場合、ダウンロード経路に入り、既存ファイルが完成サイズとみなされないときはダウンロード完了後に同名 destination が置き換えられます。
- セットアップは GGUF 以外にも pack、設定ファイル、start script などをデータ領域へ作成します。画像対応が有効なら encoder ファイルも通常の `models_root` に置かれ、`--gguf-dir` 配下には置かれません。

## 出力とエラー

- shard が検査を通れば `[ok] model files present` を表示して続行します。欠落 shard や不完全な GGUF は `setup.py` の `check_shards()` から `fail()` に渡り、エラーと修正案を表示して終了コード 1 で停止します。
- Unsloth shard の pinned size/hash 不一致も検証 helper のエラー経路で停止します。上記のとおり macOS 呼び出しは `own=False` 相当のため、hash 不一致時にはファイルと `.done` marker が削除され得ます。
- parser に値を渡さない場合は argparse の引数エラーになります。存在しないパスや書き込み不可パスでの具体的な例外表示・終了コードは、実行環境に依存し、この調査では実行して確認していません。

## 根拠

- parser 定義と未知引数の警告: `metal/setup_mac.py:332-358`。
- `setup.py` から macOS parser への委譲条件: `setup.py:9062-9069`。委譲関数: `setup.py:7703-7707`。
- 保存先、起動への早期分岐、空値を含む判定: `metal/setup_mac.py:365-371`、`metal/setup_mac.py:452-460`。
- モデル選択と固定 shard 名: `metal/setup_mac.py:66-73`、`metal/setup_mac.py:392-401`。
- 更新時の確認と非取得時の終了: `metal/setup_mac.py:435-448`。
- marker の意味と書き込み失敗時の警告: `setup.py:1007-1018`。
- ダウンロードのスキップ条件、destination 作成・置換: `setup.py:3008-3015`、`setup.py:3073-3100`。
- shard 構造検証と失敗処理: `setup.py:904-909`、`setup.py:3434-3461`。
- Unsloth 検証呼び出しと mismatch 時の削除: `metal/setup_mac.py:460-464`、`setup.py:3217-3263`。
- `--gguf-dir` 使用時の必要ディスク量への反映: `metal/setup_mac.py:418-422`。
