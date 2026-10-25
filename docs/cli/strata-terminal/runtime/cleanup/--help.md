# `strata runtime cleanup --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime cleanup` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。ヘルプ表示用のフラグ |

## 役割

`strata runtime cleanup` の使用法と、その parser に登録されたオプションを表示します。`strata_cli/cli.py` は `argparse.ArgumentParser` を使い、`cleanup` の parser を作成しています。`--help` と `-h` は明示的な個別宣言ではなく、`argparse` が各 parser に標準で追加するヘルプ action です（`strata_cli/cli.py:40-46,197-203,233-237`）。

## 使い方

ソース checkout のルートで実行する例です。

```sh
python strata.py runtime cleanup --help
```

短縮形も使えます。

```sh
python strata.py runtime cleanup -h
```

## 値と既定値

値は取りません。`--help` と `-h` は同じ parser action です。cleanup parser には `--profile`（任意）と `--output human|json`（既定値 `human`）が定義され、共通の one-shot option として `--json` と `--quiet` も登録されます。これらはヘルプに表示されるコマンド範囲を示すもので、`--help` 自体の値や動作を変更しません（`strata_cli/cli.py:233-237,508-515`）。

## 実行時の動作

ヘルプ action は使用法とオプション説明を標準出力へ表示して終了します。cleanup の処理関数 `runtime.cleanup()` は `_runtime()` から呼ばれますが、これは通常の実行経路であり、ヘルプ表示時には parser が終了するため呼ばれません（`strata_cli/cli.py:1331-1345,2217-2237`）。したがって、ヘルプ表示によって残存プロセスを停止したり、runtime cleanup の結果 JSON を出力したりはしません。

## 適用条件と副作用

`--help` は `strata runtime cleanup` の parser に適用されます。Strata のトップレベル `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows で現在のプロセスの既定 owner と DACL の設定を試み、Windows 以外では何もしません。従って、Windows ではヘルプ表示だけの場合もこのプロセス設定処理が先に実行されます。cleanup 対象のプロセス探索・終了や、cleanup の状態ファイル回復処理は行いません（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-390`、`strata_control/runtime.py:670-684`）。

## 出力とエラー

正常なヘルプ表示は stdout に出力され、`argparse` のヘルプ action により終了コード `0` で終了します。ヘルプ action が実行されず、必須サブコマンド不足や認識できない引数で parser error になった場合は usage/error が表示されて終了コード `2` になります。未認識引数は `main()` が `ap.error()` に渡し、必須サブコマンドの検査は `argparse` の subparser が行います（`strata_cli/cli.py:41-46,197-203,2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-46` — トップレベル parser と argparse のサブコマンド設定。
- `strata_cli/cli.py:197-203,233-237` — runtime 階層と cleanup parser、および cleanup 固有引数。
- `strata_cli/cli.py:508-515` — `--json` と `--quiet` を cleanup を含む one-shot parser に追加。
- `strata_cli/cli.py:1331-1345,2217-2237` — cleanup 実行経路と、引数解析後の分岐。
- `strata_control/private_files.py:349-390` — CLI 起動時に呼ぶ Windows 既定 owner/DACL 設定処理。
- `strata_control/runtime.py:670-684` — cleanup 実装。ヘルプ経路からは呼ばれない。

同一 revision の CLI `--help` は実行していません。ヘルプ action の詳細は parser 定義と標準 `argparse` の動作に基づき、外部配布物や別 revision の出力は根拠にしていません。
