# `OWN5_EXIT_AFTER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは通常配布ビルドの設定ではなく、`terminal/tools/image/gate/stage_hooks.py` が OWN-5 のテスト用ビルドに埋め込むステージフックである。同スクリプトは stable-diffusion.cpp の作業コピーへフックを挿入し、DiT のモデル呼び出し後に `OWN5_EXIT_AFTER` を評価する。指定した呼び出しの出力をダンプしてから `sd-cli` プロセスを正常終了させ、後続処理（画像生成を含む）へ進ませない。通常の Strata サーバーやフックなしの `sd-cli` の挙動を変える設定ではない（`terminal/tools/image/gate/stage_hooks.py:1-2, 10, 76-84`）。

## 値と判定

フックの `env()` は `std::getenv` の結果が null または空文字列なら null を返す。`vel_hook()` はそれ以外の値を `std::atoi` に渡し、全体の妥当性検査なしで、0 から始まるモデル呼び出し番号 `k` と比較する（`k >= atoi(value)`）。したがって空白・符号・数字の後ろの文字列は `atoi` の規則で扱われ、文字列全体を検証しない（`terminal/tools/image/gate/stage_hooks.py:33, 76-83`）。

| 条件 | unset | 終了する値の例 | 終了しない値の例 |
|---|---|---|---|
| ステージフック入りビルド | 終了判定を行わない | `0`、`1`、`2abc`（それぞれモデル呼び出し 0、1、2 の後）。負数や数字に変換できない非空文字列は `atoi` が 0 または負数を返すため、最初のモデル呼び出し後に終了する | 空文字列は unset と同じ。`3` はモデル呼び出しが 0〜2 だけなら終了条件に達しない |

`atoi` の範囲外入力の結果はこのコードで検査・制限されていないため、保証できる値域は定義されていない。大きい値への clamp や無効値時の別の既定値はない（`terminal/tools/image/gate/stage_hooks.py:33, 80-82`）。

## 有効になる条件

- `stage_hooks.py` でフックを注入し、そのコピーから作った `sd-cli` を実行すること。フック生成自体がテスト専用であり、スクリプトの説明にも「never in a shipped build path」とある（`terminal/tools/image/gate/stage_hooks.py:1-2, 118-145`）。
- `run_set.py` 経由の場合、stage-hook variant を選び、`--exit-after K` を渡すと、その値が各 `sd-cli` 子プロセスの `OWN5_EXIT_AFTER` に設定される。`--exit-after` がなければ `--env OWN5_EXIT_AFTER=...` で渡した値が使われうる。両方を指定した場合は `--exit-after` の設定が後から行われて優先する（`terminal/tools/image/gate/run_set.py:102-109, 127-140`）。
- hook のない通常ビルドでは、この環境変数を読むコードがないため効果はない。stage-hook 以外の画像実行経路・サーバーモードへは適用されない（`terminal/tools/image/gate/build_variant.py:1-2, 28-30`; `terminal/tools/image/gate/run_set.py:1-10`）。

## 実行時の詳細

`vel_hook()` は DiT の `compute()` が返した出力を `vel_<k>` としてダンプし、その直後に環境変数を読み直す。条件に達しなければ `k` を 1 増やして次の呼び出しへ進む。呼び出し番号はプロセス内の関数 static 値で 0 から始まる。環境値自体は static cache せず、フック呼び出しごとに `getenv` する（`terminal/tools/image/gate/stage_hooks.py:66, 76-84, 138-145`）。

条件に達した場合は stderr に `OWN5: exit after model call <k>` を出して flush し、`std::exit(0)` する。そのため該当 `vel_<k>` のダンプ後に正常終了し、画像は完成しない。`run_set.py` は子プロセスの出力を `.log` に集約し、終了コード 0 かつ `--exit-after` 指定時に `results.jsonl` へ `stopped after model call <K> (stage run, no picture)` の note を記録する。これは指定した文字列をそのまま記録するため、`atoi` で解釈された呼び出し番号とは表記が異なる場合がある（`terminal/tools/image/gate/stage_hooks.py:80-82`; `terminal/tools/image/gate/run_set.py:146-179`）。

## 根拠

- `terminal/tools/image/gate/stage_hooks.py:1-20, 25-33, 66-84, 118-145` — テスト専用フック、値判定、モデル呼び出し後の終了、およびコピーへの注入箇所。
- `terminal/tools/image/gate/run_set.py:1-10, 102-109, 127-140, 146-179` — `--exit-after` と `--env` の設定、子プロセス起動、ログ・終了結果の記録。
- `terminal/tools/image/gate/build_variant.py:1-2, 28-30` — フック入り variant の生成経路。
