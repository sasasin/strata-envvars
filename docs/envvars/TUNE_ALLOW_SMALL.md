# `TUNE_ALLOW_SMALL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Docker entrypoint がこの変数を読み、値が厳密に `1` の場合に `strata launch --tune-allow-small` を追加します。Terminal CLI 自体が `TUNE_ALLOW_SMALL` を読む箇所はなく、環境変数は Docker 起動ラッパー向けです（`docker/entrypoint.sh:241`）。

この CLI フラグは、通常の自動 tuner が試行対象から外す「回答が少し変わる可能性がある」設定も試せるようにします。GPU の小さいカードを直接検出したり、小さいカード向け設定を有効化したりする変数ではありません。Docker の環境変数表は「allow tuning on a small card」と説明していますが（`docs/DOCKER.md:127`）、CLI の説明と実装が示す対象は、回答に小さな差が出る可能性のある tuner 候補です（`strata_cli/launch/cmd.py:123`, `strata_cli/tune_commands.py:35-36`）。

## 値と判定

entrypoint は `${TUNE_ALLOW_SMALL:-0}` を文字列 `1` と完全一致で比較します。

| 環境変数値 | entrypoint の処理 |
|---|---|
| 未設定または空文字 | `0` として扱い、フラグを追加しない |
| `1` | `--tune-allow-small` を追加 |
| その他（例: `0`, `true`, `01`, ` 1`） | フラグを追加しない |

数値変換、空白除去、大文字小文字変換、無効値のエラーはありません。比較はシェル文字列比較です（`docker/entrypoint.sh:241`）。

## 有効になる条件

- この環境変数を使うのは Docker の標準 entrypoint 経由でサーバーを起動する経路です。別コマンドをコンテナに渡すと entrypoint はそのコマンドへ `exec` し、同変数を `launch` 引数へ変換しません（`docker/entrypoint.sh:53-56,228-251`）。
- `TUNE_ALLOW_SMALL=1` はチューニングを開始しません。Docker entrypoint は `TUNE` が空でなく `skip` でもない場合に `--tune` を追加します。Docker 文書上の未指定時の既定は `skip` です（`docker/entrypoint.sh:228-241`; `docs/DOCKER.md:125,127`）。CLI 側は読み込んだ設定の `s.tune` が `skip` なら tuner を呼ばずに戻ります（`strata_cli/launch/runner.py:1839-1845`）。
- 既にチューニング済みの preset は、`RETUNE=1` で再測定を要求しない限り再チューニングされません（`docker/entrypoint.sh:231-238`; `strata_cli/launch/runner.py:1847-1863`）。
- DeepSeek-V4.1-Flash など `multi_file()` 対象モデルは専用 tuner に進み、通常モデル向けの `--allow-small-differences` 引数は組み立てられません（`strata_cli/launch/runner.py:1779-1784,1839-1845,1795-1808`）。したがって、この変数が許可する placement 候補の設定はその経路に適用されません。
- preset を指定した場合、CLI はまず preset の設定を読み、その上に指定フラグを適用します。`--tune-allow-small` は値を `True` にする一方向の指定で、環境変数が未設定・`0` の場合に preset の `True` を `False` に戻す引数はありません（`strata_cli/launch/cmd.py:212-218,271-274`; `strata_cli/launch/settings.py:130-131,149-163`）。
- 通常 tuner でも、候補はモデル、backend、計算機クラス、モード、必要条件によって絞られます。このフラグは placement 分類の候補だけを許可し、候補の実行や採用を保証しません（`strata_cli/tune_commands.py:193-199`; `strata_control/tune_knobs.py:399-445`; `strata_control/tune_knobs.py:372-375`）。

## 実行時の詳細

環境変数は entrypoint の起動処理中に一度シェルで評価され、結果は子の `strata launch` の argv に渡ります。Strata CLI は受け取った `--tune-allow-small` を `LaunchSettings.tune_allow_small` に設定します。未指定時のデフォルトは `False` です（`docker/entrypoint.sh:241`; `strata_cli/launch/settings.py:130-131`; `strata_cli/launch/cmd.py:271-274`）。プロセス中に環境変数を変えて再評価する処理はありません。

通常モデルの tuner が実行される場合、runner は `tune_allow_small` が真なら `strata tune auto ... --allow-small-differences` を起動します。tune CLI はこの値を `Options.allow_placement` に渡し、候補選択では `answer == "placement"` の候補を許可します。これは回答に差が出る可能性のある配置設定を選択肢に加える指定で、他の無効条件や速度判定を迂回するものではありません（`strata_cli/launch/runner.py:1864-1876`; `strata_cli/tune_commands.py:193-199`; `strata_control/autotune.py:50-59`; `strata_control/tune_knobs.py:372-375,429-445`）。

環境変数の値自体に対するログ、警告、エラーはありません。通常 tuner は進捗を表示し、候補の条件が合わない場合はその候補をスキップします。測定に失敗した場合や tuner の結果が失敗・中断・判定不能の場合、runner は標準設定で起動する旨を通知します（`strata_cli/launch/runner.py:1875-1908,223-239`; `strata_control/tune_knobs.py:429-445`）。

## 根拠

- 環境変数の直接参照と CLI 引数への変換: `docker/entrypoint.sh:241`。
- CLI オプションの説明、設定デフォルト、preset の上書き順: `strata_cli/launch/cmd.py:122-123,212-218,271-274`; `strata_cli/launch/settings.py:130-131,149-163`。
- 通常 tuner へのフラグ転送と、tune/既存結果/専用 tuner によるスキップ: `strata_cli/launch/runner.py:1779-1808,1839-1876`。
- `--allow-small-differences` から placement 候補の許可への伝播: `strata_cli/tune_commands.py:35-36,193-199`; `strata_control/autotune.py:50-59`; `strata_control/tune_knobs.py:372-375,399-445`。
- Docker 文書の値説明: `docs/DOCKER.md:125-127`。
