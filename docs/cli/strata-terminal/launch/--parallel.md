# `strata launch --parallel`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | `N`（整数、1〜8） |

## 役割

同時に応答を処理するリクエスト数を指定する。値はモデル設定と起動プロファイルに反映され、通常のエンジンでは最大 `N` 件を batch slot で同時に decode し、超えた分は順番待ちにする。全カード split engine が使われる場合は `N` が split の lane 数として扱われる（`strata_cli/launch/cmd.py:97`、`serve/server.py:3983-4010`、`strata_cli/launch/runner.py:1737-1757`）。

## 使い方

```sh
# 保存済みプリセットの起動時に同時リクエスト数を4にする
strata launch --preset Office --parallel 4
```

`--preset` による既存設定を読み込んだ後、コマンドラインで指定した値がその設定を上書きする（`strata_cli/launch/cmd.py:206-212,243-244`）。

## 値と既定値

- `N` は整数で、1〜8を受け付ける。整数に変換できない値、範囲外の値は parser が拒否する。別名はない（`strata_cli/launch/cmd.py:63-70,97`）。
- 省略時の初期値は `None`（カードに合わせる）だが、指定済みプリセットの値は引き継がれる（`strata_cli/launch/settings.py:81-96`、`strata_cli/launch/cmd.py:206-212`）。新規設定で自動選択するときは VRAM に応じて、約20 GB未満で1、20 GBから2、24 GBから3、32 GBから4を選ぶ。境界判定には各段階で0.5 GBの許容幅がある（`strata_cli/launch/settings.py:36-46`、`strata_cli/launch/runner.py:1797-1805,1837-1840`）。利用可能な GPU がない、またはカード情報を取得できない場合、自動値は設定されず、起動プロファイルへ `parallel` override を追加しない。
- 明示値がカードの自動目安を超えても CLI は拒否せず警告し、起動を続ける。警告は「カードが通常保持できる数」を超える場合に出て、メモリ上の余裕が減り各応答が遅くなり得ると案内する（`strata_cli/launch/settings.py:199-212`）。

## 実行時の動作

`strata launch` は `--parallel` を設定に取り込み、起動用 JSON を作成する。通常は `launch-<name>` の共有 profile に `parallel=N` を設定し、その起動で使う host・port とともに override を置き換える（`strata_cli/launch/runner.py:1692-1715,1797-1818`）。通常のエンジンでは Strata server が設定値を `--batch N` に変換し、エンジンへ渡す。`N=1` なら追加の batch 引数を渡さず1件ずつ処理する。エンジンが要求数を扱えない場合、Strata は要求値を渡し、エンジン側の警告・調整に委ねる（`serve/server.py:3983-4010`）。

相互作用として、`--drafting auto` は複数リクエスト同時処理時に MTP を選ぶ動作が parser の説明に記され、runner も parallel 数を drafter 判定へ渡す（`strata_cli/launch/cmd.py:101-104`、`strata_cli/launch/runner.py:1599-1606`）。全カード split engine では `parallel` が lane 数になり、engine 設定内にすでに `--batch` / `--slots` がある構成では profile override を重ねない（`strata_cli/launch/runner.py:1737-1752,1797-1835`）。

## 適用条件と副作用

値は launch の設定と共有 profile に書き込まれ、起動時の同時処理数に影響する。実際に使われる slot 数はモデル、カード、engine/backend によって要求値と異なる場合がある。Strata server は要求数が engine の通常上限を超え、分割実行などの条件にも該当しない場合、標準出力へ上限を使う旨を表示する（`serve/server.py:3970-3974,4004-4010`）。調査では動的な実機 slot 数を確認していない。

## 出力とエラー

- 非整数には「数値を使うか省略」、1〜8の範囲外には「1〜8を使う」という parser エラーが設定される（`strata_cli/launch/cmd.py:63-70`）。この時点で launch の処理には進まない。
- 指定値がカードの目安を超えると警告を出すが、起動自体は許可する（`strata_cli/launch/settings.py:199-212`）。engine が要求値を調整する場合は server/engine の出力に委ねられる（`serve/server.py:3983-4010`）。

## 根拠

- `strata_cli/launch/cmd.py:63-70,73-80,97` — 値の変換・範囲 validation、コマンド parser 定義。
- `strata_cli/launch/settings.py:36-46,81-96,199-212` — 自動値、設定値、VRAM に対する警告。
- `strata_cli/launch/cmd.py:206-212,243-244` — プリセットへの CLI 値の適用。
- `strata_cli/launch/runner.py:1692-1715,1737-1757,1797-1842` — 起動設定の保存、split engine の lane 処理、profile override と自動値。
- `serve/server.py:3970-4010` — `parallel` 設定から engine 引数への変換と上限時の出力。
- `docs/TERMINAL_LAUNCH.md:96` — 利用者向け説明との照合。値域と既定値の説明は parser と一致する。
