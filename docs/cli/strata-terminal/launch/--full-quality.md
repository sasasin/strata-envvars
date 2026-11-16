# `--full-quality`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--full-quality` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真、未指定時は偽。 |

## 役割

旧 DeepSeek 用スクリプトとの互換性のため parser が受け付ける隠しフラグです。現行 Strata は DeepSeek を提供しないため、このフラグを指定するとモデルの品質設定には使われず、起動前に拒否されます。

## 使い方

```sh
strata launch --model qwen-model --full-quality
```

この例は互換フラグの拒否経路を示します。現行モデルの品質を変更するコマンド例ではありません。

## 値と既定値

値は不要です。`argparse` の `store_true` で定義され、未指定時は `False` です。追加の値を渡す形式、範囲検証、複数回指定の特別な処理はありません（`strata_cli/launch/cmd.py:110`）。

## 実行時の動作

`strata launch` の parser は `--full-quality` を受け付けますが、help 表示からは隠しています（`strata_cli/launch/cmd.py:73-80,110`）。引数設定の構築時に `full_quality` が真なら、他の旧 DeepSeek 専用フラグと同じ経路で `ValueError` を送出し、`strata_control.retired.NOT_OFFERED` の文言を返します。エラー文は「Strata no longer offers DeepSeek models. Run `strata launch` to choose one of the Qwen models.」です（`strata_cli/launch/cmd.py:206-220`、`strata_control/retired.py:42-43`）。

したがって、指定しない場合はこのフラグによる変更はありません。指定した場合は品質設定に反映されず、起動処理は続行しません。`--model` 等との組み合わせで拒否を回避できる条件はありません。

## 適用条件と副作用

旧コマンドライン呼び出しを認識して案内するための互換入力です。通常の `--help` には表示されず、DeepSeek を実行する機能や品質モードはありません（`strata_cli/launch/cmd.py:109-110,217-220`）。拒否は launch 設定の検証時に起き、`run_launch` はこの `ValueError` を終了コード `2` の失敗として扱います（`strata_cli/launch/cmd.py:798,963-964`）。この拒否経路からモデル起動・ダウンロードへ進む処理は確認できません。

## 根拠

- `strata_cli/launch/cmd.py:73-80,110` — `launch` parser の登録位置、`store_true`、help 非表示。
- `strata_cli/launch/cmd.py:206-220` — `full_quality` が真の場合の拒否条件と `ValueError`。
- `strata_control/retired.py:42-43` — 現行の拒否メッセージ。
- `strata_cli/launch/cmd.py:798,961-964` — launch 設定生成からエラー捕捉、終了コード `2` への変換。
- `docs/cli/README.md:809-824` — `strata launch` のコマンド階層と索引リンク。
