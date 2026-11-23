# `--model-config`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json` として表示される1つの文字列。parser で型・パスの検証はしない |

## 役割

このオプションは `update_cmd.py` の複数サブコマンドで共用され、通常の `strata update` では更新後エンジンのテスト起動に使う実行設定を指定する。しかし `strata components add-build` では値は利用されず、ビルドの追加・切替にも影響しない。したがって、このコマンドに渡しても指定したモデル設定での起動確認は行われない。

## 使い方

```sh
# add-build では --model-config の値は使われない。
strata components add-build ./build --model-config ./run-config.json
```

## 値と既定値

`--model-config` の値は省略できない引数として parser に登録され、未指定時は `None`。`argparse` は値を文字列として受け取るだけで、このコマンド経路では空文字列や存在しないパスを含めて設定ファイルを読み込まず、値を検査しない（`terminal/strata_cli/update_cmd.py:54-55`, `terminal/strata_cli/update_cmd.py:95-98`, `terminal/strata_cli/update_cmd.py:425-434`）。

## 実行時の動作

`add-build` は共通 parser 登録を通じてオプションを受理する。実行時には `a.model_config` を共通の updater context の `run_config` に格納するが、その後 `add-build` 分岐は `_add_build_command` を呼び、そこでは `run_config` を参照せず、ビルドの検査・登録後に `use_engine` で登録したエンジンを選択する（`terminal/strata_cli/update_cmd.py:47-56`, `terminal/strata_cli/update_cmd.py:95-99`, `terminal/strata_cli/update_cmd.py:314-321`, `terminal/strata_cli/update_cmd.py:337-340`, `terminal/strata_cli/update_cmd.py:425-442`）。

同じ値が使われるのは更新処理のテスト起動経路である。`default_test_start` は `ctx.run_config` があればそれをテスト対象として開く（`terminal/strata_control/updater.py:1342-1353`）。この動作は `add-build` の経路には適用されない。

## 適用条件と副作用

`--model-config` 自体によるファイルアクセス、モデル起動、設定変更はありません。`add-build` 本体は指定フォルダーのエンジン実行ファイルを `--version` 付きで起動して動作確認し、ビルド記録から backend・アーキテクチャを調べ、対象ファイルをコンポーネント領域へコピーします。その後、そのローカルエンジンを選択状態にします。ローカル登録物は署名なしです。`STRATA_REQUIRE_SIGNED_COMPONENTS` が署名を要求する環境では追加後の選択処理が失敗し得るため、追加だけが済んだ状態が残る場合があります（`terminal/strata_control/local_engine.py:127-177`, `terminal/strata_cli/update_cmd.py:425-442`, `terminal/strata_control/engine_library.py:296-312`, `terminal/strata_control/engine_component.py:386-394`）。

## 出力とエラー

このオプションの値に関する専用の警告・エラー・終了コードはありません。`--model-config` が指すファイルが存在しない場合でも、このオプションを理由に失敗しません。コマンド自体はビルドフォルダーや実行ファイルの不足などで失敗し得ますが、それらは `--model-config` の検証結果ではありません（`terminal/strata_control/local_engine.py:41-46`, `terminal/strata_control/local_engine.py:127-144`）。処理失敗時は human 出力では stderr に `strata: ...`、JSON 出力ではエラーオブジェクトを出して終了コードを返します（`terminal/strata_cli/update_cmd.py:307-312`, `terminal/strata_cli/update_cmd.py:374-384`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における `--model-config` の値・既定値と説明。
- `terminal/strata_cli/update_cmd.py:95-99` — `add-build` が共通 parser を使い、位置引数 `folder` を定義する箇所。
- `terminal/strata_cli/update_cmd.py:314-321`, `337-340`, `425-442` — 値の context 格納、`add-build` 分岐、値を参照せず登録・選択する処理。
- `terminal/strata_control/updater.py:1342-1353` — `run_config` が使われる別経路（更新後のテスト起動）。
- `terminal/strata_control/local_engine.py:127-177` — `add-build` の入力判定、ファイルコピー、ローカル・署名なし manifest の作成。
- `terminal/strata_control/engine_component.py:386-394` — 署名必須設定時に署名なしパッケージを拒否する処理。
