# `STRATA_DF2_PROFILE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

DFlash2 drafter の各 draft round を CUDA graph 経由で実行せず、各処理段階の前後に CUDA event を置いて所要時間を集計する計測用スイッチです。DFlash2 の実装コメントも「measurement only」としています。通常のグラフ実行経路を切り替えるため、プロファイル有効時の処理時間は通常実行の性能を表しません。トークンや確率の同一性について、この計測機能の実装から保証することはできません。

対象は `STRATA_HAVE_DFLASH2` を含むビルドで、CLI の `--draft dflash2` が選ばれ、DFlash2 の利用条件を満たしてロードできた場合です。DFlash2 は `--mtp` と `--spec 2` 以上、native pack、単一 GPU の CLI 実行、`--draft-model PACK` を必要とします。serve、batch、複数 GPU / layer split では DFlash2 を選べず、MTP に fallback します。

## 値と判定

| 環境変数の状態 | `prof_` |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `1` | 有効。例: `1`, `10`, `1anything` |
| その他の設定値 | 無効。例: `0`, `true`, ` 1` |

値全体の parse、数値変換、大文字小文字変換は行いません。`load()` 中に `getenv()` を一度呼び、その時点で `prof_` を作ります。static cache ではありませんが、この drafter インスタンスではロード後に環境を書き換えても有効状態は変わりません。

## 有効になる条件

値が有効でも、DFlash2 が実際にロードされて使用されなければ計測されません。`generate.cpp` では `--draft dflash2` のほかに、`--mtp`、`--spec 2` 以上、native pack、単一 GPU / CLI モード、draft pack が必要です。条件不足や load 失敗時は stderr に理由を出し、MTP が draft を続けます。DFlash2 対応コードがビルドに含まれない場合もこの環境変数の効果はありません。

## 実行時の詳細

通常の DFlash2 は `prepare()` で `n_new=1..8` の CUDA graph を capture します。プロファイル有効時は `prepare()` が早期 return し、graph を capture しません。各 `draft()` は stream を同期し、context と block の処理を個別に実行します。処理段階ごとに `stamp()` が event を記録し、`prof_collect()` が隣り合う event 間の時間を集計します。集計はラウンド数で割ったミリ秒として、DFlash2 インスタンスの破棄時に stderr へ次の形式で出ます:

```text
strata dflash2 profile (<rounds> rounds, ms per round, total <ms>): <stage> <ms> ...
```

`rounds` が 0 の場合は profile 行を出しません。プロファイル有効時も `draft()` の結果取得やラウンド統計更新は通常経路と共通です。通常の生成終了時に出る `dflash2 ... ms/round drafting ... GPU ...` の集計行は stdout で、profile 行とは別です。コード上、この環境変数による処理は診断・計測のための実行方式変更であり、生成データの保存や環境変数の子プロセス転送は行いません。

## 根拠

- `src/core/dflash2.cpp:64-70,107-114`: 計測専用の説明、profile 状態、および終了時の stderr 出力形式。
- `src/core/dflash2.cpp:83-105`: stage event の記録、隣接 event 間の時間集計、round 数の更新。
- `src/core/dflash2.cpp:218-224`: `load()` 時に値の先頭文字を検査し、profile と timing の別設定を初期化。
- `src/core/dflash2.cpp:476-487,504-550`: profile 時の graph capture 回避、draft round ごとの event 計測と処理。
- `include/strata/core/dflash2.hpp:33-62,86-91`: DFlash2 drafter の公開 API と profile helper。
- `src/program/generate.cpp:5446-5449,5474-5518`: 対応ビルドでの DFlash2 選択条件、失敗時の MTP fallback。
- `src/program/generate.cpp:16159-16165,16494-16503,16831-16840`: graph 準備、round 呼び出し、通常の DFlash2 統計行。
- `docs/DETAILS.md` と `tools/dflash2/README.md` を確認しましたが、`STRATA_DF2_PROFILE` の判定や計測方式に関する追加説明は見当たりませんでした。したがって、性能値や計測による出力同一性は記載していません。
