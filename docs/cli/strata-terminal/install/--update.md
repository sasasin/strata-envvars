# `strata install --update`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata install` |
| オプション | `--update` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`strata install` が委譲する `setup.py` に更新モードを選ばせます。通常の `strata install` は `setup.py --setup` を起動しますが、このフラグを付けると `setup.py --update` を起動し、既存インストールの Python パッケージ、必要なエンジン、モデル設定と draft subset を更新します。モデル自体はダウンロードせず、起動もしません（`terminal/strata_cli/cli.py:2139-2157`; `terminal/setup.py:8497-8518`）。

## 使い方

```sh
# Strata checkout の terminal/ で、既存インストールを更新する
strata install --update

# setup.py の更新モードへビルド指定も渡す
strata install --update --build
```

`--build` など setup.py 側の引数は `strata install` の後ろに続けます。Terminal CLI は `--update` を自身の引数として取り除き、残りを `setup.py` に渡します（`terminal/strata_cli/cli.py:2299-2311,2149-2157`）。

## 値と既定値

`--update` は `argparse` の `store_true` フラグであり、値を受け取りません。指定しない場合は `False` となり、`strata install` は `setup.py --setup` を実行します。別名や追加の値検証は定義されていません（`terminal/strata_cli/cli.py:218-224,2149-2157`）。

install 引数の前処理は、`strata install` の後ろにある引数列から最初の `--update` を探して Terminal CLI 側で処理し、残りを `--` の後ろに置きます。そのため setup.py 側の引数と値は Terminal CLI の parser で先に解釈されません。setup.py が受け取った `--update` はその parser でも `store_true` です（`terminal/strata_cli/cli.py:2299-2311`; `terminal/setup.py:11524-11535`）。

## 実行時の動作

1. Terminal CLI は `STRATA_INSTALL_DIR` が設定されていればそのフォルダー、そうでなければ CLI 自身の `ROOT` にある `setup.py` を選びます。ファイルがなければ「full Strata folder から実行するか、`STRATA_INSTALL_DIR` を設定する」旨を stderr に出して終了コード 5 を返します（`terminal/strata_cli/cli.py:2139-2148`）。
2. `setup.py` に `--update` と残りの setup 引数を渡し、その親フォルダーを作業ディレクトリとして起動します。バンドル版 Terminal（`ROOT/python` と `ROOT/VERSION` がある場合）は `STRATA_CONTROL_INSTALL=1` を設定し、`STRATA_INSTALL_DIR` がなければ `install_root()` を設定します。子プロセスの終了コードは `subprocess.call` の結果として返されます（`terminal/strata_cli/cli.py:2149-2157`）。
3. setup.py は既存モデル設定の一覧を得たうえで更新分岐に入り、通常のモデル起動・新規セットアップ分岐へ進みません。対象モデル設定がなければ案内を表示してコード 0 で終了します（`terminal/setup.py:11676-11697`; `terminal/setup.py:8497-8507`）。
4. 更新処理は runtime Python packages を導入し、既存エンジンを条件に応じて更新または再ビルドし、各設定を upgrade し、共有 draft vocabulary を更新します。Windows の HIP 設定では HIP runtime もエンジン実行ファイルの隣に配置します（`terminal/setup.py:8497-8518`; `terminal/setup.py:6452-6551`）。

## 適用条件と副作用

- 通常の Git checkout では、更新処理の前に `update_pull()` が最新コードを取得しようとします。git がない場合、detached HEAD の場合、または pull 後の再試行でも更新できない場合はコード 1 で終了します。新しいコミットを取得すると、新しい `setup.py` を `STRATA_UPDATE_PULLED=1` 付きで再実行します（`terminal/setup.py:8386-8423`）。
- `STRATA_UPDATE_PULLED=1` が既に設定されている場合、および Terminal Control install mode では、この setup.py の git pull はスキップされます（`terminal/setup.py:8391-8393`; `terminal/strata_cli/cli.py:2151-2156`）。
- 対象モデルが実行中でエンジンを置き換えられない場合、エンジン更新は警告して既存エンジンを保ちます。ダウンロードやビルドが失敗した場合も、対象処理では警告して既存エンジンを使い続けます。`--update --build` は通常の更新判定にかかわらずエンジンの再ビルドを要求します（`terminal/setup.py:6452-6458,6517-6550`; `terminal/setup.py:8510`）。
- モデルファイルは更新処理の対象外と明記されています。実際のファイル置換範囲や、pip が環境上で変更する全ファイルはこのオプションだけのソースからは限定できません（`terminal/setup.py:8497-8502,8508-8518`）。
- 同じ文字列 `--update` は `source-setup` の root / macOS 用文書にもありますが、別のツール・コマンド階層です。この文書は `strata-terminal` の `strata install` に限定しています（`docs/cli/README.md:383-386`）。

## 出力とエラー

setup.py が既存モデルを持たない場合は、その旨と通常の setup を案内してコード 0 で終了します。git が見つからない、HEAD が detached、または pull の履歴衝突を解決できない場合は更新を中断しコード 1 になります。エンジンの使用中・取得失敗・ビルド失敗は警告を表示して既存エンジンを保つ経路があり、設定処理の最後は成功またはエンジンが未更新である旨を表示します（`terminal/setup.py:8391-8423,8497-8529`; `terminal/setup.py:6517-6550`）。Terminal CLI 自身で `setup.py` が見つからない場合の stderr と終了コード 5 は別の失敗経路です（`terminal/strata_cli/cli.py:2143-2148`）。

## 根拠

- `terminal/strata_cli/cli.py:218-224` — `strata install` の parser、`--update` の型、setup 引数の委譲範囲。
- `terminal/strata_cli/cli.py:2299-2311` — install 引数を前処理し、`--update` を Terminal CLI 側で保持する処理。
- `terminal/strata_cli/cli.py:2139-2157` — installer 探索、バンドル版の環境設定、setup.py 呼び出しと戻り値。
- `terminal/setup.py:11524-11535,11606-11613,11676-11698` — setup.py parser、update pull の呼び出し、更新分岐。
- `terminal/setup.py:8386-8423` — Git checkout の pull、停止条件、新しい setup.py の再実行。
- `terminal/setup.py:8497-8529,6452-6551` — 更新対象、モデル不変更、エンジン更新・失敗時の既存エンジン維持。
- `docs/cli/README.md:383-386` — `strata install` 配下の option scope と予定リンク。
