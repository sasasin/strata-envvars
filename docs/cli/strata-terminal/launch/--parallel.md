# `--parallel`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`、1〜8 |

## 役割

サーバーが同時に処理する要求数を指定します。値を省略したときは、利用可能な GPU のメモリー量を基に Strata が並列数を選びます。

## 使い方

```sh
strata launch --model iq3_xxs --parallel 4 --no-tui
```

既存 preset の設定に重ねる場合は、その起動だけの値として指定できます。次回以降にも保存するには `--save-preset NAME` を併用します。

## 値と既定値

- `N` は `int()` で整数に変換され、1〜8 の範囲に限られます。小数や数値以外、範囲外の値は parser の型変換で拒否されます。例: `--parallel 4`。
- 省略時の `LaunchSettings.parallel` は `None`（カードに合わせる）です。GPU が利用可能な通常モデルでは、実装上 31.5 GB 以上は 4、23.5 GB 以上は 3、19.5 GB 以上は 2、それ未満は 1 が選ばれます。GPU を利用できない場合は、自動値を profile override に設定しません。
- `--preset NAME` を指定すると preset を読み込み、明示した `--parallel` がその値を置き換えます。`--save-preset NAME` がなければ、フラグによる変更は preset 自体には保存されません。
- parser は通常の単一値引数として宣言されており、複数回指定を蓄積する処理はありません。

## 実行時の動作

引数から設定を作る際、値が指定されていれば `s.parallel` に代入されます。起動前の検査では 1〜8 を再確認し、GPU の自動推奨数を超える指定には警告を追加します。この警告は起動を拒否せず、ソース上の説明ではエンジンが GPU メモリーに載せるモデル量を減らすため各回答が遅くなり得ます。

通常モデルでは、明示値、または自動計算値が launch profile の `parallel` override として設定されます。起動時に profile の override 一式（host、port、parallel）が更新されます。値を省略した場合、通常モデルの自動値がここで補われます。

例外として DeepSeek-V4.1-Flash 系では同時処理数は 1 です。`--parallel` が 2〜8 なら起動前に警告を出し、値を `None` に戻して指定を使いません。この系統では自動値も `None` です。値 `1` は警告・補正の対象ではなく、profile override として `parallel=1` が設定されます。

## 適用条件と副作用

- GPU の VRAM 警告は「通常そのカードに収まる」自動値との比較です。指定値が大きくても値自体は補正されず、起動処理へ進みます。
- `--plan` と併用した場合は、計画表示に並列数または「fit to your card」が含まれます。計画経路は「Nothing was changed.」を表示して終了します。
- 起動に伴い launch 用 JSON 設定と profile の override が書き込まれます。`--save-preset` を指定した場合はさらに preset が保存されます。
- 別の port で複数の launch を動かすことはできますが、複数モデルが GPU メモリーを使い切り、新しいモデルの起動に失敗する可能性があると runner が警告します。これは `--parallel` 自体の専用検査ではなく、複数 launch の起動時の注意です。

## 出力とエラー

- 数値でない値は「requests の数ではない」、1〜8 の外は「engine が処理できる範囲外」とする parser の型エラーになります。
- 通常モデルで VRAM に対して大きい値を指定すると、起動前に警告を表示しますが拒否しません。
- DeepSeek-V4.1-Flash 系に 2〜8 を指定すると、「この Strata version では一度に1要求」と警告し、指定値を使わず続行します。
- 起動前の設定検査で error があれば `strata launch` は失敗メッセージを出して終了コード 2 を返します。`--parallel` の範囲外は、通常この検査より前の parser で拒否されます。

## 根拠

- `strata_cli/launch/cmd.py:65-72,100` — `_parallel` の整数変換と 1〜8 の parser 定義。
- `strata_cli/launch/cmd.py:197-203,224-231` — preset 読み込み後に CLI 値を設定へ重ねる処理。
- `strata_cli/launch/settings.py:35-44,92,194-207` — VRAM による自動値、未指定状態、範囲・VRAM 警告の検査。
- `strata_cli/launch/cmd.py:302-355` — DeepSeek 系の値の無効化、並列数検査。
- `strata_cli/launch/runner.py:1235-1243,1246-1279` — 起動設定ファイル、profile override、自動値と DeepSeek 系の扱い。
- `strata_cli/launch/cmd.py:733-760,721-725` — 計画表示、検査 error の失敗経路。
- `strata_cli/launch/store.py:146-150`、`strata_cli/launch/cmd.py:788-793` — preset に並列数を保持し、明示したときに保存する処理。
- `strata_cli/launch/runner.py:1505-1508,1522-1524` — 別 port の launch と GPU メモリーに関する注意。
