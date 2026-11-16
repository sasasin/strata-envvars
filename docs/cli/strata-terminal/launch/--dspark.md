# `--dspark`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--dspark` |
| 別名 | なし |
| 値 | `WORD` を1個取る。値の選択肢や型変換は定義されていない。 |

## 役割

このフラグは旧 DeepSeek 起動指定との互換性のため parser に受理されるが、現行 Strata では DeepSeek モデルを提供しないことを案内して終了する。DSpark の実行設定を作ったり、エンジンへ値を渡したりはしない。`--help` の通常表示からは隠されている。

## 使い方

```sh
strata launch --model q2_0 --dspark on
```

非空の値を指定すると DeepSeek 非対応の案内で失敗するため、現行モデルの起動には使用できない。これは動作確認用の例であり、起動を成功させる例ではない。

## 値と既定値

- `strata_cli/launch/cmd.py:120` では `metavar="WORD"` の引数として登録され、`type`、`choices`、`default` は指定されていない。値の語彙・大小文字・形式に関する専用 validation はない。
- 省略時は argparse の通常の既定値 `None` となり、このフラグによる拒否は起きない。
- 通常の起動設定経路では、`settings_from_args` が最終的な `a.dspark` の真偽値を検査する（`strata_cli/launch/cmd.py:217-219`）。したがって非空値は内容を問わず拒否される。空文字列はこの判定を通過するが、DSpark の値として利用される処理はない。
- 短縮別名は登録されていない。

## 実行時の動作

parser は値を `Namespace` に格納し、通常の起動設定経路で `settings_from_args` が `dsv41_package`、`speed`、`full_quality` とともに `dspark` を検査する。値が真なら `strata_control.retired.NOT_OFFERED` を `ValueError` として送出する。メッセージは「Strata no longer offers DeepSeek models. Run `strata launch` to choose one of the Qwen models.」である（`strata_cli/launch/cmd.py:217-222`、`strata_control/retired.py:42-43`）。ただし `--list-presets`、`--delete-preset`、`--stop`、`--status`、`--show-key` は先に処理して戻るため、これらの管理モードでは `--dspark` の拒否判定に進まない（`strata_cli/launch/cmd.py:723-769`）。

この判定は `run_launch` 内で `--backend` の処理と `Catalog()` の生成を試みた後に行われる（`strata_cli/launch/cmd.py:771-798`）。そのため、有効な `--backend <メーカー>` を `--dspark` と併用し、かつ `--plan` を付けない場合、DeepSeek 拒否に至る前に環境変数 `STRATA_ENGINE_BACKEND` がこのプロセスへ設定され、選択値が設定ファイルへ保存される。`--backend auto` は同じ順序で保存済み選択を消す。`--plan` ではこの永続化・削除を行わない（`strata_cli/launch/cmd.py:771-791`、`strata_control/engine_component.py:513-525`）。無効な backend 値は `--dspark` 判定より先にエラーとなる。

## 適用条件と副作用

- 非空値の場合、モデル・プリセットを起動する本処理には進まず、DSpark の設定変更やモデルファイル操作は行われない（拒否判定は `strata_cli/launch/cmd.py:217-222`、`Runner` の作成は同ファイル:830以降）。
- 管理モードの上記オプションを併用すると、管理処理が `settings_from_args` より先に実行される。たとえば `--delete-preset NAME --dspark on` は拒否されずプリセット削除へ進むため、`--dspark` を安全確認やキャンセル条件として扱えない（`strata_cli/launch/cmd.py:723-769,798`）。
- 上記の `--backend` 併用時は、拒否されても backend 選択の保存または解除が先行し得る。`--plan` はその永続変更を抑止する。
- 旧フラグとして parser が引数を受けることと、DeepSeek や DSpark が現行実行可能であることは別である。`strata_control/retired.py:4-7,42-43` は現行版が DeepSeek を実行しない旨と、このフラグを含む「指定された DeepSeek」の案内文を定義している。

## 出力とエラー

非空値では `ValueError` が CLI の共通処理に捕捉され、通常出力では標準エラーに `strata: ` と拒否メッセージを出して終了コード `2` を返す。`--output json` の場合は標準出力に `ok:false`、`error.code:2`、同じメッセージを含む JSON を出す（`strata_cli/cli.py:2179-2186,528-533`）。この拒否経路自体は起動用ファイルを書かないが、前節の backend 永続化は先に行われる場合がある。

## 根拠

- `strata_cli/launch/cmd.py:120` — `--dspark WORD` の parser 登録。ヘルプ出力から抑制。
- `strata_cli/launch/cmd.py:217-222` — 非空値を DeepSeek 非対応エラーへ変換する条件。
- `strata_cli/launch/cmd.py:723-769,798` — 管理モードの早期分岐と、通常の設定検査までの順序。
- `strata_control/retired.py:4-7,42-43` — DeepSeek 非対応の説明と、表示する案内文。
- `strata_cli/launch/cmd.py:771-798`、`strata_control/engine_component.py:513-525` — 拒否判定より前に行われる backend 選択の環境設定・永続化。
- `strata_cli/cli.py:2179-2186,528-533` — `ValueError` の出力形式と終了コード。
