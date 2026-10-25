# `--model-path`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--model-path` |
| 別名 | なし |
| 値 | `PATH`。既存の GGUF ファイル1個、または GGUF shard を含むフォルダー |

## 役割

既に手元にあるモデルファイルを `strata launch` で使います。パスはファイルまたはフォルダーで指定でき、複数 shard のモデルでは shard を含むフォルダーを指定します。`--model` を省くとファイル情報から Strata がモデルを識別します。この文書は `strata launch` parser にある同名オプションのスコープを扱います。

## 使い方

```sh
strata launch --model-path /data/models/IQ3_XXS --no-tui
strata launch --model q2_0 --model-path /data/models/q2_0.gguf --plan
```

1例目はフォルダー内のファイルからモデルを判定して起動します。2例目のように `--model` と併用すると、そのモデル名を使い、指定パス内から該当ファイルを準備します。`--plan` では起動計画を表示して終了します。

## 値と既定値

- `PATH` は必須の文字列です。parser に型変換、選択肢、専用の既定値はなく、省略時は `None`（設定なし）です。設定への反映時に `~` をホームディレクトリへ展開します。
- 存在しないファイル・フォルダー、GGUF を含まないフォルダー、GGUF でないファイル、認識できないモデル、複数候補や不完全な shard 群などは実行時検査で拒否される場合があります。単にパス文字列を受け付けるだけでは起動可能性を保証しません。
- 空文字列は `if a.model_path` の判定を通らず、指定なしとして扱われます。複数回指定したときの特別な拒否処理はなく、argparse の通常の単一値 option として最終値が Namespace に入ります。

## 実行時の動作

設定構築では `--model-path` の値を `Path(...).expanduser()` で展開して `LaunchSettings.model_path` に保存します。`--model-path` があり、`--model` がない場合は preset から継承した `family` / `model` をクリアします。その後 Runner が実ファイルを調べ、既知の候補を一意に判別できれば family と model を設定します。フォルダーの上位を指定した場合はモデルの実フォルダーを選び、単一の `.gguf` ファイルを指定した場合はそのファイルを保持します。

ファイル群を判定した後、起動時に setup.py へ `--gguf-dir PATH` として渡します。入力がファイルなら親フォルダー、ディレクトリならそのディレクトリを渡します。Strata は手元のモデルファイルを移動せず、その場所から使います。一方、モデル family や設定に応じて不足する engine、prepared pack、画像 reader、draft layer などがあれば別途ダウンロード・準備される場合があります。

`--model` との併用時は指定モデルが優先され、ファイルヘッダーの判定と異なる場合でもパス検査段階で直ちに拒否せず、指定モデルのファイルをそのフォルダーから探します。不一致は通知され、setup が該当ファイルを見つけられず停止することがあります。`--family` は `--model` と併用する場合にモデル選択へ使われます。

`--plan` でもパスの検査とモデルファイルの識別は実行され、計画に利用されます。計画モードの説明では変更を行わず終了します。通常起動ではファイル検査後、engine/model の準備、設定の作成、推論 server 起動へ進みます。

## 適用条件と副作用

- パスが存在しない場合は engine の取得や setup に進む前に失敗します。symlink のリンク先がなくなっている場合も専用の案内を返します。
- フォルダー指定では直下およびその下のフォルダーにある GGUF を探索します。複数のモデル群がある場合は、Strata が認識するモデル群が一つだけならそれを選ぶことがあります。複数候補を絞れない場合は、対象モデルのフォルダーまたは `.gguf` ファイルを指定するよう案内します。探索・候補選定は `strata_control.models.plan_import` に委譲されます。
- DeepSeek V4.1 の shard 群は専用判定経路があります。通常の `plan_import` による識別とは異なるため、この文書では対応 shard 名や全モデル形式の境界までは列挙しません。
- `--data-dir` を併用すると、モデルファイルは指定した場所で使い続け、補助ファイルやデータ配置には `--data-dir` が関係します。既存のインストール済み設定が別のモデルパスを指す場合、その設定を再利用せず、指定されたパスで setup を行います。
- 指定ファイル・フォルダーの移動や削除をこのオプション自体は行いません。起動処理はモデル設定の保存や server 起動を行い、別途必要な補助物を取得する可能性があります。

## 出力とエラー

パスが存在しない場合は `This folder does not exist: ...` または `This file does not exist: ...`、GGUF が見つからない場合はフォルダー内にモデルファイルがない旨を stderr に出し、通常は終了コード 2 で失敗します。モデル内容が読み取れない、shard が不足する、複数モデルを特定できない等の識別失敗は `LaunchError` として案内され、識別処理で指定されているコードは 5 です。`--output json` 併用時は失敗内容を JSON の `error.message` に出力します。

起動時の setup が失敗した場合は setup のエラーを launch のエラーに変換し、追加の詳細出力をログファイルへ保存できる場合があります。失敗内容に応じた終了コード・文面は setup の結果に依存するため、すべての setup 失敗に共通のコードとは断定できません。

## 根拠

- `strata_cli/launch/cmd.py:83-90` — `strata launch` の parser 定義と PATH の説明。
- `strata_cli/launch/cmd.py:197-216` — preset へのフラグ適用、ホーム展開、モデル名未指定時に継承モデルを消す処理。
- `strata_cli/launch/cmd.py:630-641,679-720,733-760,784-787` — launch の出力・失敗処理、モデルパス検査、計画表示、起動への分岐。
- `strata_cli/launch/settings.py:77-95` — `LaunchSettings.model_path` の型と未指定値。
- `strata_cli/launch/runner.py:1149-1198` — 検査順序、パス検査、ファイル群の識別、`--model` 併用時の扱い。
- `strata_cli/launch/runner.py:730-775,925-959` — setup.py への `--gguf-dir` 転送とファイル指定時の親フォルダー化。
- `strata_cli/launch/runner.py:2011-2044` — setup、設定保存、起動までの順序。
- `strata_control/models.py:538-576,579-638,641-720` — 絶対パス化、import 対象選択、存在検査、GGUF・shard・複数候補・内容検査。
- `docs/TERMINAL_LAUNCH.md:57-67` — 利用者向けの `--model-path` 使用例。
- `tests/terminal/test_flow2_022.py:41-75,121-141` — パス不在・空フォルダー・symlink shard 等のケースを示す既存テスト（実行はしていない）。

調査範囲は上記 commit のソースと checkout 内の利用者向け文書です。CLI help や Release 配布物は別途実行・照合していません。DeepSeek 専用判定の全ルール、setup.py と各 platform/backend における補助ファイル取得の全条件は、このオプション単独の経路から確認できる範囲を超えるため記載を限定しています。
