# `strata serve --batch-telemetry`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--batch-telemetry` |
| 別名 | `--no-batch-telemetry`（無効化する否定形） |
| 値 | 値を取らない boolean フラグ |

## 役割

通常は無効なエンジンの decode batch window 計測を有効にし、処理した verifier row 数と稼働中 request slot 数を `/v1/telemetry` に含めます。対応するエンジンは計測値を標準出力の内部 protocol 行でサーバーへ送り、サーバーが request の token 出力から分離して保持します。これは GPU 使用率ではなく、batch window の仕事量を観測するための値です（`terminal/strata_cli/cli.py:78-79`、`engine/src/program/generate.cpp:16721-16740`、`terminal/serve/server.py:1041-1045`、`terminal/serve/server.py:7130-7141`）。

## 使い方

```sh
# run config の推論サーバーを foreground で起動し、対応エンジンの batch 計測を有効にする
strata serve --config ./run-config.json --batch-telemetry

# 起動せず、解決された起動計画を確認する
strata serve --config ./run-config.json --batch-telemetry --plan
```

`--config` は `--profile` の alias です。`--plan` は起動計画を出力して終了するため、サーバーや推論エンジンは起動しません（`terminal/strata_cli/cli.py:67-69`、`terminal/strata_cli/cli.py:974-981`）。

## 値と既定値

- 値を伴わないフラグです。`argparse.BooleanOptionalAction` により `--batch-telemetry` が有効、`--no-batch-telemetry` が無効を指定し、CLI parser 上の既定値は `None`（未指定）です（`terminal/strata_cli/cli.py:78-79`）。サーバー側にも同じ option 定義があります（`terminal/serve/server.py:8671-8672`）。
- 未指定時は保存 profile、run config、環境変数の順に設定を探し、いずれもなければ無効です。CLI 指定が最優先です（`terminal/strata_cli/cli.py:783-803`）。
- `STRATA_BATCH_TELEMETRY` が存在し、他の設定がない場合、Terminal CLI は値が厳密に `1` のとき有効、それ以外は無効として扱います（`terminal/strata_cli/cli.py:799-802`）。環境変数の説明は [`STRATA_BATCH_TELEMETRY`](../../../envvars/STRATA_BATCH_TELEMETRY.md) を参照してください。
- run config の `batch_telemetry` は JSON boolean である必要があります。別の型ならサーバー parser が `batch_telemetry must be true or false` で起動を拒否します（`terminal/serve/server.py:8767-8768`）。保存 profile でも値は `true` / `false` のみ受理されます（`terminal/strata_control/profiles.py:88-95`、`terminal/strata_control/profiles.py:113-116`）。

## 実行時の動作

Terminal CLI は、優先順位で決めた値の由来がコマンド指定・保存 profile・環境変数の場合、その boolean を `--batch-telemetry` または `--no-batch-telemetry` としてサーバーへ渡します。run config 由来と既定値の場合はサーバー引数へ重ねず、run config または継承環境を使います（`terminal/strata_cli/cli.py:837-844`）。サーバーは単一エンジン経路で子プロセス用環境を組み立て、明示値または config 値が true なら `STRATA_BATCH_TELEMETRY=1` を設定し、false ならその変数を取り除きます。どちらも指定がなければ継承値を維持します（`terminal/serve/server.py:705-712`、`terminal/serve/server.py:8873-8878`）。split fallback に切り替える場合もこの環境設定が適用されます（`terminal/serve/server.py:8272-8308`）。

エンジンの `generate.cpp` は環境変数が厳密に `1` の場合だけ sampler を有効にします。batch window 完了時の集計はおおむね 1 秒ごとに出力され、全 slot が idle になった時は最終の部分集計を出します。計測対象 row には pipeline の padding row と MTP row も含まれます。server は `BSTAT` 行を token stream に流さず、最後に受け取った sample を `/v1/telemetry` の work 情報へ追加します（`engine/include/strata/core/batch_telemetry.hpp:12-20,27-40`、`engine/src/program/generate.cpp:16733-16740`、`terminal/serve/server.py:1041-1045`、`terminal/serve/server.py:7130-7141`）。この設定は pipeline stage sampler も有効化します（`engine/src/program/generate.cpp:17423-17427,18243-18250`）。

## 適用条件と副作用

- `engine/src/program/generate.cpp` でこの環境変数を読むことを確認しました。別の実行ファイルを指定した場合、その実装が同じ環境変数と protocol に対応するかはこの調査では確認できません。
- replica および split の通常起動経路は、それぞれ replica / role ごとに `child_env(...)` を作ってエンジンを開始し、単一エンジン経路にある `configure_batch_telemetry_env(...)` を呼びません（`terminal/serve/server.py:8956-8961`、`terminal/serve/server.py:8313-8336`、`terminal/serve/server.py:8383-8403`）。そのため、この CLI option による環境変数の明示設定がこれらの子エンジンへ渡ることはソース上で確認できません。環境変数が起動元から継承される場合の値は別途 `child_env` の処理に従います（`terminal/serve/server.py:3870-3874`）。
- 対応エンジンは内部 protocol 用の `BSTAT`（および pipeline 用の `PSTAT`）を標準出力へ追加します。サーバーはこれらを request token として扱わず sample にします。ファイル変更や外部ネットワーク接続をこの option が行う処理は確認できません（`engine/src/program/generate.cpp:16733-16740,18243-18250`、`terminal/serve/server.py:1041-1049`）。
- 計測が無効、未対応、またはまだ sample が届いていない場合、batch sample は telemetry 応答に現れません。server は `/v1/telemetry` で `svc.metrics()` を返します（`terminal/serve/server.py:7034-7039`、`terminal/serve/server.py:7130-7141`）。

## 出力とエラー

- 有効時、対応エンジンは `BSTAT <window数> <processed rows> <active rows> <elapsed ms>` を標準出力へ出します。server がこの制御行を消費するため、クライアントの生成 token には入りません（`engine/src/program/generate.cpp:16733-16740`、`terminal/serve/server.py:1041-1045`）。
- option 自体に値の validation はありません。無効な run config 値は前述の parser error で拒否されます。CLI の parser は未知の引数を `ap.error(...)` に渡すため、値を後置しても値付き option として受理される定義ではありません（`terminal/strata_cli/cli.py:2325-2334`）。

## 根拠

- `terminal/strata_cli/cli.py:62-88` — Terminal CLI の `serve` parser、両方向 option と既定値。
- `terminal/strata_cli/cli.py:783-818,837-844` — profile / run config / environment / default の解決とサーバー引数への反映。
- `terminal/serve/server.py:705-712,8671-8673,8767-8768,8873-8878,8956-8961` — サーバー parser、config 検証、engine 環境の設定と経路分岐。
- `engine/include/strata/core/batch_telemetry.hpp:12-40`、`engine/src/program/generate.cpp:16721-16740,17423-17427,18243-18250` — 計測値、出力条件、batch / pipeline sampler。
- `terminal/serve/server.py:1041-1049,7034-7039,7130-7141` — 制御行の消費と telemetry 応答への反映。
