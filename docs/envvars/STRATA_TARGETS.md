# `STRATA_TARGETS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この commit の Strata 本体（C++/CUDA/HIP/SYCL、Python サーバーやセットアップ、候補一覧に含まれる同梱ツール）には、`STRATA_TARGETS` を読み取る実装を確認できませんでした。したがって、Strata の通常実行時にこの環境変数が何かを制御するとは判断できません。

リポジトリ内で見つかった参照は `bench/results/2026-10-04-community-2x-rtx3060/bench.py` と同ディレクトリの `bench-0.1.39.py` だけです。これらは benchmark 結果・記録の配下にあるため、調査手順で定められた対象範囲から除外されます。このため、そこに記載された benchmark 固有の使い方は Strata の環境変数仕様として扱いません。

## 値と判定

対象範囲の Strata ソースに読み取り箇所がないため、未設定・空文字・値の形式・無効値・既定値に関する Strata の判定規則はありません（確認できません）。

## 有効になる条件

対象範囲では参照が見つからず、OS、backend、build macro、CLI、モデル状態、他の環境変数との相互作用も確認できませんでした。Strata の機能を有効にする環境変数としては根拠がありません。

## 実行時の詳細

対象範囲に読み取り処理がないため、評価時期、キャッシュ、子プロセスへの継承・上書き、実行結果やログへの影響は確認できませんでした。`docs/DETAILS.md` にも、この環境変数の仕様を裏付ける説明は見つかりませんでした。

## 根拠

- `git rev-parse HEAD`: `011c9e600a93bbc9fd451c563501b5831c32bbca`。調査時の作業ツリーは `main` で、変更はありませんでした。
- 対象リポジトリ全体を `STRATA_TARGETS` で検索すると、参照は次の2ファイルに限られました。どちらも `bench/results/` 内の benchmark 記録であり、調査対象外です: `bench/results/2026-10-04-community-2x-rtx3060/bench.py:22,47`、`bench/results/2026-10-04-community-2x-rtx3060/bench-0.1.39.py:22,47`。
- `src/`, `include/`, `sycl/`, `serve/`, `setup.py`, `tools/` など、手順で指定された Strata 実装範囲には直接参照がありませんでした。該当する読み取り箇所がないため、値の変換や実際の効果についてのソース根拠はありません。
