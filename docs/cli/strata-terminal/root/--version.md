# `--version`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata`（トップレベル） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない（`nargs=0`） |

## 役割

Terminal CLI の製品バージョン、ビルド番号、実行中の Python バージョンと interpreter のパスを1行で表示して終了します。製品バージョンとビルド番号は別の値です。製品バージョンは `strata_cli.PRODUCT_VERSION`、ビルド番号は `strata_cli.version()` から取得します（`strata_cli/cli.py:30-37`、`strata_cli/__init__.py:8-29`）。

## 使い方

```sh
strata --version
```

ソース checkout からは `python strata.py --version` でも実行できます（`strata.py:1-4,30-43`）。トップレベル parser に置かれたオプションなので、サブコマンド名より前に指定します。例の出力形式は次のとおりです。

```text
strata <製品バージョン> (build <ビルド番号>; python <Pythonバージョン> at <interpreterのパス>)
```

## 値と既定値

値は不要です。parser は `nargs=0` で宣言され、オプションが処理されると独自 action が出力して `parser.exit()` を呼ぶため、サブコマンドを必須とする通常の parser 検証やコマンド処理へ進みません（`strata_cli/cli.py:30-45`）。このため `strata --version serve` も `--version` の処理時点で終了し、後続の `serve` は実行されません。製品バージョンは `PRODUCT_VERSION` 定数で、この revision では `0.2.4.2` です（`strata_cli/__init__.py:8-10`）。

ビルド番号はまず Terminal のルートにある `VERSION` ファイルを UTF-8 で読み、空白を除いた内容を使います。読み込みに失敗するか内容が空なら `CMakeLists.txt` の `project(... VERSION 数字...)` を検索し、見つからなければ `unknown` を返します（`strata_cli/__init__.py:13-29`）。この checkout には `VERSION` ファイルがなく、`CMakeLists.txt:11` の project version は `0.1.49.2` です。

## 実行時の動作

出力行には `sys.version.split()[0]` の先頭要素と `sys.executable` を含めます。標準出力へ改行付きで書き込み、argparse の `exit()` により通常は終了コード 0 で終了します（`strata_cli/cli.py:30-37`）。この action 自体は設定変更、ファイル生成、ネットワーク通信、サーバー起動を行いません。ビルド番号取得時には `VERSION` または `CMakeLists.txt` を読むだけです（`strata_cli/__init__.py:13-29`）。

`strata.py` 経由の場合、CLI parser より前に互換性用の旧 updater 判定と installed Control への handover 判定が実行されます（`strata.py:30-43`）。通常の source checkout では `.git` があるため handover を行いません（`strata_cli/handover.py:27-30,126-134`）。インストール済み Terminal では、より新しく完全な Control が有効なら同じ引数をその Control の interpreter と `strata.py` に渡して実行します。handover は `STRATA_HANDOVER` または `STRATA_NO_HANDOVER` が設定されている場合は無効です（`strata_cli/handover.py:8-10,126-159`）。

## 適用条件と副作用

このオプションは Terminal CLI のトップレベルに属します。`strata --version` の形で使います。サブコマンド parser に `--version` は追加されていないため、`strata serve --version` のようにサブコマンド後に置いた場合は、そのコマンドの未知引数として扱われます（トップレベル定義: `strata_cli/cli.py:40-45`; `main()` の引数処理: `strata_cli/cli.py:2217-2231`）。

例外的に、staging 中の新 Control を古い updater が試験起動した場合、引数が正確に `--version` で、`STRATA_NO_ACQUIRE=1` かつ `STRATA_HANDOVER` 未設定などの条件がそろうと、通常の版情報ではなく更新案内を stdout に出して終了コード 7 を返します（`strata_cli/handover.py:166-187`; 呼び出し位置: `strata.py:30-38`）。

## 出力とエラー

通常経路では stdout に1行を出力します。parser が余分な引数を返した場合、`main()` は argparse の `error()` に渡し、usage とエラーを表示して終了コード 2 にします（`strata_cli/cli.py:2223-2231`）。ただし `--version` action 自体が直ちに終了するため、その後ろの引数はこの検査に届きません。ビルド番号の両方の取得元が読めない場合はエラーにせず `build unknown` と表示します（`strata_cli/__init__.py:13-29`）。

handover 先の起動に失敗した場合は stderr に警告を出し、現在の Terminal で処理を続けます。Windows の handover 先実行では、その子プロセスの終了コードが返されます（`strata_cli/handover.py:142-162`）。

## 根拠

- `strata_cli/cli.py:30-45` — 出力 action とトップレベル parser 定義。
- `strata_cli/cli.py:2217-2231` — parser の呼び出し、余分な引数のエラー処理。
- `strata_cli/__init__.py:8-29` — 製品版定数とビルド番号の読み取り・fallback。
- `strata.py:30-43` — CLI 起動前の updater 判定、handover、preflight。
- `strata_cli/handover.py:27-30,126-162,166-187` — checkout 判定、Control handover、旧 updater の特例。
- `CMakeLists.txt:11` — source fallback に使われる project version。
