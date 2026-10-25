# `--set`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--set KEY=VALUE` |
| 別名 | なし |
| 値 | エンジン引数または環境変数名と、その値を `=` でつないだ一組。複数回指定可 |

## 役割

`strata launch` がモデルを起動するときに使う、上級者向けのエンジン設定を追加・上書きします。キーが小文字のエンジンオプション形式なら run config の `args` を変更し、大文字を含む環境変数名形式なら `env` を変更します。

通常の `strata launch` オプションに専用の選択肢がないエンジン設定や環境変数を使いたい場合に利用します。どの設定が利用可能か、その設定の効果や条件は、Strata エンジンの対応状況を別途確認してください。

## 使い方

```sh
# エンジンの --prefill をこの起動だけ 65536 にする
strata launch --preset Office --set prefill=65536 --no-tui

# 環境変数 STRATA_PIN_BY_NEED をエンジンへ 1 として渡す
strata launch --preset Office --set STRATA_PIN_BY_NEED=1 --no-tui

# 複数の設定を指定する
strata launch --preset Office \
  --set prefill=65536 \
  --set STRATA_PIN_BY_NEED=1 \
  --no-tui
```

キーは `prefill=65536` のように書き、エンジン引数を表す先頭の `--` は省略できます。キー自体に `--` を含める場合は `--set=--prefill=65536` の形で渡します。設定ペアの中に空白がある値は、shell で `--set 'key=value with spaces'` のように全体を引用符で囲みます。

## キーと値の解釈

### キー

- **エンジン引数:** `prefill=65536`、`--prefill=65536`、`no-pool=on`。小文字で始まるキーは `--` が付いていてもいなくてもエンジンフラグとして扱われます。キー中の `_` は `-` に正規化されます。例: `--pool_cores=2-14:2` は `--pool-cores` になります。
- **環境変数:** `STRATA_PIN_BY_NEED=1`、`IGC_EnableDPEmulation=1`。ASCII 大文字を少なくとも一つ含む環境変数名形式のキーは、その名前のまま環境変数として扱われます。`STRATA_` 接頭辞に限定されません。
- `=` が最初の区切りです。値の中にさらに `=` があれば値の一部として保持されます。キーと値の前後の空白は取り除かれます。
- エンジン引数キーは、先頭が小文字英字で、残りが小文字英字・数字・ハイフンである必要があります。環境変数キーは英字または `_` で始まり、続きに英数字または `_` を使えます。
- `--set` の値自体を省略すると argparse のエラーになります。`KEY` または `KEY=` のようにペア内の `=` と値を省略・空にする形は受理されますが、適用方法は以下の通りキー種別で異なります。

### 値による制御と空値

`--set` では一部の文字列を設定の削除やフラグの切り替えに使います。これらの文字列は大文字・小文字を区別しません。

| キーの種類 | 値 | 結果 |
| --- | --- | --- |
| Boolean エンジンフラグ | 値なし、空値、`on` / `true` / `yes` | フラグを引数に追加 |
| Boolean エンジンフラグ | `off` / `false` / `no` / `none` | フラグを引数から削除 |
| 値を取るエンジンオプション | `off` / `false` / `no` / `none` | そのオプションを引数から削除 |
| 値を取るエンジンオプション | 空値 | 変更しない |
| 環境変数 | `off` / `unset` / `none` | run config から環境変数を削除 |
| 環境変数 | 空値 | 値が空文字列の環境変数を設定 |
| 環境変数 | その他の文字列 | その文字列を環境変数の値に設定 |

「Boolean エンジンフラグ」は Terminal が値なしのフラグとして認識するオプションです。たとえば `--set no-pool=on` は `--no-pool` を追加し、`--set no-pool=off` は削除します。値を取るオプションで空値を指定した場合、空の値を渡すのではなく変更しません。値を取るオプションに `on` / `true` / `yes` を指定すると bare flag として渡されるため、その使い方は避けてください。

`off` などの予約語自体は通常値として渡せません。特に環境変数の値として実際の文字列 `off`、`unset`、`none` を渡したくても、このオプションでは削除を意味します。

## 優先順位と保存範囲

- `--preset NAME` と併用すると、preset の `extra` 設定を読み込んでから `--set` の値を重ねます。同じ正規化後のキーを複数回指定した場合は、コマンドラインで最後に指定した値が残ります。別表記のキーが正規化後に同じキーになる場合も一つにまとめられます。
- `--preset` と併用した `--set` の変更は、通常この起動だけに適用されます。次回以降も使うには `--save-preset NAME` を指定します。`--save-preset` は値を preset JSON の `extra` 項目に保存します。保存先は既定で profiles フォルダーの隣にある `launch-presets/` で、`STRATA_LAUNCH_PRESET_DIR` で変更できます。
- 起動時、Terminal はインストール済み run config を元に、その launch 専用の設定を作ります。`--set` のエンジンフラグは `args` に、環境変数は `env` に反映されます。setup が作成した元のモデル run config は変更しません。
- 同じ機能に関わるエンジンフラグと環境変数を両方指定した場合の優先順位は、各設定の実装に従います。関連するオプション文書と環境変数文書を確認してください。

## 無効な設定・未対応の設定

空のキーや無効なキー形式は設定構築時に拒否されます。`--set` 自体の値を省略した場合も拒否されます。前者は `ValueError` として終了コード `2` で返ります。

`--set` は、構文上正しいエンジンフラグが選択中のエンジンに実装されているかを、コマンドライン処理で常に事前検証するわけではありません。Terminal の Advanced 画面では、エンジンの help にないフラグに警告を表示し、入力値を保持します。古いエンジンなどがそのフラグを受け付けず、起動に失敗する場合があります。キーの綴り、エンジンのバージョン、backend を確認してください。

## 根拠

- `strata_cli/launch/cmd.py:16-29,75-115` — `strata launch` の使用例、`--set` の反復指定と help 説明。
- `strata_cli/launch/cmd.py:270-272` — 保存済み `extra` にコマンドラインの `--set` を重ねる処理。
- `strata_cli/launch/settings.py:77-105,120-128` — preset に保存される `LaunchSettings.extra`。
- `strata_cli/launch/settings.py:223-269` — キーの構文、`_` の正規化、値の変換、フラグと環境変数それぞれの扱い。
- `strata_cli/launch/runner.py:371-407,1235-1243` — `args` / `env` への適用と launch 専用 run config の生成。
- `strata_cli/launch/runner.py:1246-1263` — launch の選択内容から shared profile を用意する処理（`--set` の preset 保存とは別の経路）。
- `strata_cli/launch/store.py:1-7,27-36,75-85` — preset の保存先と `extra` を含む保存処理。
- `strata_cli/launch/params.py:162-201` — Advanced 画面で未登録エンジンフラグを表示・警告する処理。
- `docs/TERMINAL_LAUNCH.md:57-75` — コマンドライン例と、`--preset` に続くオプションが通常その起動にのみ適用される説明。

